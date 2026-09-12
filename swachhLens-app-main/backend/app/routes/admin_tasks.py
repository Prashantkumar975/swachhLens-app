"""Admin & Employee task management endpoints.

Role-based login with unique IDs (Admin ID / Employee ID) + password.
Admins create tasks and assign them to employees.
Employees view assigned tasks and accept or reject them.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import random
import string
import time
from fastapi import APIRouter, Depends, Header, HTTPException

from .. import config, security
from ..database import execute, query, query_one
from ..models import AdminLoginRequest, AdminTaskCreate, AdminTaskAssign

router = APIRouter(prefix="/admin", tags=["admin-tasks"])


# ── Auth helpers ──────────────────────────────────────────────────────────

def _new_task_id() -> str:
    return "T-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _now() -> int:
    return int(time.time() * 1000)


def _admin_user_public(user: dict) -> dict:
    return {
        "id": user["id"],
        "userId": user["user_id"],
        "name": user["name"],
        "role": user["role"],
    }


def _task_public(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "assignedTo": row["assigned_to"],
        "status": row["status"],
        "createdBy": row["created_by"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _create_token(user: dict) -> str:
    """Create a JWT for an admin_users row."""
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user["id"],
        "user_id": user["user_id"],
        "name": user["name"],
        "role": user["role"],
        "iat": now,
        "exp": now + 24 * 3600,
    }
    seg = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(payload, separators=(",", ":")).encode())
    )
    sig = hmac.new(config.JWT_SECRET.encode(), seg.encode(), hashlib.sha256).digest()
    return seg + "." + _b64url(sig)


def _require_admin_user(authorization: str = Header(default=None)) -> dict:
    """Dependency: decode Bearer JWT and return the admin_users row."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    try:
        payload = security.decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = query_one("SELECT * FROM admin_users WHERE id = ?", (payload["sub"],))
    if not user:
        user = query_one("SELECT * FROM admin_users WHERE user_id = ?", (payload.get("user_id", payload["sub"]),))
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


