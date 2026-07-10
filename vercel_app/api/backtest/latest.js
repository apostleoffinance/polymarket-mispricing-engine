import { normalizeDomain, sendError, sql, toIso, toNumber } from "../../lib/db.js";

function parseConfig(value) {
  if (!value) return {};
  if (typeof value === "object") return value;
  try {
    return JSON.parse(String(value));
  } catch {
    return {};
  }
}

function serializeRun(row, domain = null) {
  const config = parseConfig(row.config_json);
  const diagnostics = config.diagnostics || {};
  return {
    id: row.id,
    started_at: toIso(row.started_at),
    total_evaluations: toNumber(row.total_evaluations),
    actionable_signals: toNumber(row.actionable_signals),
    directional_wins: toNumber(row.directional_wins),
    edge_closed_count: toNumber(row.edge_closed_count),
    directional_win_rate: toNumber(row.directional_win_rate),
    edge_closed_rate: toNumber(row.edge_closed_rate),
    mean_edge_at_signal: toNumber(row.mean_edge_at_signal),
    mean_edge_after: toNumber(row.mean_edge_after),
    mean_minutes_to_reprice:
      row.mean_minutes_to_reprice === null || row.mean_minutes_to_reprice === undefined
        ? null
        : Number(row.mean_minutes_to_reprice),
    domain,
    use_lag_horizon: Boolean(config.use_lag_horizon),
    min_stability: config.min_stability ?? null,
    source_summaries: diagnostics.source_summaries || {},
    pairs_agent_sourced: toNumber(diagnostics.pairs_agent_sourced),
    agent_signals: toNumber(diagnostics.agent_signals),
    pairs_skipped_stability: toNumber(diagnostics.pairs_skipped_stability),
  };
}

export default async function handler(req, res) {
  try {
    const db = sql();
    const domain = normalizeDomain(req.query.domain);
    const [run] = await db`
      SELECT
        id,
        started_at,
        config_json,
        total_evaluations,
        actionable_signals,
        directional_wins,
        edge_closed_count,
        directional_win_rate,
        edge_closed_rate,
        mean_edge_at_signal,
        mean_edge_after,
        mean_minutes_to_reprice
      FROM backtest_runs
      ORDER BY id DESC
      LIMIT 1
    `;

    if (!run) {
      res.status(200).json(null);
      return;
    }

    const result = serializeRun(run, domain);

    if (domain) {
      const [stats] = await db`
        SELECT
          COUNT(*)::int AS actionable,
          COUNT(*) FILTER (WHERE directional_win)::int AS wins,
          COUNT(*) FILTER (WHERE edge_closed)::int AS edge_closed,
          AVG(ABS(edge_at_t)) AS mean_edge_at,
          AVG(ABS(edge_at_t_plus)) AS mean_edge_after,
          AVG(minutes_to_reprice) AS mean_reprice
        FROM backtest_results
        WHERE run_id = ${run.id}
          AND domain = ${domain}
      `;

      const actionable = toNumber(stats.actionable);
      const wins = toNumber(stats.wins);
      const closed = toNumber(stats.edge_closed);

      Object.assign(result, {
        actionable_signals: actionable,
        directional_wins: wins,
        edge_closed_count: closed,
        directional_win_rate: actionable ? wins / actionable : 0,
        edge_closed_rate: actionable ? closed / actionable : 0,
        mean_edge_at_signal: toNumber(stats.mean_edge_at),
        mean_edge_after: toNumber(stats.mean_edge_after),
        mean_minutes_to_reprice:
          stats.mean_reprice === null || stats.mean_reprice === undefined
            ? null
            : Number(stats.mean_reprice),
      });
    }

    res.status(200).json(result);
  } catch (error) {
    sendError(res, error);
  }
}
