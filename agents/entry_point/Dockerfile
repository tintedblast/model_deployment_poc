FROM python:3.11-slim
WORKDIR /app

COPY agents/entry_point/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/entry_point/ .

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}