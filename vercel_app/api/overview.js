import {
  fetchCandidateStats,
  normalizeDomain,
  sendError,
  sql,
  toNumber,
} from "../lib/db.js";

export default async function handler(req, res) {
  try {
    const db = sql();
    const domain = normalizeDomain(req.query.domain);

    // Keep this endpoint cheap — full-table snapshot scans were timing out on Vercel.
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

    let snapshots = 0;
    try {
      const [snap] = await db`
        SELECT reltuples::bigint AS estimate
        FROM pg_class
        WHERE relname = 'probability_history'
      `;
      snapshots = toNumber(snap?.estimate);
    } catch {
      snapshots = 0;
    }

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

    const candidates = await fetchCandidateStats(db);

    res.status(200).json({
      domain,
      markets: toNumber(markets.count),
      snapshots,
      relationships: toNumber(relationships.count),
      signals: toNumber(signals.count),
      markets_with_100_plus_snapshots: 0,
      avg_snapshots_per_market: 0,
      max_snapshots_per_market: 0,
      domains: Object.fromEntries(domainRows.map((row) => [row.domain, toNumber(row.count)])),
      candidates,
      edge_dynamics: edgeDynamics,
      snapshot_count_estimated: true,
    });
  } catch (error) {
    sendError(res, error);
  }
}
