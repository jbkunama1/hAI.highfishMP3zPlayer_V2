FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir mcp>=1.29.0 mutagen>=1.47.0

COPY mcp_server.py /app/mcp_server.py

ENV MUSIC_ROOT=/music

ENTRYPOINT ["python", "/app/mcp_server.py"]