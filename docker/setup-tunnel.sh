#!/usr/bin/env bash
# Optional helper: Cloudflare Tunnel for exposing the local API.
#
# Required:
#   TUNNEL_HOSTNAME=api.example.com
# Optional:
#   TUNNEL_NAME=realballondor
#   API_ORIGIN=http://127.0.0.1:8800
#   CLOUDFLARED_HOME=$HOME/.cloudflared
#   CONFIG_DIR=$HOME/docker/realballondor-tunnel
set -euo pipefail

TUNNEL_NAME="${TUNNEL_NAME:-realballondor}"
TUNNEL_HOSTNAME="${TUNNEL_HOSTNAME:?Set TUNNEL_HOSTNAME (e.g. api.example.com)}"
API_ORIGIN="${API_ORIGIN:-http://127.0.0.1:8800}"
CLOUDFLARED_HOME="${CLOUDFLARED_HOME:-$HOME/.cloudflared}"
CONFIG_DIR="${CONFIG_DIR:-$HOME/docker/realballondor-tunnel}"

if ! cloudflared tunnel list 2>/dev/null | grep -q "${TUNNEL_NAME}"; then
  cloudflared tunnel create "${TUNNEL_NAME}"
fi

TUNNEL_ID=$(cloudflared tunnel list | awk -v name="${TUNNEL_NAME}" '$0 ~ name {print $1; exit}')
echo "TUNNEL_ID=$TUNNEL_ID"

mkdir -p "${CONFIG_DIR}"
cat > "${CONFIG_DIR}/config.yml" <<CFG
tunnel: ${TUNNEL_ID}
credentials-file: ${CLOUDFLARED_HOME}/${TUNNEL_ID}.json

ingress:
  - hostname: ${TUNNEL_HOSTNAME}
    service: ${API_ORIGIN}
  - service: http_status:404
CFG

cloudflared tunnel route dns --overwrite-dns "${TUNNEL_NAME}" "${TUNNEL_HOSTNAME}"

pm2 delete "${TUNNEL_NAME}-tunnel" 2>/dev/null || true
pm2 start /usr/local/bin/cloudflared --name "${TUNNEL_NAME}-tunnel" -- \
  tunnel --config "${CONFIG_DIR}/config.yml" run
pm2 save
