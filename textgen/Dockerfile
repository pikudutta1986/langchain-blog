FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Update the package list and install the dependencies
RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements.txt file and install the dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app.py file
COPY app.py .

# Expose the port
EXPOSE 8000

# Start the application with uvicorn to serve the FastAPI application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
