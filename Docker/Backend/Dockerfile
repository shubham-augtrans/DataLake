FROM python:3.12-slim

# Prevent python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Print logs immediately
ENV PYTHONUNBUFFERED=1

# Install system packages
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Copy requirements first (better caching)
COPY core/requirements ./requirements

# Install dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements/requirements.txt

# Copy Django project
COPY core/ .

# Expose Django port
EXPOSE 8000

# Default command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]