from fastapi import APIRouter, HTTPException, Depends
from auth.utils import get_current_user
from db import get_connection

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