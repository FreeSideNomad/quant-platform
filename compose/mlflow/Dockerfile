FROM ghcr.io/mlflow/mlflow:v3.1.0

# Add Postgres driver and boto3 (for S3/MinIO artefact store)
RUN pip install --no-cache-dir psycopg2-binary==2.9.* boto3==1.35.*
