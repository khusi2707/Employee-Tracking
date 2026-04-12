from fastapi import FastAPI
from auth.router import router as auth_router
from attendance.router import router as attendance_router
from leave.router import router as leave_router
from payroll.router import router as payroll_router
from reports.router import router as reports_router
from db import setup_database

app = FastAPI(title="HRMS API")

app.include_router(auth_router)
app.include_router(attendance_router)
app.include_router(leave_router)
app.include_router(payroll_router)
app.include_router(reports_router)

setup_database()

@app.get("/")
def root():
    return {"message": "HRMS API running"}
