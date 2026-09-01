FROM python:3.11-slim
WORKDIR /app

COPY agents/triage_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/triage_agent/ .

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}