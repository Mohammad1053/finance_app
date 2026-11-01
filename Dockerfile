FROM python:3.12-slim

# Do not write .pyc files and flush logs immediately
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# Install dependencies first so Docker can cache this layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Run as a non-root user and give it a writable data directory
RUN useradd --create-home appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data
USER appuser

ENV DATABASE_URL=sqlite:////data/finance.db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]