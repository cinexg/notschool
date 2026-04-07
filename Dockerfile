# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy just the requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Initialize a fresh SQLite database for the container
RUN python -c "from db.crud import init_db; init_db()"

# Command to run the application using Uvicorn
# Cloud Run automatically injects the $PORT environment variable, so we must bind to it
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]