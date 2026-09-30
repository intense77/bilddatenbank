#!/usr/bin/env bash
set -e

# Erstelle Storage-Verzeichnis falls nicht vorhanden
mkdir -p ./qdrant_storage

if docker compose version >/dev/null 2>&1; then
    echo "Starte Qdrant via Docker Compose..."
    docker compose up -d
elif which docker-compose >/dev/null 2>&1; then
    echo "Starte Qdrant via docker-compose..."
    docker-compose up -d
else
    echo "Starte Qdrant via Docker..."
    if docker ps -a --format '{{.Names}}' | grep -Eq "^archive_qdrant\$"; then
        docker start archive_qdrant
    else
        docker run -d \
            --name archive_qdrant \
            --restart unless-stopped \
            -p 6333:6333 \
            -p 6334:6334 \
            -v "$(pwd)/qdrant_storage:/qdrant/storage" \
            -e QDRANT__SERVICE__ENABLE_STATIC_CONTENT=1 \
            qdrant/qdrant:latest
    fi
fi

echo "Qdrant läuft. Dashboard: http://localhost:6333/dashboard"
