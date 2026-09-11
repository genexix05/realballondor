#!/usr/bin/env bash
# Create/route Cloudflare Tunnel for apiballondoro.alexmn.dev and start it with pm2.
set -euo pipefail

if ! cloudflared tunnel list 2>/dev/null | grep -q realballondor; then
  cloudflared tunnel create realballondor
fi

TUNNEL_ID=$(cloudflared tunnel list | awk '/realballondor/ {print $1; exit}')
echo "TUNNEL_ID=$TUNNEL_ID"

mkdir -p ~/docker/realballondor-tunnel
cat > ~/docker/realballondor-tunnel/config.yml <<CFG
tunnel: ${TUNNEL_ID}
credentials-file: /home/genexix05/.cloudflared/${TUNNEL_ID}.json

ingress:
  - hostname: apiballondoro.alexmn.dev
    service: http://127.0.0.1:8800
  - service: http_status:404
CFG

cloudflared tunnel route dns --overwrite-dns realballondor apiballondoro.alexmn.dev

pm2 delete realballondor-tunnel 2>/dev/null || true
pm2 start /usr/local/bin/cloudflared --name realballondor-tunnel -- \
  tunnel --config /home/genexix05/docker/realballondor-tunnel/config.yml run
pm2 save
