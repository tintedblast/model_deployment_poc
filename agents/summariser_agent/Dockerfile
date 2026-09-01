FROM python:3.11-slim
WORKDIR /app

COPY agents/summariser_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ ./core/
COPY shared/ ./shared/
COPY agents/summariser_agent/ .

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}