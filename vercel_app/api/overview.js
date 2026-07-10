import {
  fetchBacktestByDomain,
  fetchCandidateStats,
  fetchLiveByDomain,
  normalizeDomain,
  sendError,
  sql,
  toNumber,
} from "../lib/db.js";

export default async function handler(req, res) {
  try {
    const db = sql();
    const domain = normalizeDomain(req.query.domain);

    const [markets] = domain
      ? await db`
          SELECT COUNT(*)::int AS count
          FROM markets
          WHERE domain = ${domain}
        `
      : await db`
          SELECT COUNT(*)::int AS count
          FROM markets
          WHERE domain IS NOT NULL
        `;

    const [snapshots] = domain
      ? await db`
          SELECT COUNT(*)::int AS count
          FROM probability_history ph
          JOIN markets m ON m.id = ph.market_id
          WHERE m.domain = ${domain}
        `
      : await db`
          SELECT COUNT(*)::int AS count
          FROM probability_history
        `;

    const [relationships] = domain
      ? await db`
          SELECT COUNT(*)::int AS count
          FROM market_relationships r
          JOIN markets m ON m.id = r.parent_market_id
          WHERE r.parent_market_id IS NOT NULL
            AND m.domain = ${domain}
        `
      : await db`
          SELECT COUNT(*)::int AS count
          FROM market_relationships
          WHERE parent_market_id IS NOT NULL
        `;

    const [signals] = domain
      ? await db`
          SELECT COUNT(*)::int AS count
          FROM arbitrage_signals s
          LEFT JOIN markets parent_m ON parent_m.id = s.parent_market
          WHERE s.parent_market ~ '^[0-9]+$'
            AND s.related_market ~ '^[0-9]+$'
            AND parent_m.domain = ${domain}
        `
      : await db`
          SELECT COUNT(*)::int AS count
          FROM arbitrage_signals s
          WHERE s.parent_market ~ '^[0-9]+$'
            AND s.related_market ~ '^[0-9]+$'
        `;

    const [depth] = domain
      ? await db`
          SELECT
            COUNT(*) FILTER (WHERE n >= 100)::int AS markets_100,
            ROUND(AVG(n), 1) AS avg_snapshots,
            MAX(n)::int AS max_snapshots
          FROM (
            SELECT ph.market_id, COUNT(*) AS n
            FROM probability_history ph
            JOIN markets m ON m.id = ph.market_id
            WHERE m.domain = ${domain}
            GROUP BY ph.market_id
          ) t
        `
      : await db`
          SELECT
            COUNT(*) FILTER (WHERE n >= 100)::int AS markets_100,
            ROUND(AVG(n), 1) AS avg_snapshots,
            MAX(n)::int AS max_snapshots
          FROM (
            SELECT market_id, COUNT(*) AS n
            FROM probability_history
            GROUP BY market_id
          ) t
        `;

    let edgeDynamics = {
      with_lag: 0,
      mean_abs_lag_minutes: null,
      mean_stability: null,
    };
    try {
      const [dyn] = domain
        ? await db`
            SELECT
              COUNT(*) FILTER (WHERE COALESCE(lag_minutes, 0) <> 0)::int AS with_lag,
              AVG(ABS(lag_minutes)) FILTER (WHERE lag_minutes IS NOT NULL) AS mean_abs_lag,
              AVG(stability_score) FILTER (WHERE stability_score IS NOT NULL) AS mean_stability
            FROM market_relationships r
            JOIN markets m ON m.id = r.parent_market_id
            WHERE r.parent_market_id IS NOT NULL
              AND m.domain = ${domain}
          `
        : await db`
            SELECT
              COUNT(*) FILTER (WHERE COALESCE(lag_minutes, 0) <> 0)::int AS with_lag,
              AVG(ABS(lag_minutes)) FILTER (WHERE lag_minutes IS NOT NULL) AS mean_abs_lag,
              AVG(stability_score) FILTER (WHERE stability_score IS NOT NULL) AS mean_stability
            FROM market_relationships
            WHERE parent_market_id IS NOT NULL
          `;
      edgeDynamics = {
        with_lag: toNumber(dyn?.with_lag),
        mean_abs_lag_minutes:
          dyn?.mean_abs_lag === null || dyn?.mean_abs_lag === undefined
            ? null
            : Number(dyn.mean_abs_lag),
        mean_stability:
          dyn?.mean_stability === null || dyn?.mean_stability === undefined
            ? null
            : Number(dyn.mean_stability),
      };
    } catch (error) {
      console.warn("edge dynamics unavailable:", error.message || error);
    }

    const domainRows = await db`
      SELECT domain, COUNT(*)::int AS count
      FROM markets
      WHERE domain IS NOT NULL
      GROUP BY domain
      ORDER BY domain
    `;

    const liveByDomain = await fetchLiveByDomain(db);
    const { latestRunId, rows: backtestByDomain } = await fetchBacktestByDomain(db);
    const candidates = await fetchCandidateStats(db);

    res.status(200).json({
      domain,
      markets: toNumber(markets.count),
      snapshots: toNumber(snapshots.count),
      relationships: toNumber(relationships.count),
      signals: toNumber(signals.count),
      markets_with_100_plus_snapshots: toNumber(depth?.markets_100),
      avg_snapshots_per_market: toNumber(depth?.avg_snapshots),
      max_snapshots_per_market: toNumber(depth?.max_snapshots),
      domains: Object.fromEntries(domainRows.map((row) => [row.domain, toNumber(row.count)])),
      live_by_domain: liveByDomain,
      backtest_by_domain: backtestByDomain,
      latest_backtest_run_id: latestRunId,
      candidates,
      edge_dynamics: edgeDynamics,
    });
  } catch (error) {
    sendError(res, error);
  }
}
