FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Create a dedicated unprivileged user for runtime.
RUN groupadd --system app && \
    useradd --system --gid app --create-home --home-dir /home/app app

# Copy dependency manifest first to maximize layer cache reuse.
COPY requirements.txt ./

# No apt-get packages are installed by default; current requirements are expected
# to resolve using prebuilt wheels on python:3.11-slim.
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt gunicorn

COPY app ./app

RUN chown -R app:app /app

USER app:app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-w", "2", "-b", "0.0.0.0:8000", "--timeout", "60", "--graceful-timeout", "30", "--access-logfile", "-", "--error-logfile", "-"]
