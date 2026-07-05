FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Cloud Run sets $PORT (default 8080).
ENV PORT=8080
CMD exec uvicorn app.api:app --host 0.0.0.0 --port ${PORT}
