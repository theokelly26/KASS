"""Provision Grafana with KASS datasource and dashboards via HTTP API."""

import json
import os
import sys
from pathlib import Path

import httpx

GRAFANA_URL = "http://localhost:3000"
GRAFANA_AUTH = ("admin", os.environ.get("GRAFANA_PASSWORD", "admin"))
DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "grafana" / "dashboards"


def create_datasource(client: httpx.Client) -> None:
    """Create the TimescaleDB/PostgreSQL datasource."""
    # Check if datasource already exists
    resp = client.get(f"{GRAFANA_URL}/api/datasources/name/KASS-TimescaleDB")
    if resp.status_code == 200:
        print("  Datasource 'KASS-TimescaleDB' already exists")
        return

    payload = {
        "name": "KASS-TimescaleDB",
        "uid": "kass-tsdb",
        "type": "grafana-postgresql-datasource",
        "url": "localhost:5432",
        "database": "kalshi_alpha",
        "user": "theokelly",
        "secureJsonData": {"password": ""},
        "jsonData": {
            "sslmode": "disable",
            "maxOpenConns": 5,
            "maxIdleConns": 2,
            "connMaxLifetime": 14400,
            "postgresVersion": 1700,
            "timescaledb": True,
        },
        "access": "proxy",
        "isDefault": True,
    }

    resp = client.post(f"{GRAFANA_URL}/api/datasources", json=payload)
    if resp.status_code in (200, 409):
        print("  Datasource created successfully")
    else:
        print(f"  Warning: datasource creation returned {resp.status_code}: {resp.text}")


def import_dashboards(client: httpx.Client) -> None:
    """Import all dashboard JSON files."""
    if not DASHBOARD_DIR.exists():
        print(f"  Dashboard directory not found: {DASHBOARD_DIR}")
        return

    for json_file in sorted(DASHBOARD_DIR.glob("*.json")):
        try:
            dashboard = json.loads(json_file.read_text())

            # Wrap in import payload
            payload = {
                "dashboard": dashboard,
                "overwrite": True,
                "folderId": 0,
            }

            # Remove id to create new
            if "id" in payload["dashboard"]:
                payload["dashboard"]["id"] = None

            resp = client.post(f"{GRAFANA_URL}/api/dashboards/db", json=payload)
            if resp.status_code == 200:
                result = resp.json()
                print(f"  Imported: {json_file.name} -> {result.get('url', '')}")
            else:
                print(f"  Warning: {json_file.name} returned {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"  Error importing {json_file.name}: {e}")


def main() -> None:
    print("Provisioning Grafana...")

    client = httpx.Client(auth=GRAFANA_AUTH, timeout=30)

    try:
        # Test connection
        resp = client.get(f"{GRAFANA_URL}/api/health")
        if resp.status_code != 200:
            print(f"Error: Grafana not responding at {GRAFANA_URL}")
            sys.exit(1)

        print("1. Creating datasource...")
        create_datasource(client)

        print("2. Importing dashboards...")
        import_dashboards(client)

        print("Done! Open http://localhost:3000 to view dashboards.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
