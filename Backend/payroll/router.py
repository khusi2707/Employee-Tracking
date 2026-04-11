from fastapi import APIRouter, HTTPException, Depends
from auth.utils import get_current_user
from db import get_connection
from .schemas import PayrollRequest
import calendar

router = APIRouter(prefix="/payroll", tags=["Payroll"])

@router.post("/calculate", status_code=201)
def calculate_payroll(data: PayrollRequest, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("hr", "admin"):
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Check employee exists
    cursor.execute("SELECT id, salary FROM employees WHERE id = %s", (data.employee_id,))
    employee = cursor.fetchone()
    if not employee:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Employee not found")

    base_salary = float(employee["salary"])

    # Total days in that month
    total_days = calendar.monthrange(data.year, data.month)[1]

    # Present days from attendance
    cursor.execute(
        """SELECT COUNT(*) as present_days FROM attendance
           WHERE employee_id = %s
           AND MONTH(date) = %s
           AND YEAR(date) = %s""",
        (data.employee_id, data.month, data.year)
    )
    present_days = cursor.fetchone()["present_days"]

    # Overtime hours for the month
    cursor.execute(
        """SELECT COALESCE(SUM(overtime_hours), 0) AS total_overtime
        FROM attendance
        WHERE employee_id = %s AND MONTH(date) = %s AND YEAR(date) = %s""",
        (data.employee_id, data.month, data.year)
    )
    total_overtime = float(cursor.fetchone()["total_overtime"])

    # Overtime pay: hourly rate = monthly salary / (total_days * 8 standard hours)
    hourly_rate = base_salary / (total_days * 8)
    overtime_pay = round(hourly_rate * total_overtime, 2)

    # Factor into net salary
    deduction = (base_salary / total_days) * (total_days - present_days)
    net_salary = base_salary - deduction + overtime_pay

    # Delete existing record for same month/year
    cursor.execute(
        "DELETE FROM payroll WHERE employee_id = %s AND month = %s AND year = %s",
        (data.employee_id, data.month, data.year)
    )

    # Insert new record
    cursor.execute(
    """INSERT INTO payroll (employee_id, month, year, basic_salary, deductions, overtime_hours, overtime_pay, net_salary)
       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
    (data.employee_id, data.month, data.year, base_salary, round(deduction, 2), total_overtime, overtime_pay, round(net_salary, 2))
    )
    conn.commit()

    cursor.execute(
        "SELECT * FROM payroll WHERE employee_id = %s AND month = %s AND year = %s",
        (data.employee_id, data.month, data.year)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    return result

@router.get("/my-payroll")
def my_payroll(current_user: dict = Depends(get_current_user)):
    employee_id = int(current_user["sub"])

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM payroll WHERE employee_id = %s ORDER BY year DESC, month DESC",
        (employee_id,)
    )
    records = cursor.fetchall()
    cursor.close()
    conn.close()

    return records