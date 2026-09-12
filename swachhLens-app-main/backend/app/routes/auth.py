"""Authentication endpoints: register, login, logout, me."""
from __future__ import annotations

import logging
import re
import secrets
import string
import time

from fastapi import APIRouter, Depends, HTTPException

from .. import notify, security
from ..database import execute, query_one
from ..dependencies import get_current_user
from ..models import (
    LoginRequest,
    RegisterRequest,
    ForgotPasswordRequest,
    VerifyOtpRequest,
    ResetPasswordRequest,
    RegisterOtpRequest,
    VerifyRegisterOtpRequest,
    ResendRegisterOtpRequest,
)

log = logging.getLogger("swachlens.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _user_public(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "phone": user.get("phone", ""),
        "name": user["name"],
        "role": user["role"],
        "verified": bool(user.get("verified", 1)),
    }


@router.post("/register", status_code=201)
def register(body: RegisterRequest):
    email = body.email.strip().lower() if body.email else None
    phone = body.phone.strip() if body.phone else None
    if not email and not phone:
        raise HTTPException(status_code=422, detail="Please provide an email or phone number.")
    if email is not None and not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Please enter a valid email address.")
    if email and query_one("SELECT id FROM users WHERE email = ?", (email,)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    if phone and query_one("SELECT id FROM users WHERE phone = ?", (phone,)):
        raise HTTPException(status_code=409, detail="An account with this phone number already exists.")

    # Use phone as identifier if no email
    identifier = email or phone or body.name.strip()
    name = body.name.strip() or identifier
    user = {
        "id": "usr_" + security.sha256_short(identifier),
        "email": email,
        "phone": phone,
        "password_hash": security.hash_password(body.password),
        "name": name,
        "role": body.role,
        "created_at": int(time.time() * 1000),
    }
    execute(
        "INSERT INTO users (id, email, phone, password_hash, name, role, created_at)"
        " VALUES (:id, :email, :phone, :password_hash, :name, :role, :created_at)",
        {
            "id": user["id"],
            "email": user["email"],
            "phone": user["phone"],
            "password_hash": user["password_hash"],
            "name": user["name"],
            "role": user["role"],
            "created_at": user["created_at"],
        },
    )
    return {"user": _user_public(user), "token": security.create_token(user)}


# ---- Phone-OTP registration (account verification) ----

def _normalize_phone(raw: str) -> str:
    """Return a canonical +91XXXXXXXXXX number, or empty if invalid."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) == 10:
        return "+91" + digits
    return ""


def _issue_otp(user_id: str, identifier: str, email: str = "", name: str = "") -> dict:
    """Generate, persist and deliver an OTP for the given user.

    Returns the API response dict. When no SMS/email channel is configured
    (dev mode) the code is returned in the response so the flow stays usable.
    """
    otp_code = _generate_otp()
    now = int(time.time() * 1000)
    execute(
        "INSERT INTO otp_requests (user_id, otp_code, expires_at, verified, created_at)"
        " VALUES (?, ?, ?, 0, ?)",
        (user_id, otp_code, now + 5 * 60 * 1000, now),
    )
    delivered = notify.notify_otp(identifier, otp_code, email=email, name=name)
    if delivered:
        return {"detail": "OTP sent."}
    log.warning(
        "No OTP delivery channel (SMTP/Twilio) — returning the code in the "
        "response for development. Configure SMTP_HOST/SMTP_USER/SMTP_PASS "
        "or TWILIO_* to actually send it."
    )
    return {"detail": "OTP sent.", "otp": otp_code}


@router.post("/register-otp", status_code=200)
def register_otp(body: RegisterOtpRequest):
    """Step 1 of phone-verified registration.

    Validates the details, creates the account in an unverified state and
    sends a 6-digit OTP to the given phone number.
    """
    email = body.email.strip().lower() if body.email else None
    phone = _normalize_phone(body.phone)
    name = body.name.strip()

    if not phone:
        raise HTTPException(status_code=422, detail="Please enter a valid 10-digit phone number.")
    if not name:
        raise HTTPException(status_code=422, detail="Please enter your full name.")
    if email is not None and email and not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Please enter a valid email address.")
    if email and query_one("SELECT id FROM users WHERE email = ?", (email,)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    existing = query_one("SELECT * FROM users WHERE phone = ?", (phone,))
    if existing and existing.get("verified", 1):
        raise HTTPException(status_code=409, detail="An account with this phone number already exists.")

    now = int(time.time() * 1000)
    if existing:
        # Unverified account from a previous attempt — refresh its details and resend.
        user_id = existing["id"]
        execute(
            "UPDATE users SET email = ?, name = ?, password_hash = ?, role = ? WHERE id = ?",
            (email, name, security.hash_password(body.password), body.role, user_id),
        )
        user = {**existing, "email": email, "name": name, "role": body.role}
    else:
        identifier = email or phone
        user = {
            "id": "usr_" + security.sha256_short(identifier),
            "email": email,
            "phone": phone,
            "password_hash": security.hash_password(body.password),
            "name": name,
            "role": body.role,
            "verified": 0,
            "created_at": now,
        }
        execute(
            "INSERT INTO users (id, email, phone, password_hash, name, role, verified, created_at)"
            " VALUES (:id, :email, :phone, :password_hash, :name, :role, :verified, :created_at)",
            user,
        )
        user_id = user["id"]

    resp = _issue_otp(user_id, phone, email=email or "", name=name)
    return {**resp, "phone": phone}


@router.post("/verify-register-otp")
def verify_register_otp(body: VerifyRegisterOtpRequest):
    """Step 2 of phone-verified registration.

    Checks the OTP and marks the account verified, returning the session
    (user + token) so the citizen is logged straight in.
    """
    phone = _normalize_phone(body.phone)
    if not phone:
        raise HTTPException(status_code=422, detail="Please enter a valid 10-digit phone number.")

    user = query_one("SELECT * FROM users WHERE phone = ?", (phone,))
    if not user or user.get("verified", 1):
        raise HTTPException(status_code=400, detail="No pending registration found for this number.")

    now = int(time.time() * 1000)
    otp_row = query_one(
        "SELECT * FROM otp_requests WHERE user_id = ? AND otp_code = ? AND verified = 0"
        " AND expires_at > ? ORDER BY id DESC LIMIT 1",
        (user["id"], body.otp, now),
    )
    if not otp_row:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

    execute("UPDATE otp_requests SET verified = 1 WHERE id = ?", (otp_row["id"],))
    execute("UPDATE users SET verified = 1 WHERE id = ?", (user["id"],))
    user["verified"] = 1
    return {"user": _user_public(user), "token": security.create_token(user)}


@router.post("/resend-register-otp")
def resend_register_otp(body: ResendRegisterOtpRequest):
    """Resend the registration OTP for an unverified account."""
    phone = _normalize_phone(body.phone)
    if not phone:
        raise HTTPException(status_code=422, detail="Please enter a valid 10-digit phone number.")

    user = query_one("SELECT * FROM users WHERE phone = ?", (phone,))
    if not user or user.get("verified", 1):
        raise HTTPException(status_code=400, detail="No pending registration found for this number.")

    resp = _issue_otp(user["id"], phone, email=user["email"] or "", name=user["name"])
    return {**resp, "phone": phone}


@router.post("/login")
def login(body: LoginRequest):
    identifier = body.email.strip()
    # Support login by email, phone, or username (name column)
    if EMAIL_RE.match(identifier.lower()):
        user = query_one("SELECT * FROM users WHERE LOWER(email) = ?", (identifier.lower(),))
    elif re.match(r"^\+?\d{7,15}$", identifier):
        user = query_one("SELECT * FROM users WHERE phone = ?", (identifier,))
    else:
        user = query_one("SELECT * FROM users WHERE LOWER(name) = LOWER(?)", (identifier,))
    if not user or not security.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if not user.get("verified", 1):
        raise HTTPException(
            status_code=403,
            detail="Your account is not verified yet. Please enter the OTP sent to your phone.",
        )
    return {"user": _user_public(user), "token": security.create_token(user)}


@router.post("/logout")
def logout(_user: dict = Depends(get_current_user)):
    # JWTs are stateless; the client just discards the token. A token blacklist
    # can be added later if revocation is needed.
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return _user_public(user)


# ---- Forgot / Reset Password ----

def _generate_otp() -> str:
    """Generate a 6-digit numeric OTP."""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest):
    """Send a 6-digit OTP to the user's email or phone. Returns the OTP in
    the response for development (in production, send via email/SMS only).
    """
    identifier = body.identifier.strip()
    user = None
    if EMAIL_RE.match(identifier.lower()):
        user = query_one("SELECT * FROM users WHERE LOWER(email) = ?", (identifier.lower(),))
    elif re.match(r"^\+?\d{7,15}$", identifier):
        user = query_one("SELECT * FROM users WHERE phone = ?", (identifier,))
    else:
        user = query_one("SELECT * FROM users WHERE LOWER(name) = LOWER(?)", (identifier,))

    # Always return the same message to prevent user enumeration
    if not user:
        return {"detail": "If an account with that identifier exists, an OTP has been sent."}

    otp_code = _generate_otp()
    now = int(time.time() * 1000)
    execute(
        "INSERT INTO otp_requests (user_id, otp_code, expires_at, verified, created_at)"
        " VALUES (?, ?, ?, 0, ?)",
        (user["id"], otp_code, now + 5 * 60 * 1000, now),
    )

    # Actually deliver the code: email via SMTP, phone via Twilio SMS.
    delivered = notify.notify_otp(
        identifier, otp_code, email=user["email"], name=user["name"]
    )
    if delivered:
        return {"detail": "OTP sent."}

    # No delivery channel configured (SMTP / Twilio env vars) or the send
    # failed — keep the flow usable in development by returning the code.
    log.warning(
        "No OTP delivery channel (SMTP/Twilio) — returning the code in the "
        "response for development. Configure SMTP_HOST/SMTP_USER/SMTP_PASS "
        "or TWILIO_* to actually send it."
    )
    return {
        "detail": "OTP sent.",
        "otp": otp_code,
    }


@router.post("/verify-otp")
def verify_otp(body: VerifyOtpRequest):
    """Verify the OTP. On success, return a short-lived reset token."""
    identifier = body.identifier.strip()
    user = None
    if EMAIL_RE.match(identifier.lower()):
        user = query_one("SELECT * FROM users WHERE LOWER(email) = ?", (identifier.lower(),))
    elif re.match(r"^\+?\d{7,15}$", identifier):
        user = query_one("SELECT * FROM users WHERE phone = ?", (identifier,))
    else:
        user = query_one("SELECT * FROM users WHERE LOWER(name) = LOWER(?)", (identifier,))

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

    now = int(time.time() * 1000)
    otp_row = query_one(
        "SELECT * FROM otp_requests WHERE user_id = ? AND otp_code = ? AND verified = 0"
        " AND expires_at > ? ORDER BY id DESC LIMIT 1",
        (user["id"], body.otp, now),
    )
    if not otp_row:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

    # Mark OTP as verified
    execute("UPDATE otp_requests SET verified = 1 WHERE id = ?", (otp_row["id"],))

    # Issue a short-lived reset token (JWT with 10-minute expiry)
    reset_token = security.create_reset_token(user)
    return {"resetToken": reset_token}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest):
    """Reset password using the reset token from verify-otp."""
    payload = security.verify_reset_token(body.token)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    user = query_one("SELECT * FROM users WHERE id = ?", (payload["sub"],))
    if not user:
        raise HTTPException(status_code=400, detail="User not found.")

    new_hash = security.hash_password(body.password)
    execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
    return {"detail": "Password updated successfully."}
