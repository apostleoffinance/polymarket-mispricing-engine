import { neon } from "@neondatabase/serverless";

export const DOMAINS = ["politics", "football", "crypto", "macro", "geopolitics"];

let client;

export function sql() {
  if (!process.env.DATABASE_URL) {
    throw new Error("DATABASE_URL environment variable is required");
  }
  if (!client) {
    client = neon(process.env.DATABASE_URL);
  }
  return client;
}

export function normalizeDomain(value) {
  const raw = Array.isArray(value) ? value[0] : value;
  if (!raw || String(raw).toLowerCase() === "all") return null;
  return String(raw);
}

export function toNumber(value) {
  if (value === null || value === undefined) return 0;
  return Number(value);
}

export function toIso(value) {
  if (!value) return null;
  if (value instanceof Date) return value.toISOString();
  return new Date(value).toISOString();
}

export function sendError(res, error) {
  console.error(error);
  res.status(500).json({
    error: "Internal Server Error",
    message: error instanceof Error ? error.message : String(error),
  });
}

export function parseReasonJson(value) {
  if (!value) return {};
  if (typeof value === "object") return value;
  try {
    return JSON.parse(String(value));
  } catch {
    return {};
  }
}

export function enrichSignalRow(row) {
  const reason = parseReasonJson(row.reason_json);
  const lagMinutes =
    row.lag_minutes != null
      ? Number(row.lag_minutes)
      : reason.lag_minutes != null
        ? Number(reason.lag_minutes)
        : null;
  const leadCorrelation =
    row.lead_correlation != null
      ? toNumber(row.lead_correlation)
      : reason.lead_correlation != null
        ? Number(reason.lead_correlation)
        : null;
  const stabilityScore =
    row.stability_score != null
      ? toNumber(row.stability_score)
      : reason.stability_score != null
        ? Number(reason.stability_score)
        : null;

  return {
    parent_id: row.parent_market,
    parent_question: row.parent_question,
    domain: row.domain,
    child_id: row.related_market,
    child_question: row.child_question,
    expected: row.expected_probability === null ? null : toNumber(row.expected_probability),
    observed: row.observed_probability === null ? null : toNumber(row.observed_probability),
    edge: row.edge === null ? null : toNumber(row.edge),
    confidence: row.confidence === null ? null : toNumber(row.confidence),
    signal: row.signal,
    created_at: toIso(row.created_at),
    explanation: reason.explanation || null,
    lag_minutes: Number.isFinite(lagMinutes) ? lagMinutes : null,
    lead_correlation: leadCorrelation,
    stability_score: stabilityScore,
    beta: reason.beta != null ? Number(reason.beta) : null,
    correlation_shrunk:
      reason.correlation_shrunk != null ? Number(reason.correlation_shrunk) : null,
    n_observations:
      reason.n_observations != null ? Number(reason.n_observations) : null,
    relationship_type: reason.relationship_type || row.relationship_type || null,
    discovery_source:
      reason.discovery_source || row.discovery_source || null,
  };
}

export async function fetchCandidateStats(db = sql()) {
  try {
    const rows = await db`
      SELECT
        status,
        COUNT(*)::int AS count
      FROM candidate_relationships
      GROUP BY status
    `;
    const byStatus = Object.fromEntries(
      rows.map((row) => [row.status, toNumber(row.count)]),
    );
    return {
      proposed: byStatus.proposed || 0,
      validated: byStatus.validated || 0,
      promoted: byStatus.promoted || 0,
      rejected: byStatus.rejected || 0,
      total: Object.values(byStatus).reduce((sum, n) => sum + n, 0),
    };
  } catch (error) {
    console.warn("candidate_relationships unavailable:", error.message || error);
    return {
      proposed: 0,
      validated: 0,
      promoted: 0,
      rejected: 0,
      total: 0,
      unavailable: true,
    };
  }
}

export async function fetchLiveByDomain(db = sql()) {
  const rows = await db`
    SELECT
      COALESCE(parent_m.domain, 'unknown') AS domain,
      COUNT(*)::int AS signal_count,
      COUNT(*) FILTER (WHERE s.signal = 'BUY')::int AS buy_count,
      COUNT(*) FILTER (WHERE s.signal = 'SELL')::int AS sell_count,
      COUNT(*) FILTER (WHERE s.signal = 'HOLD')::int AS hold_count
    FROM arbitrage_signals s
    LEFT JOIN markets parent_m ON parent_m.id = s.parent_market
    WHERE s.parent_market ~ '^[0-9]+$'
      AND s.related_market ~ '^[0-9]+$'
    GROUP BY COALESCE(parent_m.domain, 'unknown')
    ORDER BY domain
  `;

  return Object.fromEntries(
    rows.map((row) => [
      row.domain,
      {
        signals: toNumber(row.signal_count),
        buy: toNumber(row.buy_count),
        sell: toNumber(row.sell_count),
        hold: toNumber(row.hold_count),
      },
    ]),
  );
}

export async function fetchBacktestByDomain(db = sql()) {
  const [latest] = await db`
    SELECT MAX(id)::int AS id
    FROM backtest_runs
  `;

  if (!latest?.id) {
    return { latestRunId: null, rows: {} };
  }

  const rows = await db`
    SELECT
      COALESCE(domain, 'unknown') AS domain,
      COUNT(*)::int AS actionable,
      COUNT(*) FILTER (WHERE directional_win)::int AS wins,
      COUNT(*) FILTER (WHERE edge_closed)::int AS edge_closed,
      AVG(ABS(edge_at_t)) AS mean_edge_at,
      AVG(ABS(edge_at_t_plus)) AS mean_edge_after,
      AVG(minutes_to_reprice) AS mean_reprice
    FROM backtest_results
    WHERE run_id = ${latest.id}
    GROUP BY COALESCE(domain, 'unknown')
    ORDER BY domain
  `;

  return {
    latestRunId: latest.id,
    rows: Object.fromEntries(
      rows.map((row) => {
        const actionable = toNumber(row.actionable);
        const wins = toNumber(row.wins);
        const closed = toNumber(row.edge_closed);
        return [
          row.domain,
          {
            actionable_signals: actionable,
            directional_wins: wins,
            directional_win_rate: actionable ? wins / actionable : 0,
            edge_closed_count: closed,
            edge_closed_rate: actionable ? closed / actionable : 0,
            mean_edge_at_signal: toNumber(row.mean_edge_at),
            mean_edge_after: toNumber(row.mean_edge_after),
            mean_minutes_to_reprice:
              row.mean_reprice === null || row.mean_reprice === undefined
                ? null
                : Number(row.mean_reprice),
          },
        ];
      }),
    ),
  };
}
