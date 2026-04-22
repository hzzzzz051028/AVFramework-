#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

case "$1" in
    backend)
        echo "Starting backend server..."
        cd "$PROJECT_DIR/backend/build"
        ./avframework
        ;;
    frontend)
        echo "Starting frontend server..."
        cd "$PROJECT_DIR/frontend"
        npm run dev
        ;;
    docker)
        echo "Starting with Docker..."
        cd "$PROJECT_DIR"
        docker-compose up -d
        echo "Services started!"
        echo "Frontend: http://localhost"
        echo "Backend API: http://localhost:8080"
        echo "WebSocket: ws://localhost:8081"
        ;;
    stop)
        echo "Stopping Docker services..."
        cd "$PROJECT_DIR"
        docker-compose down
        ;;
    *)
        echo "Usage: $0 {backend|frontend|docker|stop}"
        exit 1
        ;;
esac
