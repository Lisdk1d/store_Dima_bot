# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Telegram e-commerce shop bot (Russian-language) with three deployable services backed by one PostgreSQL database:

- **Bot** (`bot/main.py`) — aiogram 3 Telegram bot. Customer storefront (browse catalog → cart → checkout) and admin commands.
- **Admin API** (`bot/api_main.py`) — FastAPI backend exposing catalog/orders/stats over HTTP, secured by an API key.
- **Frontend** (`frontend/`) — Vite + vanilla JS admin dashboard (no framework) that consumes the Admin API.

The bot and API share the same source tree under `bot/src/` and the same DB access layer.

## Commands

All Python commands run from the **`bot/`** directory (imports are rooted at `src.`, and i18n file paths in `main.py` are relative to `bot/`). Running from the repo root will break imports and translation loading.

```bash
# Local dev (requires a running PostgreSQL reachable per .env, and a venv)
cd bot
python main.py                                   # start the bot (polling or webhook per BOT_MODE)
uvicorn api_main:app --host 0.0.0.0 --port 8000  # start the admin API

# Frontend
cd frontend
npm install
npm run dev        # Vite dev server on :5173, proxies /api and /health → localhost:18000
npm run build      # production build to dist/

# Full stack via Docker (postgres + bot + api + frontend)
cp .env.example .env   # then fill BOT_TOKEN, ADMIN_IDS, API_SECRET_KEY
docker compose up --build -d
docker compose ps
docker compose logs -f bot

# Quick API checks
curl http://localhost:18000/health
curl -H "X-API-Key: <API_SECRET_KEY>" http://localhost:18000/api/stats
```

There is **no automated test suite** (`TESTING_LOG.md` is a manual end-to-end checklist) and **no linter configured**. `venv/` is committed in the tree but is gitignored going forward; do not edit files under it.

Docker port mapping: bot `18080→8080`, api `18000→8000`, frontend `13000→80`. Inside Compose the bot/api reach Postgres at host `postgres:5432` (overridden via env in `docker-compose.yml`).

## Architecture

### Database access — single chokepoint
All DB access goes through one class in `bot/src/utils/db.py`, exported as the singleton `db`. Both the bot handlers and the FastAPI endpoints call `db.*` methods — never construct sessions or queries elsewhere. The method names (e.g. `get_unique_categories`, `add_to_cart`, `create_order`) are a deliberately preserved public API carried over from a prior MongoDB implementation, so keep signatures stable when refactoring.

ORM models live in `bot/src/models/` (`User`, `CartItem`, `Product`, `Order`, `OrderItem`, `Payment`) on SQLAlchemy 2.0 async (`asyncpg`). `src/models/base.py` holds the engine/`async_session` factory.

### Schema management — no migration tool
There is **no Alembic**. `init_db()` (in `base.py`) runs `Base.metadata.create_all` on startup, then `_migrate_schema()` applies a hand-written list of idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` statements. **When you add a column to a model, you must also append a matching `ALTER TABLE` to `_migrate_schema()`** or existing databases won't get the column. Both entrypoints call `init_db()` at startup.

### Category normalization
Categories are free-text strings stored on `Product`, not a separate table. `db.py` contains normalization/dedup/alias-merge logic (`_normalize_category_for_match`, `_deduplicate_categories`, `_merge_category_aliases`) that collapses categories differing only by case/whitespace/zero-width chars. Use the existing helpers rather than comparing category strings directly.

### Bot structure (aiogram)
Routers are composed bottom-up: `src/handlers/__init__.py` includes `admin` then `user` routers, each of which aggregates `message`/`callback`/`checkout` sub-routers in their own `__init__.py`. To add a handler, register it on the appropriate sub-router.

- **FSM flows** are defined in `src/utils/states.py` (product add/edit, delete, checkout). Checkout is `quantity → address → payment`.
- **Middlewares** (`src/utils/middlewares.py`): `ThrottlingMiddleware` (TTLCache, drops bursts), `TranslateMiddleware` (injects a fluentogram translator as `locale`), `AlbumMiddleware` (buffers media-group photos). All three are wired in `create_dispatcher()` in `main.py`.
- **i18n**: all user-facing text is in Fluent files at `bot/src/i18n/ru/{text,button}.ftl`, loaded in `main.py`. The hub is Russian-only (`root_locale="ru"`). Add strings to the `.ftl` files, not inline.
- **Admin access** is gated by `ADMIN_IDS` from config; admin bot commands are registered per-admin via `BotCommandScopeChat` in `setup_commands()`.
- **Run mode** is `BOT_MODE` (`polling` default | `webhook`). Webhook mode requires `WEBHOOK_HOST` and serves an aiohttp app; token is validated against Telegram before start.

### Admin API ↔ Frontend
`api_main.py` defines Pydantic request/response models and thin endpoints that delegate to `db`. Every data endpoint depends on `verify_api_key`, which accepts the key via `X-API-Key` header or `Authorization: Bearer`. CORS origins come from `settings.CORS_ORIGINS`. The frontend (`frontend/src/main.js`) is a single file holding all state and rendering; the API key is supplied at build time (`VITE_API_SECRET_KEY`) or entered in the UI, and `VITE_API_URL` empty means same-origin (nginx proxies `/api`).

### Configuration
All config is via `pydantic-settings` in `src/utils/config.py`, loaded from `.env`. Note `ADMIN_IDS` and `CORS_ORIGINS` are parsed as JSON (e.g. `ADMIN_IDS=[123456789]`). `DATABASE_URL` and `webhook_url` are derived properties.

## Deployment
`scripts/deploy.sh` does `git pull` + `docker compose up -d --build` on a VPS. Production runs the bot in webhook mode behind an HTTPS reverse proxy (nginx config in `deploy/` and `frontend/nginx.conf`). `scripts/migrate_mongo_to_postgres.py` is a one-off data migration from the legacy MongoDB store.
