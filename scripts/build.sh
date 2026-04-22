#!/bin/bash

set -e

echo "Building AVFramework..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Building backend..."
cd "$PROJECT_DIR/backend"
mkdir -p build
cd build
cmake ..
make -j$(nproc)

echo "Backend built successfully!"

echo "Building frontend..."
cd "$PROJECT_DIR/frontend"
npm install
npm run build

echo "Frontend built successfully!"

echo "AVFramework build complete!"
