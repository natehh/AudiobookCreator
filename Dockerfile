FROM python:3.9-slim

# Add logging during build
RUN echo "Installing system dependencies..."
RUN apt-get update && apt-get install -y \
    ffmpeg \
    sqlite3 \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

RUN echo "pcm.!default { type null }" > /etc/asound.conf

RUN mkdir -p /app/data && chmod -R 777 /app/data

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Copy .env file
COPY .env .env

# Install Python dependencies with verbose output
RUN pip install --no-cache-dir -r requirements.txt -v

# Copy application code
COPY ./audiobook_creator /app/audiobook_creator

# Create directories with feedback
RUN echo "Creating directories..." && \
    mkdir -p output && \
    mkdir -p tmp

# Expose port
EXPOSE 8000

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1

# Run with more verbose logging
CMD ["uvicorn", "audiobook_creator.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug"]