# chatbot

A minimal Flask + Socket.IO real-time group chat server with registration, login and an admin page.

> **The name is misleading.** There is no bot, no NLP and no AI in this repository. "Chatbot" is only
> the UI title; the app is a human-to-human chat room. Every message is broadcast to all connected
> clients — there is no automated reply of any kind.

This is the smallest and cleanest of three near-identical copies of the same project on this account.
The other two are [`chatapp`](https://github.com/Haroldke13/chatapp) (adds a README and a static
export attempt) and [`chatbotapp.github.io`](https://github.com/Haroldke13/chatbotapp.github.io)
(adds Alembic migrations). **Consider keeping one and archiving the others.**

## What it does

`app.py` (~145 lines) is the whole application:

- `/` — landing page
- `/register` — create an account; password hashed with bcrypt; every new user gets the role `User`
- `/login`, `/logout` — Flask-Login sessions
- `/chat` — the chat room (login required)
- `/admin` — lists all users and all chat history; gated by a `role_required('Admin')` decorator

Socket.IO: the client emits `send_message`; the server stores the message in the `chathistory` table
and re-emits `receive_message` to **every** connected client (`broadcast=True`). One global room;
no private messages, no rooms, no typing indicators, no online-user list, no message history replay
on page load.

## Tech stack

Python 3, Flask, Flask-SocketIO, Flask-SQLAlchemy, Flask-Login, Flask-Bcrypt, Flask-Migrate,
`psycopg2` (PostgreSQL), Bootstrap 5 and the Socket.IO 4.0 client from a CDN.

## Setup

```bash
git clone https://github.com/Haroldke13/chatbot.git
cd chatbot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` is unpinned and **does not list `eventlet` or `gevent`**, which Flask-SocketIO
normally needs for a production async worker. You may need `pip install eventlet` as well.

### PostgreSQL is required

`app.py` hardcodes:

```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:password@localhost/chatbot_db'
```

Create a `chatbot_db` database and either match those credentials or edit the line. Tables are
created automatically at startup by `db.create_all()`.

### Run

```bash
python app.py      # starts socketio.run(app, debug=True) on http://127.0.0.1:5000
```

The `Procfile` (`web: python app.py`) targets a PaaS such as Heroku or Render, but running the
Werkzeug dev server in production is not recommended.

## Known issues

- `app.py` defines `User` and `ChatHistory` twice — once by importing them from `user.py`/`db.py`,
  then again as local classes that shadow the imports. `user.py` and `db.py` are effectively dead
  code.
- `db = SQLAlchemy()` is reassigned after `from user import db`, so the two module-level `db` objects
  diverge. It works because everything the app uses is defined after the reassignment, but it is fragile.
- `app.config['SECRET_KEY'] = 'your_secret_key'` — a placeholder. Set a real one before deploying.
- The hardcoded PostgreSQL URI embeds the literal password `password`. That is a placeholder rather
  than a real credential, but it should still come from an environment variable.
- The `role_required` decorator runs before `@login_required` resolves in some orderings and would
  raise on an anonymous user; `/admin` happens to stack them safely, but the decorator is not robust.

## Status

**Working prototype.** Last commit December 2024. Registration, login, broadcast chat and the admin
view all work against a local PostgreSQL instance. No tests and no `.gitignore`.

## Licence

**Proprietary software — all rights reserved.** Copyright © 2026 Joel Harold Onyango.

This repository is not open source. The full terms are in [LICENSE](LICENSE); in
summary, you may not copy, redistribute, modify, sublicense, publish, re-host or
commercially exploit this software, in whole or in part, without the prior
written permission of the copyright holder. Access to this repository does not
grant any licence beyond reading it.
