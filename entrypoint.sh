#!/bin/sh
# Make the data directory writable for the app user, then drop root privileges.
set -e
mkdir -p /data
chown -R appuser:appuser /data
exec su -s /bin/sh appuser -c "exec uvicorn app.main:app --host 0.0.0.0 --port 8000"
