FROM python:3.12-slim AS base

WORKDIR /app

RUN pip install --no-cache-dir uv

# Install agent dependencies
RUN uv pip install --system --no-cache \
    "google-adk>=1.26.0" \
    "mcp>=1.8.0" \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.34.0" \
    "pyyaml>=6.0.2"

COPY . .

EXPOSE 8001

CMD ["uvicorn", "agent.serve_a2a:app", "--host", "0.0.0.0", "--port", "8001"]
