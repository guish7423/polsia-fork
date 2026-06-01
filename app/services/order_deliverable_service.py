"""Order deliverable service — generates actual deliverable artifacts for completed orders."""

import json
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_order import ExternalOrder


# ── Deliverable template library ──────────────────────────────────────────

DOCKERFILE_FASTAPI = """FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

DOCKERFILE_NEXTJS = """FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
"""

DOCKER_COMPOSE_TEMPLATE = """version: "3.8"
services:
  app:
    build: .
    ports:
      - "{port}:{port}"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{port}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
"""

NGINX_TEMPLATE = """server {{
    listen 80;
    server_name {domain};
    return 301 https://$server_name$request_uri;
}}

server {{
    listen 443 ssl;
    server_name {domain};

    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;

    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    location /health {{
        proxy_pass http://127.0.0.1:{port}/health;
    }}
}}
"""

GITHUB_ACTIONS_DEPLOY = """name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build and Deploy
        run: |
          docker compose build
          docker compose up -d
"""

PROMETHEUS_CONFIG = """global:
  scrape_interval: 15s
scrape_configs:
  - job_name: 'app'
    static_configs:
      - targets: ['localhost:{port}']
"""

BACKUP_SCRIPT = """#!/bin/bash
# Automated backup script
BACKUP_DIR="/var/backups/{project}"
mkdir -p "$BACKUP_DIR"
DATE=$(date +%Y%m%d-%H%M%S)
tar -czf "$BACKUP_DIR/{project}-$DATE.tar.gz" /app/data
find "$BACKUP_DIR" -name "{project}-*.tar.gz" -mtime +30 -delete
echo "Backup complete: {project}-$DATE.tar.gz"
"""

DEPLOY_README = """# {project} — Deployment Package

## Quick Start
```bash
cp .env.example .env
# Edit .env with your configuration
docker compose up -d
```

## Services
- App: http://localhost:{port}
- Health: http://localhost:{port}/health

## Maintenance
- View logs: `docker compose logs -f`
- Restart: `docker compose restart`
- Backup: `bash backup.sh`

## Support
Contact: support@crosswave.app
"""

K8S_DEPLOYMENT = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: {project}
  labels:
    app: {project}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {project}
  template:
    metadata:
      labels:
        app: {project}
    spec:
      containers:
      - name: app
        image: {project}:latest
        ports:
        - containerPort: {port}
        envFrom:
        - configMapRef:
            name: {project}-config
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
"""

K8S_SERVICE = """apiVersion: v1
kind: Service
metadata:
  name: {project}-service
spec:
  selector:
    app: {project}
  ports:
  - protocol: TCP
    port: 80
    targetPort: {port}
  type: ClusterIP
"""

K8S_HPA = """apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {project}-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {project}
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
"""


def _detect_tech_stack(description: str, requirements: str) -> dict:
    """Auto-detect tech stack from order description."""
    text = f"{description or ''} {requirements or ''}".lower()
    stack = {
        "has_fastapi": any(k in text for k in ["fastapi", "python api", "uvicorn"]),
        "has_nextjs": any(k in text for k in ["nextjs", "next.js", "react frontend"]),
        "has_react": any(k in text for k in ["react", "frontend", "ui"]) and "next" not in text,
        "has_postgres": any(k in text for k in ["postgres", "postgresql", "database"]),
        "has_redis": "redis" in text,
        "has_k8s": any(k in text for k in ["kubernetes", "k8s", "k3s"]),
        "has_docker": any(k in text for k in ["docker", "container"]),
        "has_domain": any(k in text for k in ["domain", "ssl", "https"]),
    }
    return stack


def generate_standard_deliverables(
    order_title: str,
    description: str = "",
    requirements: str = "",
    tier: str = "basic",
    order_id: int = 0,
) -> list[dict]:
    """Generate the set of deliverable artifacts for an order.
    Returns list of {name, type, content, description} dicts."""
    stack = _detect_tech_stack(description, requirements)
    project_slug = order_title.lower().replace(" ", "-").replace("--", "-")[:40] or f"project-{order_id}"
    port = 8000 if stack.get("has_fastapi") else 3000
    deliverables = []

    # Basic deliverables — always present
    dockerfile = DOCKERFILE_FASTAPI if stack.get("has_fastapi") else DOCKERFILE_NEXTJS
    deliverables.append({
        "name": "Dockerfile",
        "type": "text",
        "content": dockerfile,
        "description": "Production-ready Docker image definition",
    })

    compose_port = 8000 if stack.get("has_fastapi") else 3000
    deliverables.append({
        "name": "docker-compose.yml",
        "type": "text",
        "content": DOCKER_COMPOSE_TEMPLATE.format(port=compose_port),
        "description": "Multi-service orchestration with health checks",
    })

    if stack.get("has_domain"):
        deliverables.append({
            "name": "nginx.conf",
            "type": "text",
            "content": NGINX_TEMPLATE.format(
                domain=f"{project_slug}.crosswave.app",
                port=compose_port,
            ),
            "description": "Nginx reverse proxy with SSL termination",
        })

    deliverables.append({
        "name": "README.md",
        "type": "markdown",
        "content": DEPLOY_README.format(project=project_slug, port=compose_port),
        "description": "Deployment package documentation",
    })

    if tier in ("standard", "enterprise"):
        deliverables.append({
            "name": ".github/workflows/deploy.yml",
            "type": "text",
            "content": GITHUB_ACTIONS_DEPLOY,
            "description": "CI/CD pipeline (GitHub Actions)",
        })
        deliverables.append({
            "name": "backup.sh",
            "type": "text",
            "content": BACKUP_SCRIPT.format(project=project_slug),
            "description": "Automated backup script with 30-day rotation",
        })

    if tier == "standard":
        deliverables.append({
            "name": "prometheus.yml",
            "type": "text",
            "content": PROMETHEUS_CONFIG.format(port=9090),
            "description": "Prometheus monitoring configuration",
        })

    if tier == "enterprise":
        for manifest_name, content in [
            ("k8s-deployment.yaml", K8S_DEPLOYMENT),
            ("k8s-service.yaml", K8S_SERVICE),
            ("k8s-hpa.yaml", K8S_HPA),
        ]:
            deliverables.append({
                "name": manifest_name,
                "type": "text",
                "content": content.format(project=project_slug, port=compose_port),
                "description": f"Kubernetes manifest: {manifest_name}",
            })

    return deliverables


async def get_deliverables(db: AsyncSession, order_id: int) -> list[dict]:
    """Retrieve deliverables for an order."""
    result = await db.execute(
        select(ExternalOrder.deliverables, ExternalOrder.delivery_notes)
        .where(ExternalOrder.id == order_id)
    )
    row = result.first()
    if not row:
        return []
    return row[0] or []


async def save_deliverables(
    db: AsyncSession,
    order_id: int,
    deliverables: list[dict],
    delivery_notes: str = "",
) -> dict:
    """Save deliverables to an order."""
    await db.execute(
        update(ExternalOrder)
        .where(ExternalOrder.id == order_id)
        .values(
            deliverables=deliverables,
            delivery_notes=delivery_notes,
            updated_at=datetime.now(timezone.utc),
        )
    )
    await db.flush()
    return {"order_id": order_id, "deliverables_count": len(deliverables)}
