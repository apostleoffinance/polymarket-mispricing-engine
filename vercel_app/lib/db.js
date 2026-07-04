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
