"""Deployment entrypoint for chatbot.

Additive only — app.py is untouched. It exposes the Flask app for gunicorn's
eventlet worker, adds a /healthz probe, and shouts if the database URI is still
the hardcoded localhost literal.

Why it does NOT repoint the database itself: app.py calls
`db.init_app(app)` at import time, and Flask-SQLAlchemy 3.x builds the engine
inside init_app() from the config as it stands at that moment. By the time this
module can touch anything, the engine already exists with the wrong URL, and
re-initialising raises. That needs a one-line change in app.py (DEPLOY.md §1).

Run with:  gunicorn -k eventlet -w 1 deploy_wsgi:app
"""

import logging
import os

from app import app, socketio  # noqa: F401,E402  (socketio must be imported so
                               # its handlers register on this app instance)

_log = logging.getLogger("deploy_wsgi")

# --- secret key -------------------------------------------------------------
_secret = os.environ.get("SECRET_KEY")
if _secret:
    app.secret_key = _secret
    app.config["SECRET_KEY"] = _secret

# --- database sanity check --------------------------------------------------
_configured = str(app.config.get("SQLALCHEMY_DATABASE_URI", ""))
_wanted = os.environ.get("DATABASE_URL")
if _wanted and _wanted != _configured:
    _log.error(
        "DATABASE_URL is set but app.py hardcodes SQLALCHEMY_DATABASE_URI and "
        "Flask-SQLAlchemy has already built its engine from that literal. The "
        "app is talking to %r, not to DATABASE_URL. Apply the one-line fix in "
        "DEPLOY.md section 1.",
        _configured.split("@")[-1],
    )

# --- health probe -----------------------------------------------------------
if "healthz" not in app.view_functions:

    @app.route("/healthz")
    def healthz():
        """Liveness probe. No DB round trip, so a Postgres blip does not
        restart every live WebSocket connection."""
        return {"status": "ok"}, 200


if __name__ == "__main__":  # pragma: no cover - local smoke test only
    socketio.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 5760)))
