#!/usr/bin/env bash
# Deploy StoreDima bot stack to a VPS with Docker Compose + webhook mode.
set -euo pipefail

if [[ ! -f .env ]]; then
  echo "Create .env from .env.example first"
  exit 1
fi

echo "==> Pulling latest changes..."
git pull --ff-only || true

echo "==> Ensuring shared Docker network exists..."
docker network create gorba_net 2>/dev/null || true

echo "==> Building and starting containers (postgres + bot)..."
docker compose -f docker-compose.yml down
docker compose -f docker-compose.yml up -d --build

echo "==> Waiting for PostgreSQL..."
sleep 8

echo "==> Building and starting containers (api + payment-page)..."
docker compose -f docker-compose.web.yml down
docker compose -f docker-compose.web.yml up -d --build

echo "==> Deployment complete."
echo "Bot webhook URL should be: \${WEBHOOK_HOST}\${WEBHOOK_PATH}"
echo "Admin API: http://<server-ip>:18000/health"
echo "Payment page: http://<server-ip>:18001/health"
echo "Admin panel is deployed separately from the ../Gorba_admin_panel repo."

docker compose -f docker-compose.yml -f docker-compose.web.yml ps
