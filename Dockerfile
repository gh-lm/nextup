# ---- Build stage: install dependencies into a self-contained venv ----
FROM python:3.12-slim-bookworm AS build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools \
 && pip install --no-cache-dir -r /tmp/requirements.txt \
 # Nothing installs anything at runtime, so the installer itself is dropped.
 # It is the only reason setuptools and pip's vendored libraries were in the
 # finished image, and they were the bulk of what a scanner complained about.
 && pip uninstall -y pip setuptools wheel 2>/dev/null || true

# ---- Final stage: runtime only ----
FROM python:3.12-slim-bookworm

# Patch OS packages at build time.
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin nextup

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NEXTUP_DATA_DIR=/data

COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY app ./app
COPY wsgi.py run.py VERSION ./

RUN mkdir -p /data && chown -R 1000:1000 /data /app

USER 1000
EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/login', timeout=8)" || exit 1

# One worker, several threads: the background refresh thread should exist once,
# and SQLite is happiest with a single writer process.
# --no-control-socket: nothing here drives gunicorn through its control
# interface, and it is the one thing that wants to write outside /data, which
# stops the container running with a read-only filesystem.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", \
     "--timeout", "180", "--no-control-socket", "--access-logfile", "-", \
     "wsgi:application"]
