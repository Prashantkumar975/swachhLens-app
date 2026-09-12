"""SwachhLens — OTP delivery (email via SMTP, SMS via Twilio).

Uses only the Python standard library so the backend needs no extra
dependencies. Credentials come from environment variables (see .env.example):

  Email (SMTP):
    SMTP_HOST        e.g. smtp.gmail.com
    SMTP_PORT        default 587
    SMTP_USER        the sender account / username
    SMTP_PASS        the account password or app password
    SMTP_FROM        optional "From" address (defaults to SMTP_USER)
    SMTP_USE_TLS     "1" (default) to STARTTLS before login

  SMS (Twilio):
    TWILIO_ACCOUNT_SID
    TWILIO_AUTH_TOKEN
    TWILIO_FROM_NUMBER   e.g. +15017122661

When no channel is configured, notify_otp() returns False and the caller
falls back to dev mode (OTP returned in the API response).
"""
from __future__ import annotations

import base64
import logging
import os
import re
import smtplib
import urllib.parse
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr

log = logging.getLogger("swachlens.notify")

APP_NAME = "SwachhLens"
OTP_MINUTES = 5

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?\d{7,15}$")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "") or SMTP_USER
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1") == "1"

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER", "")


def email_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASS)


def sms_configured() -> bool:
    return bool(TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM)


def send_email(to_email: str, otp: str, name: str = "") -> bool:
    """Send the OTP by email over SMTP. Returns True on success."""
    if not email_configured():
        log.warning("SMTP not configured — cannot email OTP to %s", to_email)
        return False

    greeting = f"Hi {name.strip()}," if (name or "").strip() else "Hi,"
    msg = EmailMessage()
    msg["Subject"] = f"{APP_NAME}: Your password reset code"
    msg["From"] = formataddr((APP_NAME, SMTP_FROM))
    msg["To"] = to_email
    msg.set_content(
        f"{greeting}\n\n"
        f"Your {APP_NAME} password reset code is: {otp}\n\n"
        f"This code expires in {OTP_MINUTES} minutes. "
        f"If you didn't request it, you can safely ignore this email.\n\n"
        f"— The {APP_NAME} team"
    )
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as srv:
            if SMTP_USE_TLS:
                srv.starttls()
            srv.login(SMTP_USER, SMTP_PASS)
            srv.send_message(msg)
        log.info("OTP email sent to %s", to_email)
        return True
    except Exception:  # noqa: BLE001 — never leak credentials / break the flow
        log.exception("Failed to send OTP email to %s", to_email)
        return False


def send_sms(to_phone: str, otp: str) -> bool:
    """Send the OTP by SMS via the Twilio REST API (stdlib urllib)."""
    if not sms_configured():
        log.warning("Twilio not configured — cannot SMS OTP to %s", to_phone)
        return False

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
    body = urllib.parse.urlencode(
        {
            "To": to_phone,
            "From": TWILIO_FROM,
            "Body": f"Your {APP_NAME} password reset code is: {otp}. "
                    f"It expires in {OTP_MINUTES} minutes.",
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body)
    req.add_header(
        "Authorization",
        "Basic " + base64.b64encode(f"{TWILIO_SID}:{TWILIO_TOKEN}".encode()).decode(),
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 (https)
            ok = 200 <= resp.status < 300
        if ok:
            log.info("OTP SMS sent to %s", to_phone)
        return ok
    except Exception:  # noqa: BLE001
        log.exception("Failed to send OTP SMS to %s", to_phone)
        return False


def notify_otp(identifier: str, otp: str, email: str = "", name: str = "") -> bool:
    """Deliver an OTP to the right channel for the given identifier.

    - email address  → SMTP email
    - phone number   → Twilio SMS
    - username       → email if the account has one
    Returns True only when a real delivery channel was used successfully.
    """
    identifier = (identifier or "").strip()
    if EMAIL_RE.match(identifier.lower()):
        return send_email(email or identifier, otp, name)
    if PHONE_RE.match(identifier):
        return send_sms(identifier, otp)
    if email and EMAIL_RE.match(email.lower()):
        return send_email(email, otp, name)
    return False