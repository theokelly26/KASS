#!/bin/bash
set -e

echo "=== Kalshi Alpha Database Setup ==="

# Create database if it doesn't exist
createdb kalshi_alpha 2>/dev/null && echo "Created database kalshi_alpha" || echo "Database kalshi_alpha already exists"

# Run all migrations in order
for f in sql/*.sql; do
    echo "Running $f..."
    psql kalshi_alpha -f "$f"
done

echo "=== Database setup complete ==="
