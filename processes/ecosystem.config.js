module.exports = {
  apps: [
    {
      name: "kass-ws-manager",
      script: "python",
      args: "-m src.ingestion.ws_client",
      cwd: __dirname + "/..",
      autorestart: true,
      max_restarts: 50,
      restart_delay: 5000,
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "kass-discovery",
      script: "python",
      args: "-m src.discovery.market_scanner",
      cwd: __dirname + "/..",
      autorestart: true,
      cron_restart: "0 */6 * * *",
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "kass-writer-trades",
      script: "python",
      args: "-m src.persistence.writers.trade_writer",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "kass-writer-ticker",
      script: "python",
      args: "-m src.persistence.writers.ticker_writer",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "kass-writer-orderbook",
      script: "python",
      args: "-m src.persistence.writers.orderbook_writer",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "kass-writer-lifecycle",
      script: "python",
      args: "-m src.persistence.writers.lifecycle_writer",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "kass-health-monitor",
      script: "python",
      args: "-m src.monitoring.health",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
  ],
};
