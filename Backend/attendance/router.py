from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, time
from auth.utils import get_current_user
from db import get_connection
import csv
import io
from fastapi.responses import StreamingResponse
from typing import Optional

router = APIRouter(prefix="/attendance", tags=["Attendance"])

@router.post("/mark", status_code=201)
def mark_attendance(current_user: dict = Depends(get_current_user)):
    employee_id = int(current_user["sub"])
    now = datetime.now()
    today = now.date()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)


    # --- (added ) ---
    # Check if the employee has an APPROVED leave for today
    leave_query = """
        SELECT id FROM leaves 
        WHERE employee_id = %s 
        AND status = 'approved' 
        AND %s BETWEEN start_date AND end_date
    """
    cursor.execute(leave_query, (employee_id, today))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=400, 
            detail="You are currently on an approved leave. Attendance marking is disabled."
        )
    # --------------------------------------------

    cursor.execute(
        "SELECT id FROM attendance WHERE employee_id = %s AND date = %s",
        (employee_id, today)
    )
    if cursor.fetchone():
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Attendance already marked for today")

    cursor.execute(
        "INSERT INTO attendance (employee_id, date, check_in, status) VALUES (%s, %s, %s, %s)",
        (employee_id, today, now, "present")
    )
    conn.commit()
    cursor.close()
    conn.close()

    return {
        "message": "Attendance marked successfully",
        "employee_id": employee_id,
        "check_in": now,
        "date": today
    }

# Configurable working hours threshold — change when needed
STANDARD_HOURS = 8.0

@router.post("/checkout", status_code=200)
def checkout(current_user: dict = Depends(get_current_user)):
    employee_id = int(current_user["sub"])
    now = datetime.now()
    today = now.date()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT id, check_in, check_out FROM attendance WHERE employee_id = %s AND date = %s",
        (employee_id, today)
    )
    record = cursor.fetchone()

    if not record:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="No check-in found for today. Mark attendance first.")

    if record["check_out"]:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Already checked out for today.")

    hours_worked = (now - record["check_in"]).total_seconds() / 3600
    overtime = round(max(0.0, hours_worked - STANDARD_HOURS), 2)

    cursor.execute(
        "UPDATE attendance SET check_out = %s, overtime_hours = %s WHERE id = %s",
        (now, overtime, record["id"])
    )
    conn.commit()
    cursor.close()
    conn.close()

    return {
        "message": "Checked out successfully",
        "employee_id": employee_id,
        "check_out": now,
        "hours_worked": round(hours_worked, 2),
        "overtime_hours": overtime
    }

# Change this variable when the official start time is decided
LATE_THRESHOLD = time(9, 0, 0)  # 09:00 AM


def _query_late_records(employee_id=None):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT
            a.id,
            a.employee_id,
            e.name AS employee_name,
            e.department,
            a.date,
            a.check_in,
            TIMEDIFF(TIME(a.check_in), %s) AS late_by
        FROM attendance a
        JOIN employees e ON e.id = a.employee_id
        WHERE TIME(a.check_in) > %s
    """
    params = [LATE_THRESHOLD.strftime("%H:%M:%S"), LATE_THRESHOLD.strftime("%H:%M:%S")]

    if employee_id is not None:
        query += " AND a.employee_id = %s"
        params.append(employee_id)

    query += " ORDER BY a.date DESC"

    cursor.execute(query, params)
    records = cursor.fetchall()
    cursor.close()
    conn.close()
    return records


@router.get("/late-mark/all")
def get_all_late_marks(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("hr", "admin"):
        raise HTTPException(status_code=403, detail="Access denied. HR or Admin only.")

    records = _query_late_records()
    return {
        "late_threshold": LATE_THRESHOLD.strftime("%H:%M"),
        "total_late_records": len(records),
        "records": records
    }


@router.get("/late-mark/me")
def get_my_late_marks(current_user: dict = Depends(get_current_user)):
    employee_id = int(current_user["sub"])
    records = _query_late_records(employee_id=employee_id)
    return {
        "employee_id": employee_id,
        "late_threshold": LATE_THRESHOLD.strftime("%H:%M"),
        "total_late_records": len(records),
        "records": records
    }

@router.get("/overtime/{employee_id}")
def get_overtime_summary(employee_id: int, month: int, year: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("hr", "admin"):
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, name FROM employees WHERE id = %s", (employee_id,))
    employee = cursor.fetchone()
    if not employee:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Employee not found")

    cursor.execute(
        """SELECT date, check_in, check_out, overtime_hours
           FROM attendance
           WHERE employee_id = %s AND MONTH(date) = %s AND YEAR(date) = %s
           AND overtime_hours > 0
           ORDER BY date""",
        (employee_id, month, year)
    )
    records = cursor.fetchall()

    cursor.execute(
        """SELECT COALESCE(SUM(overtime_hours), 0) AS total_overtime
           FROM attendance
           WHERE employee_id = %s AND MONTH(date) = %s AND YEAR(date) = %s""",
        (employee_id, month, year)
    )
    total = cursor.fetchone()["total_overtime"]

    cursor.close()
    conn.close()

    return {
        "employee_id": employee_id,
        "employee_name": employee["name"],
        "month": month,
        "year": year,
        "total_overtime_hours": float(total),
        "breakdown": records
    }


#us13

@router.get("/report/monthly")
def get_monthly_attendance_report(current_user: dict = Depends(get_current_user)):
    # Check if admin or hr:
    if current_user.get("role") not in ("hr", "admin"):
        raise HTTPException(status_code=403, detail="Access denied. HR or Admin only.")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # call the view
        cursor.execute("SELECT * FROM monthly_attendance_report ORDER BY year DESC, month DESC, total_days_present DESC")
        report = cursor.fetchall()
        
        return {
            "status": "success",
            "report_generated_at": datetime.now(),
            "data": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()
#us 14
@router.get("/leaderboard")
def get_leaderboard():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # calls the US-14 View 
    cursor.execute("SELECT * FROM attendance_ranking")
    ranking = cursor.fetchall()

    cursor.close()
    conn.close()
    return ranking

