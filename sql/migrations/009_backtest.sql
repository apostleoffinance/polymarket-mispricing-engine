-- Migration 009: backtesting runs and per-signal outcomes
-- psql -h localhost -p 5433 -d polymarket -f sql/migrations/009_backtest.sql

CREATE TABLE IF NOT EXISTS backtest_runs (
    id                    SERIAL PRIMARY KEY,
    started_at            TIMESTAMP DEFAULT NOW(),
    config_json           TEXT,
    total_evaluations     INTEGER,
    actionable_signals    INTEGER,
    directional_wins      INTEGER,
    edge_closed_count     INTEGER,
    directional_win_rate  NUMERIC(20, 10),
    edge_closed_rate      NUMERIC(20, 10),
    mean_edge_at_signal   NUMERIC(20, 10),
    mean_edge_after       NUMERIC(20, 10),
    mean_minutes_to_reprice NUMERIC(20, 10)
);

CREATE TABLE IF NOT EXISTS backtest_results (
    id                    SERIAL PRIMARY KEY,
    run_id                INTEGER REFERENCES backtest_runs(id),
    parent_market_id      TEXT NOT NULL,
    child_market_id       TEXT NOT NULL,
    domain                TEXT,
    signal_time           TIMESTAMP NOT NULL,
    horizon_minutes       INTEGER,
    signal                TEXT NOT NULL,
    expected_probability  NUMERIC(20, 10),
    observed_at_t         NUMERIC(20, 10),
    observed_at_t_plus    NUMERIC(20, 10),
    edge_at_t             NUMERIC(20, 10),
    edge_at_t_plus        NUMERIC(20, 10),
    confidence            NUMERIC(20, 10),
    directional_win       BOOLEAN,
    edge_closed           BOOLEAN,
    minutes_to_reprice    NUMERIC(20, 10),
    simple_pnl            NUMERIC(20, 10)
);

CREATE INDEX IF NOT EXISTS backtest_results_run_id_idx ON backtest_results (run_id);
CREATE INDEX IF NOT EXISTS backtest_results_signal_time_idx ON backtest_results (signal_time);
