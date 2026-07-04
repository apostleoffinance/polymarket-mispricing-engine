import {
  fetchBacktestByDomain,
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

    const domainRows = await db`
      SELECT domain, COUNT(*)::int AS count
      FROM markets
      WHERE domain IS NOT NULL
      GROUP BY domain
      ORDER BY domain
    `;

    const liveByDomain = await fetchLiveByDomain(db);
    const { latestRunId, rows: backtestByDomain } = await fetchBacktestByDomain(db);

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
    });
  } catch (error) {
    sendError(res, error);
  }
}
