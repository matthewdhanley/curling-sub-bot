FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source files
COPY bot.py db.py ./
COPY cogs/ cogs/

# Mount point for the SQLite volume
RUN mkdir -p /data

ENV PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
