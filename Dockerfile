# ---- Build stage: install dependencies into a self-contained venv ----
FROM python:3.14-slim-trixie@sha256:0514bc76712d64f8bb48adcb95b1ab0d88c69fee95d62fe4c18ee948bee9b1e1 AS build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir pip==26.2.2 \
 && pip install --no-cache-dir --require-hashes --only-binary=:all: -r /tmp/requirements.lock \
 && pip uninstall -y pip

FROM python:3.14-slim-trixie@sha256:0514bc76712d64f8bb48adcb95b1ab0d88c69fee95d62fe4c18ee948bee9b1e1

RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip uninstall -y pip

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin nextup

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NEXTUP_DATA_DIR=/data

COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY app ./app
COPY wsgi.py run.py VERSION LICENSE ./

RUN mkdir -p /data && chown -R 1000:1000 /data /app

USER 1000
EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/login', timeout=8)" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", \
     "--timeout", "180", "--no-control-socket", "--access-logfile", "-", \
     "wsgi:application"]
