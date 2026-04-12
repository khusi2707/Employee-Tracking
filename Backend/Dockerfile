# 1. Use a lightweight Python image
FROM python:3.10-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy the requirements file from the parent directory
# Note: This works if you build from the ROOT of the project
COPY requirements.txt .

# 4. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy everything from the backend folder into the container
COPY . .

# 6. Expose the port FastAPI runs on
EXPOSE 8000

# 7. Command to run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]