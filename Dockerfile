FROM python:3.13-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 10000
CMD ["sh","-c","uvicorn cloudapp:app --host 0.0.0.0 --port ${PORT:-10000}"]
