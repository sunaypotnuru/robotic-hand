# ==============================================================================
# LUNA ROBOTIC ARM & HAND - INDUSTRIAL DOCKER ENGINE CONFIGURATION
# ==============================================================================
# Base: Official stable python-slim image
FROM python:3.10-slim

# Set environment system variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Set container working directory
WORKDIR /app

# Install native system dependencies required for PyAudio, OpenCV, and PostgreSQL compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    portaudio19-dev \
    libasound2-dev \
    libgl1 \
    libglib2.0-0 \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install LUNA Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy full LUNA project workspace inside the container
COPY . .

# Expose cybernetic server port
EXPOSE 5000

# Start LUNA System Orchestrator
CMD ["python", "app.py"]
