#!/usr/bin/env bash
# Inicia o servidor localmente para desenvolvimento.
# Uso:
#   ./start.sh
#   CLIENT_ID=meu-id CLIENT_SECRET=meu-segredo ./start.sh

export CLIENT_ID="${CLIENT_ID:-pandape-client-id}"
export CLIENT_SECRET="${CLIENT_SECRET:-pandape-client-secret}"
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-local-dev-jwt-secret-key-troque-em-producao}"
export TOKEN_EXPIRES_IN="${TOKEN_EXPIRES_IN:-3600}"
PORT="${PORT:-5000}"

echo ""
echo "Iniciando Pandape Webhook Receiver na porta $PORT ..."
python app.py
