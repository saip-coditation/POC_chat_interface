# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy backend project
COPY backend/ /app/

# Copy frontend files to a location where collectstatic can find them
COPY css/ /app/static_src/css/
COPY js/ /app/static_src/js/
COPY public/ /app/static_src/public/
COPY index.html /app/templates/

# Expose port
EXPOSE 8000

# Run migrations, collect static files, and start server
CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]
