FROM python:3.12-slim

# Do not write .pyc files and flush logs immediately
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# Install dependencies first so Docker can cache this layer
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 --retries 10 -r requirements.txt

COPY app ./app
COPY entrypoint.sh /entrypoint.sh

# The app runs as appuser; the entrypoint fixes /data ownership first because
# mounted disks are often owned by root
RUN useradd --create-home appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data \
    && chmod +x /entrypoint.sh

ENV DATABASE_URL=sqlite:////data/finance.db

EXPOSE 8000

CMD ["/entrypoint.sh"]
