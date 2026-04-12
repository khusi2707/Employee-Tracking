from pydantic import BaseModel
from typing import List

class EmployeeInDepartment(BaseModel):
    id: int
    name: str
    email: str
    role: str
    salary: float

class DepartmentReport(BaseModel):
    department: str
    total_employees: int
    employees: List[EmployeeInDepartment]