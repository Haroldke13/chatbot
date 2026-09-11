# syntax=docker/dockerfile:1
###############################################################################
# chatbot — Flask-SocketIO chat with Flask-Login + PostgreSQL
#
# Build:  docker build -t chatbot:latest .
# Run:    see DEPLOY.md
#
# THIS IMAGE BUILDS AND STARTS, BUT THE APP WILL NOT REACH YOUR DATABASE until
# the hardcoded SQLALCHEMY_DATABASE_URI in app.py is env-ified. DEPLOY.md §1.
#
# Python is pinned to 3.11 deliberately: eventlet is the async worker here and
# it is not reliable on 3.12+.
###############################################################################

FROM python:3.11.9-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# requirements-deploy.txt, not requirements.txt — see the header of that file.
COPY requirements-deploy.txt ./
RUN python -m pip install --upgrade pip setuptools wheel \
 && python -m pip install -r requirements-deploy.txt

FROM python:3.11.9-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=5760

COPY --from=builder /opt/venv /opt/venv

RUN useradd --system --create-home --uid 10004 --shell /usr/sbin/nologin appuser

WORKDIR /app
COPY --chown=root:root . /app

USER appuser

EXPOSE 5760

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5760/healthz', timeout=4).status == 200 else 1)"

# ONE worker, and that is not a typo. Socket.IO keeps long-lived connections
# with server-side session affinity; multiple workers need a Redis message
# queue (socketio = SocketIO(app, message_queue='redis://...')) before they can
# see each other's broadcasts. Until that exists, -w 1 is the correct setting.
CMD ["gunicorn", \
     "--worker-class", "eventlet", \
     "--workers", "1", \
     "--bind", "0.0.0.0:5760", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "deploy_wsgi:app"]
