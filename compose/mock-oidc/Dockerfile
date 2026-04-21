FROM python:3.12-slim

RUN pip install --no-cache-dir \
    fastapi==0.115.* \
    uvicorn[standard]==0.34.* \
    pyjwt[crypto]==2.10.* \
    cryptography==44.* \
    python-multipart==0.0.*

WORKDIR /app
COPY mock_oidc.py ./

EXPOSE 9800
CMD ["uvicorn", "mock_oidc:app", "--host", "0.0.0.0", "--port", "9800"]