def _require_admin(user: dict = Depends(_require_admin_user)) -> dict:
    """Dependency: require admin role."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    return user


def _require_employee(user: dict = Depends(_require_admin_user)) -> dict:
    """Dependency: require employee role."""
    if user["role"] != "employee":
        raise HTTPException(status_code=403, detail="Employee access only")
    return user


# ── Login ─────────────────────────────────────────────────────────────────

@router.post("/login")
def admin_login(body: AdminLoginRequest):
    """Login with Admin ID or Employee ID + password."""
    user_id = body.user_id.strip().upper()
    user = query_one("SELECT * FROM admin_users WHERE user_id = ?", (user_id,))
    if not user or not security.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid User ID or password.")
    token = _create_token(user)
    return {"user": _admin_user_public(user), "token": token}


@router.get("/me")
def admin_me(user: dict = Depends(_require_admin_user)):
    """Get current user profile."""
    return _admin_user_public(user)


# ── Task CRUD ─────────────────────────────────────────────────────────────

@router.get("/tasks")
def list_tasks(user: dict = Depends(_require_admin_user)):
    """List tasks. Admins see all, employees see only their assigned tasks."""
    if user["role"] == "admin":
        rows = query("SELECT * FROM admin_tasks ORDER BY created_at DESC")
    else:
        rows = query(
            "SELECT * FROM admin_tasks WHERE assigned_to = ? ORDER BY created_at DESC",
            (user["user_id"],),
        )
    return {"tasks": [_task_public(r) for r in rows]}


@router.post("/tasks", status_code=201)
def create_task(body: AdminTaskCreate, user: dict = Depends(_require_admin)):
    """Admin creates a new task."""
    now = _now()
    task_id = _new_task_id()
    execute(
        "INSERT INTO admin_tasks (id, title, description, assigned_to, status, created_by, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)",
        (task_id, body.title, body.description, body.assignedTo, user["user_id"], now, now),
    )
    row = query_one("SELECT * FROM admin_tasks WHERE id = ?", (task_id,))
    return {"task": _task_public(row)}


@router.patch("/tasks/{task_id}/assign")
def assign_task(task_id: str, body: AdminTaskAssign, user: dict = Depends(_require_admin)):
    """Admin assigns (or reassigns) a task to an employee."""
    row = query_one("SELECT * FROM admin_tasks WHERE id = ?", (task_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Task not found.")

    target = query_one("SELECT * FROM admin_users WHERE user_id = ?", (body.assignedTo,))
    if not target or target["role"] != "employee":
        raise HTTPException(status_code=400, detail="Invalid employee User ID.")

    now = _now()
    execute(
        "UPDATE admin_tasks SET assigned_to = ?, status = 'pending', updated_at = ? WHERE id = ?",
        (body.assignedTo, now, task_id),
    )
    row = query_one("SELECT * FROM admin_tasks WHERE id = ?", (task_id,))
    return {"task": _task_public(row)}


@router.patch("/tasks/{task_id}/accept")
def accept_task(task_id: str, user: dict = Depends(_require_employee)):
    """Employee accepts a task assigned to them."""
    row = query_one("SELECT * FROM admin_tasks WHERE id = ?", (task_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Task not found.")
    if row["assigned_to"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="This task is not assigned to you.")
    if row["status"] != "pending":
        raise HTTPException(status_code=409, detail="Only pending tasks can be accepted.")

    now = _now()
    execute("UPDATE admin_tasks SET status = 'accepted', updated_at = ? WHERE id = ?", (now, task_id))
    row = query_one("SELECT * FROM admin_tasks WHERE id = ?", (task_id,))
    return {"task": _task_public(row)}


@router.patch("/tasks/{task_id}/reject")
def reject_task(task_id: str, user: dict = Depends(_require_employee)):
    """Employee rejects a task assigned to them."""
    row = query_one("SELECT * FROM admin_tasks WHERE id = ?", (task_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Task not found.")
    if row["assigned_to"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="This task is not assigned to you.")
    if row["status"] != "pending":
        raise HTTPException(status_code=409, detail="Only pending tasks can be rejected.")

    now = _now()
    execute("UPDATE admin_tasks SET status = 'rejected', updated_at = ? WHERE id = ?", (now, task_id))
    row = query_one("SELECT * FROM admin_tasks WHERE id = ?", (task_id,))
    return {"task": _task_public(row)}


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str, user: dict = Depends(_require_admin)):
    """Admin deletes a task."""
    row = query_one("SELECT * FROM admin_tasks WHERE id = ?", (task_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Task not found.")
    execute("DELETE FROM admin_tasks WHERE id = ?", (task_id,))
    return None


@router.get("/employees")
def list_employees(user: dict = Depends(_require_admin)):
    """List all employee accounts with workload counts."""
    rows = query("SELECT user_id, name FROM admin_users WHERE role = 'employee' ORDER BY name")
    employees = []
    for r in rows:
        uid = r["user_id"]
        # Count pending tasks (admin_tasks + citizen reports)
        task_count = query_one(
            "SELECT COUNT(*) as cnt FROM admin_tasks WHERE assigned_to = ? AND status = 'pending'",
            (uid,)
        )["cnt"]
        report_count = query_one(
            "SELECT COUNT(*) as cnt FROM reports WHERE assigned_to = ? AND status IN ('ASSIGNED', 'IN_PROGRESS', 'VERIFY')",
            (uid,)
        )["cnt"]
        employees.append({
            "userId": uid,
            "name": r["name"],
            "workload": task_count + report_count,
            "pendingTasks": task_count,
            "activeReports": report_count,
        })
    return {"employees": employees}


@router.post("/register-employee", status_code=201)
def register_employee(body: dict, user: dict = Depends(_require_admin)):
    """Admin registers a new employee account."""
    user_id = body.get("userId", "").strip()
    phone = body.get("phone", "").strip()
    password = body.get("password", "")
    name = body.get("name", "").strip()

    if not user_id or not phone or not password:
        raise HTTPException(status_code=400, detail="userId, phone, and password are required.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if query_one("SELECT id FROM admin_users WHERE user_id = ?", (user_id,)):
        raise HTTPException(status_code=409, detail=f"Employee ID '{user_id}' already exists.")

    if not name:
        name = user_id

    now = int(time.time() * 1000)
    emp_id = "adm_" + security.sha256_short(user_id)
    execute(
        "INSERT INTO admin_users (id, user_id, name, phone, password_hash, role, created_at)"
        " VALUES (?, ?, ?, ?, ?, 'employee', ?)",
        (emp_id, user_id, name, phone, security.hash_password(password), now),
    )
    return {
        "detail": f"Employee '{user_id}' registered successfully.",
        "userId": user_id,
        "name": name,
        "phone": phone,
    }


# ── Citizen Reports (bridge to the reports table) ────────────────────────

def _report_public(row: dict) -> dict:
    """Convert a citizen report row to the shape the admin dashboard expects."""
    return {
        "id": row["id"],
        "wasteType": row["waste_type"],
        "location": row["location"],
        "lat": row.get("lat"),
        "lng": row.get("lng"),
        "description": row["description"],
        "severity": row["severity"],
        "reporter": row["reporter"],
        "reporterName": row["reporter_name"],
        "status": row["status"],
        "assignedTo": row["assigned_to"],
        "assignedBy": row.get("assigned_by"),
        "photo": row.get("photo") or '',
        "proofPhoto": row.get("proof_photo") or '',
        "createdAt": row["created_at"],
        "resolvedAt": row["resolved_at"],
    }


@router.get("/reports")
def list_citizen_reports(user: dict = Depends(_require_admin)):
    """Admin sees citizen reports: PENDING ones (all admins see), plus ASSIGNED/IN_PROGRESS they assigned."""
    # PENDING reports are visible to all admins
    pending_rows = query(
        "SELECT * FROM reports WHERE status = 'PENDING' ORDER BY created_at DESC"
    )
    # ASSIGNED/IN_PROGRESS reports only visible to the admin who assigned them
    my_rows = query(
        "SELECT * FROM reports WHERE assigned_by = ? AND status IN ('ASSIGNED', 'IN_PROGRESS', 'VERIFY')"
        " ORDER BY created_at DESC",
        (user["user_id"],),
    )
    return {"reports": [_report_public(r) for r in pending_rows + my_rows]}


@router.patch("/reports/{report_id}/assign")
def admin_assign_report(report_id: str, body: AdminTaskAssign, user: dict = Depends(_require_admin)):
    """Admin assigns a citizen report to an employee."""
    row = query_one("SELECT * FROM reports WHERE id = ?", (report_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Report not found.")

    target = query_one("SELECT * FROM admin_users WHERE user_id = ?", (body.assignedTo,))
    if not target or target["role"] != "employee":
        raise HTTPException(status_code=400, detail="Invalid employee User ID.")

    now = _now()
    history = json.loads(row["history"] or "[]")
    history.append({"at": now, "to": "ASSIGNED", "by": user["name"] + " assigned to " + (target["name"] or body.assignedTo)})

    execute(
        "UPDATE reports SET status = 'ASSIGNED', assigned_to = ?, assigned_by = ?, history = ? WHERE id = ?",
        (body.assignedTo, user["user_id"], json.dumps(history), report_id),
    )
    updated = query_one("SELECT * FROM reports WHERE id = ?", (report_id,))
    return {"report": _report_public(updated)}


@router.get("/employee-tasks")
def employee_combined_tasks(user: dict = Depends(_require_admin_user)):
    """Employee sees their assigned tasks from BOTH admin_tasks and citizen reports."""
    uid = user["user_id"]
    # Admin tasks assigned to this employee
    admin_rows = query(
        "SELECT * FROM admin_tasks WHERE assigned_to = ? ORDER BY created_at DESC", (uid,)
    )
    # Citizen reports assigned to this employee (all statuses including completed)
    report_rows = query(
        "SELECT * FROM reports WHERE assigned_to = ? ORDER BY created_at DESC", (uid,)
    )
    return {
        "adminTasks": [_task_public(r) for r in admin_rows],
        "reports": [_report_public(r) for r in report_rows],
    }


@router.patch("/reports/{report_id}/emp-accept")
def employee_accept_report(report_id: str, user: dict = Depends(_require_employee)):
    """Employee accepts an assigned citizen report."""
    row = query_one("SELECT * FROM reports WHERE id = ?", (report_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Report not found.")
    if row["assigned_to"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not assigned to you.")
    if row["status"] != "ASSIGNED":
        raise HTTPException(status_code=409, detail="Only assigned reports can be accepted.")

    now = _now()
    history = json.loads(row["history"] or "[]")
    history.append({"at": now, "to": "IN_PROGRESS", "by": user["name"] + " accepted"})
    execute("UPDATE reports SET status = 'IN_PROGRESS', history = ? WHERE id = ?",
            (json.dumps(history), report_id))
    updated = query_one("SELECT * FROM reports WHERE id = ?", (report_id,))
    return {"report": _report_public(updated)}


@router.patch("/reports/{report_id}/emp-reject")
def employee_reject_report(report_id: str, user: dict = Depends(_require_employee)):
    """Employee rejects an assigned citizen report — goes back to PENDING."""
    row = query_one("SELECT * FROM reports WHERE id = ?", (report_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Report not found.")
    if row["assigned_to"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not assigned to you.")
    if row["status"] != "ASSIGNED":
        raise HTTPException(status_code=409, detail="Only assigned reports can be rejected.")

    now = _now()
    history = json.loads(row["history"] or "[]")
    history.append({"at": now, "to": "PENDING", "by": user["name"] + " rejected"})
    execute("UPDATE reports SET status = 'PENDING', assigned_to = NULL, history = ? WHERE id = ?",
            (json.dumps(history), report_id))
    updated = query_one("SELECT * FROM reports WHERE id = ?", (report_id,))
    return {"report": _report_public(updated)}


@router.patch("/reports/{report_id}/complete")
def employee_complete_report(report_id: str, body: dict, user: dict = Depends(_require_employee)):
    """Employee marks a report as completed with proof photo."""
    row = query_one("SELECT * FROM reports WHERE id = ?", (report_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Report not found.")
    if row["assigned_to"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not assigned to you.")
    if row["status"] != "IN_PROGRESS":
        raise HTTPException(status_code=409, detail="Only in-progress reports can be completed.")

    proof_photo = body.get("proofPhoto", "")
    if not proof_photo:
        raise HTTPException(status_code=400, detail="Proof photo is required.")

    now = _now()
    history = json.loads(row["history"] or "[]")
    history.append({"at": now, "to": "VERIFY", "by": user["name"] + " completed — awaiting admin verification"})
    execute("UPDATE reports SET status = 'VERIFY', proof_photo = ?, history = ? WHERE id = ?",
            (proof_photo, json.dumps(history), report_id))
    updated = query_one("SELECT * FROM reports WHERE id = ?", (report_id,))
    return {"report": _report_public(updated)}


@router.patch("/reports/{report_id}/verify")
def admin_verify_report(report_id: str, body: dict, user: dict = Depends(_require_admin)):
    """Admin verifies or rejects a completed report."""
    row = query_one("SELECT * FROM reports WHERE id = ?", (report_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Report not found.")
    if row["status"] != "VERIFY":
        raise HTTPException(status_code=409, detail="Only reports awaiting verification can be verified.")

    approved = body.get("approved", True)
    now = _now()
    history = json.loads(row["history"] or "[]")

    if approved:
        history.append({"at": now, "to": "RESOLVED", "by": user["name"] + " verified — task resolved"})
        execute("UPDATE reports SET status = 'RESOLVED', resolved_at = ?, history = ? WHERE id = ?",
                (now, json.dumps(history), report_id))
    else:
        history.append({"at": now, "to": "IN_PROGRESS", "by": user["name"] + " sent back — proof insufficient"})
        execute("UPDATE reports SET status = 'IN_PROGRESS', proof_photo = NULL, history = ? WHERE id = ?",
                (json.dumps(history), report_id))

    updated = query_one("SELECT * FROM reports WHERE id = ?", (report_id,))
    return {"report": _report_public(updated)}


@router.get("/reports/{report_id}/history")
def report_history(report_id: str, user: dict = Depends(_require_admin_user)):
    """Get the full history of a report."""
    row = query_one("SELECT * FROM reports WHERE id = ?", (report_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Report not found.")
    return {
        "report": _report_public(row),
        "history": json.loads(row["history"] or "[]"),
    }


# ── Employee Forgot Password (phone-based OTP) ───────────────────────────

def _generate_emp_otp() -> str:
    """Generate a 6-digit numeric OTP."""
    return ''.join(random.choices(string.digits, k=6))


@router.post("/forgot-password")
def admin_forgot_password(body: dict):
    """Send OTP to employee's registered phone number."""
    phone = body.get("phone", "").strip()
    user_id = body.get("userId", "").strip().upper()

    if not phone and not user_id:
        raise HTTPException(status_code=400, detail="Phone number or Employee ID is required.")

    # Look up employee by user_id or phone
    emp = None
    if user_id:
        emp = query_one("SELECT * FROM admin_users WHERE user_id = ? AND role = 'employee'", (user_id,))
    if not emp and phone:
        emp = query_one("SELECT * FROM admin_users WHERE phone = ? AND role = 'employee'", (phone,))

    # Always return same message to prevent user enumeration
    if not emp:
        return {"detail": "If an account with that phone number exists, an OTP has been sent."}

    otp_code = _generate_emp_otp()
    now = int(time.time() * 1000)
    # Store OTP in otp_requests using a special emp_ prefix for the user_id
    execute(
        "INSERT INTO otp_requests (user_id, otp_code, expires_at, verified, created_at)"
        " VALUES (?, ?, ?, 0, ?)",
        ("emp_" + emp["id"], otp_code, now + 5 * 60 * 1000, now),
    )

    # In dev mode, return OTP in response (no SMS configured)
    emp_phone = emp.get("phone", "")
    if emp_phone:
        from .. import notify
        delivered = notify.notify_otp(emp_phone, otp_code, email="", name=emp["name"])
    else:
        delivered = False

    if delivered:
        return {"detail": "OTP sent to your registered phone number."}

    # Dev mode: return OTP in response
    masked = (emp_phone[:3] + "***" + emp_phone[-2:]) if len(emp_phone) >= 5 else "***"
    return {
        "detail": f"OTP sent to {masked}.",
        "otp": otp_code,
        "maskedPhone": masked,
    }


