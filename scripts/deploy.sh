#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# Polsia Fork — Fly.io 一键部署脚本
# ═══════════════════════════════════════════════════════════════════════════════

echo "==> Checking flyctl..."
if ! command -v flyctl &>/dev/null && ! command -v fly &>/dev/null; then
  echo "Installing flyctl..."
  curl -fsSL https://fly.io/install.sh | sh
  export FLYCTL_INSTALL="$HOME/.fly"
  export PATH="$FLYCTL_INSTALL/bin:$PATH"
fi
FLY="$(command -v flyctl || command -v fly || echo "$HOME/.fly/bin/flyctl")"

echo "==> Logging into Fly.io (opens browser)..."
$FLY auth login

echo ""
echo "==> Creating PostgreSQL database..."
$FLY postgres create --name polsia-db --region hkg --initial-cluster-size 1 --vm-size shared-cpu-1x 2>/dev/null || \
  echo "DB may already exist, continuing..."

echo ""
echo "==> Deploying backend API..."
$FLY launch --copy-config --no-deploy --region hkg --name polsia-api 2>/dev/null || true
$FLY deploy

echo ""
echo "==> Attaching database to backend..."
$FLY postgres attach polsia-db --app polsia-api 2>/dev/null || echo "Already attached"

echo ""
echo "==> Setting backend environment variables..."
$FLY secrets set \
  LLM_API_KEY="your-deepseek-api-key" \
  API_KEY="$(openssl rand -hex 16)" \
  LLM_API_MOCK="true" \
  DEBUG="false" \
  --app polsia-api

echo ""
echo "==> Deploying frontend..."
cd frontend
$FLY launch --copy-config --no-deploy --region hkg --name polsia-frontend 2>/dev/null || true
$FLY deploy
cd ..

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "  Deployment complete!"
echo ""
echo "  Backend:  https://polsia-api.fly.dev"
echo "  Frontend: https://polsia-frontend.fly.dev"
echo "  Health:   https://polsia-api.fly.dev/api/v1/health"
echo ""
echo "  Set LLM_API_KEY:"
echo "    fly secrets set LLM_API_KEY=sk-your-key-here --app polsia-api"
echo ""
echo "  Set API_KEY (for frontend):"
echo "    fly secrets set API_KEY=your-custom-key --app polsia-api"
echo "═══════════════════════════════════════════════════════════════════════════"
