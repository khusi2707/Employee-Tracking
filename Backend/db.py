import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

load_dotenv()

def get_connection(include_db=True):
    """Connects to MySQL. set include_db=False to connect to the server only."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME") if include_db else None
    )

def setup_database():
    try:
        # Connect to the MySQL server (not the DB) to create the DB first
        conn = get_connection(include_db=False)
        cursor = conn.cursor()
        
        cursor.execute("CREATE DATABASE IF NOT EXISTS hrms")
        print("Database 'hrms' verified/created.")
        
        # Switch to the newly created database
        cursor.execute("USE hrms")

        # Define the Table Schemas
        queries = [
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('employee', 'manager', 'hr', 'admin') DEFAULT 'employee',
                department VARCHAR(100),
                salary DECIMAL(10, 2) DEFAULT 0.00
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                employee_id INT NOT NULL,
                date DATE NOT NULL,
                check_in DATETIME,
                check_out DATETIME,
                overtime_hours DECIMAL(4, 2) DEFAULT 0.00,
                status VARCHAR(20) DEFAULT 'present',
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            )
""",
            """
            CREATE TABLE IF NOT EXISTS leaves (
                id INT AUTO_INCREMENT PRIMARY KEY,
                employee_id INT NOT NULL,
                leave_type VARCHAR(50),
                start_date DATE,
                end_date DATE,
                reason TEXT,
                status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS payroll (
                id INT AUTO_INCREMENT PRIMARY KEY,
                employee_id INT NOT NULL,
                month INT NOT NULL,
                year INT NOT NULL,
                basic_salary DECIMAL(10, 2),
                deductions DECIMAL(10, 2),
                overtime_hours DECIMAL(6, 2) DEFAULT 0.00,
                overtime_pay DECIMAL(10, 2) DEFAULT 0.00,
                net_salary DECIMAL(10, 2),
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            )
            """,
            #US-12-attendace_log
              """
            CREATE TABLE IF NOT EXISTS attendance_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            attendance_id INT,
            action_type VARCHAR(50), 
            log_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            #Trigger for the log
            """
           CREATE TRIGGER IF NOT EXISTS after_attendance_insert
           AFTER INSERT ON attendance
           FOR EACH ROW
           BEGIN
          INSERT INTO attendance_logs (attendance_id, action_type)
            VALUES (NEW.id, 'INSERT');
            END;
             """,

        # US-13: Monthly Attendance View
        """
        CREATE OR REPLACE VIEW monthly_attendance_report AS
        SELECT 
            e.id AS employee_id,
            e.name AS employee_name,
            MONTH(a.date) AS month,
            YEAR(a.date) AS year,
            COUNT(a.id) AS total_days_present
        FROM employees e
        JOIN attendance a ON e.id = a.employee_id
        WHERE a.status = 'present'
        GROUP BY e.id, e.name, MONTH(a.date), YEAR(a.date);
        """,

        # US-14: Attendance Ranking (Leaderboard)
        """
        CREATE OR REPLACE VIEW attendance_ranking AS
        SELECT 
            e.id AS employee_id,
            e.name AS employee_name,
            COUNT(a.id) AS total_days,
            RANK() OVER (ORDER BY COUNT(a.id) DESC) as rank_position
        FROM employees e
        JOIN attendance a ON e.id = a.employee_id
        WHERE a.status = 'present'
        GROUP BY e.id, e.name;
        """
        ]

        for query in queries:
            cursor.execute(query)
        
        print("Tables created successfully.")
        
    except Error as e:
        print(f"Error: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    setup_database()