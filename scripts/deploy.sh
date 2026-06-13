#!/usr/bin/env bash
# Deploy StoreDima bot stack to a VPS with Docker Compose + webhook mode.
set -euo pipefail

if [[ ! -f .env ]]; then
  echo "Create .env from .env.example first"
  exit 1
fi

echo "==> Pulling latest changes..."
git pull --ff-only || true

echo "==> Building and starting containers..."
docker compose down
docker compose up -d --build

echo "==> Waiting for PostgreSQL..."
sleep 8

echo "==> Deployment complete."
echo "Bot webhook URL should be: \${WEBHOOK_HOST}\${WEBHOOK_PATH}"
echo "Admin panel: http://<server-ip>:3000"
echo "Admin API: http://<server-ip>:8000/health"

docker compose ps
