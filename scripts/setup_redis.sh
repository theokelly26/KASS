#!/bin/bash
set -e

echo "=== Redis Configuration ==="

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "Redis is not running. Starting Redis..."
    brew services start redis 2>/dev/null || redis-server --daemonize yes
fi

echo "Redis is running: $(redis-cli ping)"

# Set max memory policy (evict least recently used keys when memory limit reached)
redis-cli CONFIG SET maxmemory-policy allkeys-lru > /dev/null
redis-cli CONFIG SET maxmemory 512mb > /dev/null

echo "Redis configured: maxmemory=512mb, policy=allkeys-lru"
echo "=== Redis setup complete ==="
