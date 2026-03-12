FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Update the package list and install the dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* # Remove the package list to free up space   

# Copy the requirements.txt file and install the dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app.py file
COPY app.py .

# Create the models and output directories
RUN mkdir -p /app/models /app/output

# Expose the port
EXPOSE 8001

# Start the application with uvicorn to serve the FastAPI application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
