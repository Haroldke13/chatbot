# Deploying `chatbot`

Flask-SocketIO group chat with Flask-Login accounts, bcrypt passwords, an
`Admin` role view, and PostgreSQL-backed message history.

| Fact | Value |
|---|---|
| WSGI entrypoint | `deploy_wsgi:app`, run under gunicorn's **eventlet** worker |
| Listens on | `5760` inside the container |
| Suggested hostname | `chat.harolditdata.uk` |
| Persistent state | PostgreSQL (external) |
| Transport | WebSocket + HTTP long-polling fallback |

This is the cleanest of the three near-identical chat repos (`chatapp` and
`chatbotapp.github.io` are the others; both carry a committed `venv/` and should
be archived rather than deployed).

---

## 1. BLOCKER — the database URI is hardcoded

`app.py` line 17:

```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:password@localhost/chatbot_db'
```

and three lines later `db.init_app(app)` runs. Flask-SQLAlchemy 3.x **builds the
engine inside `init_app()`** from the config as it stands at that moment, and
re-initialising the same app raises `RuntimeError`. So this cannot be fixed from
`deploy_wsgi.py` or from any other new file — by the time anything else runs,
the engine already exists pointing at `localhost`.

It is a one-line change in `app.py`:

```python
import os
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
```

`deploy_wsgi.py` detects the mismatch and logs a loud error at startup if
`DATABASE_URL` is set but ignored, so you will not silently run against nothing.

Until it lands, the container starts, serves `/healthz`, renders the login page,
and fails on the first query. Do not add the DNS record yet.

(If you truly cannot patch it, the other way out is to give the container a
Postgres actually reachable at `localhost:5432` inside its own network
namespace — e.g. a compose service with `network_mode: "service:db"` and role
`postgres` / password `password` / database `chatbot_db`. That works, but you are
then running a database whose password is published on GitHub. Patch the line.)

## 2. Environment variables

| Variable | Required | Default | Read by | Notes |
|---|---|---|---|---|
| `DATABASE_URL` | **Yes** (after the fix above) | `postgresql://postgres:password@localhost/chatbot_db` (hardcoded) | `app.py`, once patched | SQLAlchemy URL. With `psycopg2-binary` the scheme is `postgresql://`. Note that managed providers hand you `postgres://`, which SQLAlchemy 2.x rejects — rewrite the scheme. |
| `SECRET_KEY` | **Yes, in production** | `'your_secret_key'` (hardcoded in `app.py`) | `deploy_wsgi.py` | Signs the session cookie that Flask-Login and the Socket.IO handshake both rely on. The current literal is public, so anyone can forge a login. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `PORT` | No | `5760` | `Procfile` only | The Dockerfile binds 5760 unconditionally. |

No third-party API keys. Despite the repo name there is no LLM and no chatbot in
it — it is a human-to-human chat room.

## 3. Create the schema

`db.create_all()` only runs under `if __name__ == '__main__'`, which gunicorn
never executes, and the repo ships no migrations. Create the tables once:

```bash
docker run --rm --env-file /etc/harold/chatbot.env chatbot:latest \
  python -c "from deploy_wsgi import app; from app import db; \
             app.app_context().push(); db.create_all(); print('tables created')"
```

Tables: `user` (id, username, email, password, role) and `chathistory`
(id, user_id, message, timestamp).

To make yourself an admin you must set `role = 'Admin'` in the database by hand
— registration hardcodes `role = 'User'` and there is no promotion route.

## 4. Build and run

```bash
docker build -t chatbot:latest .

docker run -d --name chatbot \
  --restart unless-stopped \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m \
  -p 127.0.0.1:5760:5760 \
  --env-file /etc/harold/chatbot.env \
  --memory 350m --cpus 0.5 \
  chatbot:latest
```

### Why one worker

```
gunicorn --worker-class eventlet --workers 1 ...
```

Socket.IO connections are long-lived and stateful. With two or more workers, a
message broadcast by worker A never reaches clients held by worker B, and the
polling fallback breaks outright without sticky sessions. Multiple workers
require a Redis message queue first:

```python
socketio = SocketIO(app, message_queue='redis://redis:6379/0')
```

One eventlet worker handles hundreds of idle sockets on a few hundred MB. That
is well past what this app will ever see.

**Known limitation:** eventlet monkey-patches the world, but `psycopg2` is a C
extension and its socket calls are *not* cooperative — a slow query blocks every
WebSocket in the worker. Fine at this scale; it is the reason not to grow this
app on eventlet without moving to `psycopg` 3 async or a thread pool.

Python is pinned to **3.11** in the Dockerfile because eventlet is unreliable on
3.12+. If you want a newer Python, switch to
`gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker` with
`gevent` + `gevent-websocket` instead.

## 5. Dependencies

The build uses **`requirements-deploy.txt`**, added by this pass;
`requirements.txt` is untouched. Reasons, in full, are in the header of that
file: the original is unpinned, asks for source-build `psycopg2`, and contains
no WSGI server or async worker.

## 6. Health check

`GET /healthz` → `{"status": "ok"}`, added by `deploy_wsgi.py`. It does not
touch the database on purpose: a Postgres blip should not cause Docker to
restart the container and drop every live WebSocket.

## 7. Cloudflare tunnel

```yaml
  - hostname: chat.harolditdata.uk
    service: http://localhost:5760
```

Cloudflare proxies WebSockets by default, so no extra flags are needed. Keep the
tunnel's `originRequest.connectTimeout` default and do **not** set a short
`idleTimeout` — it would cut idle chat sockets. Full config in
`/home/onyango/Projects/DEPLOYMENT_PLAN.md`.

## 8. Other things found while reading the code

- `app.py` imports `db`/`User` from `user.py` and `ChatHistory` from `db.py`,
  then immediately redefines all three against a fresh `SQLAlchemy()` instance.
  The imported ones are dead but still register duplicate model classes on a
  second metadata. It works; it is confusing. `user.py` and `db.py` can be
  deleted once you confirm nothing else imports them.
- `role_required` checks `current_user.role` but is applied *below*
  `@login_required`, so an anonymous user hits the login redirect first. Correct
  by luck, not by design.
- `handle_send_message` trusts `data['message']` and stores it raw; the template
  is responsible for escaping. Check `chat.html` does not use `|safe` before you
  expose this.
- There is no rate limiting on registration or on message send.

## 9. Files added by the deployment pass

`Dockerfile`, `.dockerignore`, `requirements-deploy.txt`, `deploy_wsgi.py`,
`DEPLOY.md`, and a rewritten `Procfile`.

The old `Procfile` said `web: python app.py`, which runs
`socketio.run(app, debug=True)` — the Werkzeug development server with the
debugger enabled. That is a remote-code-execution hole if it is ever reachable
from the internet, so it was replaced with the gunicorn line. It is the only
pre-existing file this pass changed, and it is a deployment file, not source.
