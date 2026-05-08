FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir mcp-secure-remote \
 && useradd --no-create-home --shell /bin/false mcp

USER mcp

ENTRYPOINT ["mcp-secure-remote"]
