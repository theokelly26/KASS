#!/bin/bash
set -e

echo "=== Mac Mini Full Setup for KASS ==="

# Install Homebrew if not present
if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install dependencies
echo "Installing system dependencies..."
brew install postgresql@16 redis python@3.11 node 2>/dev/null || true

# Install TimescaleDB
echo "Installing TimescaleDB..."
brew tap timescale/tap 2>/dev/null || true
brew install timescaledb 2>/dev/null || true

# Run timescaledb-tune to configure PostgreSQL for TimescaleDB
echo "Configuring TimescaleDB..."
timescaledb-tune --quiet --yes 2>/dev/null || echo "timescaledb-tune not available, configure manually"

# Start services
echo "Starting services..."
brew services start postgresql@16
brew services start redis

# Wait for Postgres to be ready
echo "Waiting for PostgreSQL..."
for i in {1..30}; do
    pg_isready -q && break
    sleep 1
done

# Create database user
echo "Creating database user..."
createuser kalshi 2>/dev/null || echo "User kalshi already exists"
psql postgres -c "ALTER USER kalshi WITH PASSWORD 'your_password';" 2>/dev/null || true

# Install PM2 for process management
echo "Installing PM2..."
npm install -g pm2 2>/dev/null || true

# Setup PM2 to start on boot
pm2 startup 2>/dev/null || true

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -e ".[dev]"

# Run database setup
echo "Setting up database..."
bash scripts/setup_db.sh

# Run Redis setup
echo "Setting up Redis..."
bash scripts/setup_redis.sh

echo "=== Mac Mini setup complete ==="
echo "Next steps:"
echo "  1. Copy .env.example to .env and fill in your Kalshi API credentials"
echo "  2. Place your Kalshi private key at keys/kalshi_private_key.pem"
echo "  3. Start services: pm2 start processes/ecosystem.config.js"
