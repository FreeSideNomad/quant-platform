FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.0 uvicorn==0.30.6
COPY app.py .
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
EXPOSE 4444
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "4444"]
