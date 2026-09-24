# see.io site contract: HTTP on :8080, state ONLY under /data.
FROM python:3.12-slim
WORKDIR /app
ENV DATA_DIR=/data
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt
# The public container ships only the builder and read-only discovery code.
# In particular, it does not contain agent_protocol.py or any wallet key adapter.
COPY main.py mcp_server.py chains.py ./
COPY app ./app
COPY static ./static
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
