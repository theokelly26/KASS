#!/bin/bash
set -e

echo "=== KASS Grafana Setup ==="

# Install Grafana if not present
if ! brew list grafana &>/dev/null; then
    echo "Installing Grafana..."
    brew install grafana
else
    echo "Grafana already installed"
fi

# Start Grafana
echo "Starting Grafana..."
brew services start grafana

# Wait for Grafana to be ready
echo "Waiting for Grafana to start..."
for i in $(seq 1 30); do
    if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
        echo "Grafana is ready!"
        break
    fi
    sleep 1
done

echo ""
echo "Grafana running at http://localhost:3000"
echo "Default login: admin / admin"
echo ""
echo "Provisioning datasource and dashboards..."

# Run provisioning script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python "$SCRIPT_DIR/provision_grafana.py"

echo ""
echo "=== Setup Complete ==="
echo "Open http://localhost:3000 in your browser"