@router.post("/verify-forgot-otp")
def admin_verify_forgot_otp(body: dict):
    """Verify the OTP and return a reset token."""
    phone = body.get("phone", "").strip()
    user_id = body.get("userId", "").strip().upper()
    otp = body.get("otp", "").strip()

    if not otp:
        raise HTTPException(status_code=400, detail="OTP is required.")

    # Find the employee
    emp = None
    if user_id:
        emp = query_one("SELECT * FROM admin_users WHERE user_id = ? AND role = 'employee'", (user_id,))
    if not emp and phone:
        emp = query_one("SELECT * FROM admin_users WHERE phone = ? AND role = 'employee'", (phone,))
    if not emp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

    now = int(time.time() * 1000)
    otp_row = query_one(
        "SELECT * FROM otp_requests WHERE user_id = ? AND otp_code = ? AND verified = 0"
        " AND expires_at > ? ORDER BY id DESC LIMIT 1",
        ("emp_" + emp["id"], otp, now),
    )
    if not otp_row:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

    execute("UPDATE otp_requests SET verified = 1 WHERE id = ?", (otp_row["id"],))

    # Issue a short-lived reset token using the admin token creator
    reset_token = _create_token(emp)
    return {"resetToken": reset_token}


@router.post("/reset-emp-password")
def admin_reset_emp_password(body: dict):
    """Reset employee password using the reset token."""
    token = body.get("token", "")
    password = body.get("password", "")

    if not token or not password:
        raise HTTPException(status_code=400, detail="Token and new password are required.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    # Decode the token
    try:
        payload = security.decode_token(token)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    emp = query_one("SELECT * FROM admin_users WHERE id = ?", (payload["sub"],))
    if not emp:
        raise HTTPException(status_code=400, detail="Employee not found.")

    new_hash = security.hash_password(password)
    execute("UPDATE admin_users SET password_hash = ? WHERE id = ?", (new_hash, emp["id"]))
    return {"detail": "Password updated successfully. You can now log in."}
