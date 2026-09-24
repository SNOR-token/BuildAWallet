# Production BuildAWallet: HUMAN builder + NON-HUMAN mainnet agent protocol.
# Requires env: BAW_MASTER_KEY, AGENT_BOOTSTRAP_SECRET, and chain RPC URLs.
# State under /data only.
FROM python:3.12-slim
WORKDIR /app
ENV DATA_DIR=/data
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libffi-dev \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py mcp_server.py chains.py agent_protocol.py wallet_crypto.py evm.py solana_adapter.py utxo_adapter.py pricing.py human_worker.py ./
COPY app ./app
COPY static ./static
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
