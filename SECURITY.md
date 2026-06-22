# Security

## Secret rotation (do this before launch)

The repository's git history contains a previously committed `.env`
(commits `7512b55`..`6eb822e`). Treat the following as **compromised** and
rotate them:

1. **BOT_TOKEN** — open @BotFather → your bot → API Token → **Revoke** and
   regenerate. Put the new token in `.env` (never commit it).
2. **API_SECRET_KEY** — generate a fresh value:
   `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
   Used only for the dev-only `ADMIN_AUTH_MODE=devkey` fallback.
3. **DB_PASS** — set a new strong PostgreSQL password and update `.env`.
4. (Optional) Purge `.env` from history with `git filter-repo --path .env
   --invert-paths` and force-push. Rotation above is mandatory regardless.

`ENV=production` (the default) refuses to start with empty/default/weak
`API_SECRET_KEY` or `DB_PASS`. Set `ENV=development` for local runs.

## Admin panel authentication

The panel authenticates with **Telegram WebApp `initData`** — a payload signed
by Telegram with the bot token, sent on every request and verified server-side
(`ADMIN_IDS` membership + `auth_date` freshness). No secret is shipped to the
browser. Cookie sessions are intentionally not used: the panel runs in a
Telegram iframe where third-party cookies are unreliable.

- `ADMIN_AUTH_MODE=initdata` (default) — production.
- `ADMIN_AUTH_MODE=devkey` — local dev only; the `X-API-Key` fallback. Rejected
  in production by config validation.

## Webhook mode

`BOT_MODE=webhook` requires a non-empty `WEBHOOK_SECRET`; Telegram's
`X-Telegram-Bot-Api-Secret-Token` is then verified on every update.

## Payments

Payment webhooks are signature-verified (HMAC over the raw body with
`PAYMENT_WEBHOOK_SECRET`), idempotent (`payment_events` table), and the amount
is re-checked server-side against the order. The endpoint is disabled until
`PAYMENT_WEBHOOK_SECRET` is set. Provider-specific payload parsing must be
finalized when a provider is chosen.

## Personal data hygiene

Customer data collected: Telegram id, username, delivery address.

- Delivery addresses and contacts are **never logged** (logging redacts
  secrets/tokens; audit entries store changed field *names* only, never values).
- Restrict DB and admin-API access; the panel requires an admin Telegram id.
- Apply a retention policy: periodically delete delivery addresses / old orders
  once they are no longer operationally needed.

## Reporting

Report suspected vulnerabilities privately to the maintainer rather than via a
public issue.
