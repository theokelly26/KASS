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
    // Phase 2: Signal Processors
    {
      name: "kass-signal-flow",
      script: "python",
      args: "-m src.signals.flow.toxicity",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "kass-signal-oi",
      script: "python",
      args: "-m src.signals.flow.oi_divergence",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "kass-signal-regime",
      script: "python",
      args: "-m src.signals.microstructure.regime",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "kass-signal-crossmarket",
      script: "python",
      args: "-m src.signals.cross_market.propagation",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "kass-signal-lifecycle",
      script: "python",
      args: "-m src.signals.cross_market.lifecycle_alpha",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "kass-aggregator",
      script: "python",
      args: "-m src.signals.aggregator.aggregator",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
    // Phase 2.5: Observability Layer
    {
      name: "kass-writer-signals",
      script: "python",
      args: "-m src.persistence.writers.signal_writer",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "kass-price-snapshots",
      script: "python",
      args: "-m src.monitoring.price_snapshots",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "kass-view-refresher",
      script: "python",
      args: "-m src.monitoring.view_refresher",
      cwd: __dirname + "/..",
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
  ],
};
