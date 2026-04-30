#!/usr/bin/env bash
set -euo pipefail

echo "Decay Clocks Production Deployment"
echo "=================================="
read -p "Domain (e.g., decay.example.com): " DOMAIN
read -p "Admin email (for Let's Encrypt): " ADMIN_EMAIL
read -p "Postgres password (default: dcpass): " PG_PASS
PG_PASS=${PG_PASS:-dcpass}
read -p "Grafana admin password (default: admin): " GF_PASS
GF_PASS=${GF_PASS:-admin}

export DOMAIN ADMIN_EMAIL POSTGRES_PASSWORD=$PG_PASS GRAFANA_PASSWORD=$GF_PASS

echo "Starting services..."
docker compose -f docker/compose/docker-compose.prod.yml up -d

echo "Waiting for API to be healthy..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "API is live!"
        break
    fi
    sleep 2
done

echo "Running database migrations..."
docker compose -f docker/compose/docker-compose.prod.yml exec -T api alembic upgrade head

echo ""
echo "Deployment complete!"
echo "API: https://$DOMAIN"
echo "Grafana: https://$DOMAIN/grafana (login: admin / $GF_PASS)"
echo "Prometheus: http://localhost:9090 (internal only)"
