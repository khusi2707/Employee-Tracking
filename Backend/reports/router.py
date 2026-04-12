from fastapi import APIRouter, HTTPException, Depends
from auth.utils import get_current_user
from db import get_connection
import csv
import io
from typing import Optional
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/reports", tags=["Reports"])


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
    # Verify the person
    if current_user.get("role") not in ("hr", "admin"):
        raise HTTPException(
            status_code=403, 
            detail="Access denied. You must be an HR or Admin to download reports."
        )

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        if report_type == "ranking":
            query = "SELECT * FROM attendance_ranking"
            cursor.execute(query)
            filename = "Attendance_Ranking.csv"
            
        elif report_type == "summary":
            if not month or not year:
                raise HTTPException(status_code=400, detail="Month and Year are required for summary")
            query = "SELECT * FROM monthly_attendance_report WHERE month = %s AND year = %s"
            cursor.execute(query, (month, year))
            filename = f"Attendance_Summary_{month}_{year}.csv"
            
        elif report_type == "leaves":
            if not month or not year:
                raise HTTPException(status_code=400, detail="Month and Year are required for leaves")
            query = """
                SELECT e.name AS employee_name, l.leave_type, l.start_date, 
                       l.end_date, l.status
                FROM leaves l JOIN employees e ON l.employee_id = e.id
                WHERE (MONTH(l.start_date) = %s AND YEAR(l.start_date) = %s)
            """
            cursor.execute(query, (month, year))
            filename = f"Leaves_Report_{month}_{year}.csv"
        else:
            raise HTTPException(status_code=400, detail="Invalid type. Use ranking, summary, or leaves")

        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No data found for this report.")

    #  Convert database rows to CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    
    #  Stream the file for download
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )