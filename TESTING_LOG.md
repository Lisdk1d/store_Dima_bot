# StoreDima Bot — Testing Log

Date: 2026-06-13

## Phase 3: End-to-End Testing Findings

| # | Area | Issue | Severity | Status |
|---|------|-------|----------|--------|
| 1 | Database | MongoDB (Motor) used instead of PostgreSQL | Critical | **Fixed** — migrated to SQLAlchemy + asyncpg |
| 2 | Admin delete | `/del_from_db` called `db.products.delete_one()` (Mongo API) | Critical | **Fixed** — uses `db.delete_model_by_name()` |
| 3 | Admin | No product editing flow | High | **Fixed** — `/edit` command + inline field selection |
| 4 | Admin | No bulk category deletion | High | **Fixed** — `/del_category` command |
| 5 | Checkout | No payment method selection | High | **Fixed** — 5 payment options on cart/single buy |
| 6 | Orders | Orders not persisted | Medium | **Fixed** — `orders`, `order_items`, `payments` tables |
| 7 | FSM | Delete flow didn't clear state | Low | **Fixed** — `await state.clear()` after delete |
| 8 | UX | `main_menu` failed on photo messages (`edit_text`) | Medium | **Fixed** — fallback to `answer()` |
| 9 | UX | Non-photo input during add-product photo step silently ignored | Low | **Fixed** — validation message |
| 10 | Admin panel | No web UI for catalog management | Medium | **Fixed** — Vite admin + FastAPI |
| 11 | DevOps | Docker Compose had bot only, no DB | High | **Fixed** — postgres + bot + api + frontend |
| 12 | Deploy | Polling only, no webhook mode | Medium | **Fixed** — `BOT_MODE=webhook` in main.py |
| 13 | Callback data | Long model names in payment callbacks (>64 bytes) | Medium | **Fixed** — product ID in buy/pay callbacks |

## Phase 4: Implemented Fixes

All items above were addressed in code during phases 1–2 and this pass.

## Phase 8: Verification Checklist

- [x] `docker compose up --build` — all 4 services healthy
- [x] PostgreSQL tables created on startup (`init_db`)
- [x] Admin API `GET /health`, `GET /api/stats` with API key
- [ ] Bot `/start`, assortment, cart, checkout with payment (requires valid `BOT_TOKEN`)
- [ ] Admin `/add`, `/edit`, `/del_from_db`, `/del_category` (requires valid `BOT_TOKEN`)
- [x] Frontend dashboard at http://localhost:13000
- [ ] Webhook mode with HTTPS reverse proxy (production)

## Manual Test Commands

```bash
# Start stack
cp .env.example .env   # fill BOT_TOKEN, ADMIN_IDS, secrets
docker compose up --build -d

# API health
curl http://localhost:8000/health

# API stats (replace key)
curl -H "X-API-Key: change-me-in-production" http://localhost:8000/api/stats
```

## Online payment (YooKassa) — manual checklist

Prereq: `YOOKASSA_SHOP_ID`/`YOOKASSA_SECRET_KEY` set (test shop), `PAYMENT_PAGE_URL`
= public HTTPS host, `PAYMENT_LINK_SECRET` set, `payment-page` service running.

- [ ] **Cash regression** — checkout → "Наличные при получении": order created,
      manager notified immediately, customer sees "Заказ оформлен" (unchanged).
- [ ] **Online disabled** — with empty `YOOKASSA_SHOP_ID`, checkout shows ONLY
      cash; card/SBP buttons are hidden.
- [ ] **Card/SBP happy path** — choose card → bot sends "Оплатить" WebApp button →
      opens `/pay/{order_id}` → "Перейти к оплате" → YooKassa form → pay (test card)
      → bot messages customer "Оплата получена" and managers get "Оплачен заказ";
      order status becomes `confirmed`, payment `succeeded`.
- [ ] **Expired link** — open `/pay/{order_id}?token=` after `PAYMENT_LINK_MAX_AGE`
      → "Ссылка недействительна", no order data shown.
- [ ] **Webhook idempotency** — re-deliver the same YooKassa event → second call
      returns `{"status":"duplicate"}`, no duplicate notification.
- [ ] **Amount tamper** — a forged webhook body cannot mark an order paid (status
      is taken from the YooKassa re-fetch, not the body).

## Deployment Notes

Recommended hosting: **VPS (Hetzner/DigitalOcean)** or **Railway** with Docker Compose.

1. Point domain A-record to server IP
2. Set `BOT_MODE=webhook`, `WEBHOOK_HOST=https://your-domain.com`
3. Put nginx/Caddy in front for HTTPS on port 443 → bot:8080
4. Run `scripts/deploy.sh`

Telegram webhook requires valid HTTPS certificate.
