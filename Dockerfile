FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-metadata.txt ./
RUN pip install --no-cache-dir -r requirements-metadata.txt
COPY . .
RUN useradd --create-home --shell /usr/sbin/nologin mp3z
USER mp3z
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:80/api/ping')" || exit 1
CMD ["python", "cover_app.py"]
