from fastapi import APIRouter, HTTPException, Depends
from auth.utils import get_current_user
from db import get_connection
import csv
import io
from typing import Optional
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/reports", tags=["Reports"])


# US-06 / US-11: Get all employees — used by HR to pick an employee
# in the payroll calculator and overtime report pages.
@router.get("/employees")
def get_all_employees(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("hr", "admin"):
        raise HTTPException(status_code=403, detail="Access denied. HR or Admin only.")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, name, department, role FROM employees ORDER BY name"
    )
    employees = cursor.fetchall()
    cursor.close()
    conn.close()

    return {"total": len(employees), "employees": employees}


@router.get("/department")
def get_all_departments(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("hr", "admin"):
        raise HTTPException(status_code=403, detail="Access denied. HR or Admin only.")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            department,
            COUNT(*) AS total_employees
        FROM employees
        GROUP BY department
        ORDER BY department
    """)
    departments = cursor.fetchall()
    cursor.close()
    conn.close()

    return {
        "total_departments": len(departments),
        "departments": departments
    }


@router.get("/department/{department_name}")
def get_employees_by_department(
    department_name: str,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") not in ("hr", "admin"):
        raise HTTPException(status_code=403, detail="Access denied. HR or Admin only.")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, email, role, salary
        FROM employees
        WHERE department = %s
        ORDER BY name
    """, (department_name,))
    employees = cursor.fetchall()
    cursor.close()
    conn.close()

    if not employees:
        raise HTTPException(status_code=404, detail=f"No employees found in department '{department_name}'")

    return {
        "department": department_name,
        "total_employees": len(employees),
        "employees": employees
    }


# us15

@router.get("/export-master")
def export_master_report(
    report_type: str, 
    month: Optional[int] = None, 
    year: Optional[int] = None,
    current_user: dict = Depends(get_current_user)  
):
    if current_user.get("role") not in ("hr", "admin"):
        raise HTTPException(status_code=403, detail="Access denied.")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        if report_type == "ranking":
            query = "SELECT * FROM attendance_ranking"
            cursor.execute(query)
            filename = "Attendance_Ranking.csv"
        elif report_type == "summary":
            if not month or not year:
                raise HTTPException(status_code=400, detail="Month and Year required")
            query = "SELECT * FROM monthly_attendance_report WHERE month = %s AND year = %s"
            cursor.execute(query, (month, year))
            filename = f"Attendance_Summary_{month}_{year}.csv"
        elif report_type == "leaves":
            if not month or not year:
                raise HTTPException(status_code=400, detail="Month and Year required")
            query = """
                SELECT e.name AS employee_name, l.leave_type, l.start_date, 
                       l.end_date, l.status
                FROM leaves l JOIN employees e ON l.employee_id = e.id
                WHERE (MONTH(l.start_date) = %s AND YEAR(l.start_date) = %s)
            """
            cursor.execute(query, (month, year))
            filename = f"Leaves_Report_{month}_{year}.csv"
        else:
            raise HTTPException(status_code=400, detail="Invalid type")

        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No data found for this report.")

    # --- ADD THIS CLEANING LOOP TO PREVENT BREAKING ---
    clean_rows = []
    for row in rows:
        # Converts Decimals, Dates, and Nulls to strings so the CSV writer is happy
        clean_row = {k: (str(v) if v is not None else "") for k, v in row.items()}
        clean_rows.append(clean_row)

    output = io.StringIO()
    # Use clean_rows here instead of rows
    writer = csv.DictWriter(output, fieldnames=clean_rows[0].keys())
    writer.writeheader()
    writer.writerows(clean_rows)
    
    output.seek(0)
    return StreamingResponse(
        io.StringIO(output.getvalue()), # Wrapped in StringIO for safety
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
