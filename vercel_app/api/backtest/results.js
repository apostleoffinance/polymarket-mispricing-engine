import { normalizeDomain, sendError, sql, toIso, toNumber } from "../../lib/db.js";

export default async function handler(req, res) {
  try {
    const db = sql();
    const domain = normalizeDomain(req.query.domain);
    const limit = Math.min(Math.max(Number(req.query.limit || 50), 1), 5000);

    const rows = domain
      ? await db`
          SELECT
            r.parent_market_id,
            parent_m.question AS parent_question,
            r.child_market_id,
            child_m.question AS child_question,
            r.domain,
            r.signal,
            r.edge_at_t,
            r.edge_at_t_plus,
            r.directional_win,
            r.edge_closed,
            r.simple_pnl,
            r.minutes_to_reprice,
            r.signal_time
          FROM backtest_results r
          LEFT JOIN markets parent_m ON parent_m.id = r.parent_market_id
          LEFT JOIN markets child_m ON child_m.id = r.child_market_id
          WHERE r.run_id = (SELECT MAX(id) FROM backtest_runs)
            AND r.domain = ${domain}
          ORDER BY ABS(r.edge_at_t) DESC
          LIMIT ${limit}
        `
      : await db`
          SELECT
            r.parent_market_id,
            parent_m.question AS parent_question,
            r.child_market_id,
            child_m.question AS child_question,
            r.domain,
            r.signal,
            r.edge_at_t,
            r.edge_at_t_plus,
            r.directional_win,
            r.edge_closed,
            r.simple_pnl,
            r.minutes_to_reprice,
            r.signal_time
          FROM backtest_results r
          LEFT JOIN markets parent_m ON parent_m.id = r.parent_market_id
          LEFT JOIN markets child_m ON child_m.id = r.child_market_id
          WHERE r.run_id = (SELECT MAX(id) FROM backtest_runs)
          ORDER BY ABS(r.edge_at_t) DESC
          LIMIT ${limit}
        `;

    res.status(200).json(
      rows.map((row) => ({
        parent_id: row.parent_market_id,
        parent_question: row.parent_question,
        child_id: row.child_market_id,
        child_question: row.child_question,
        domain: row.domain,
        signal: row.signal,
        edge_at_t: row.edge_at_t === null ? null : toNumber(row.edge_at_t),
        edge_at_t_plus: row.edge_at_t_plus === null ? null : toNumber(row.edge_at_t_plus),
        directional_win: row.directional_win,
        edge_closed: row.edge_closed,
        simple_pnl: row.simple_pnl === null ? null : toNumber(row.simple_pnl),
        minutes_to_reprice:
          row.minutes_to_reprice === null || row.minutes_to_reprice === undefined
            ? null
            : Number(row.minutes_to_reprice),
        signal_time: toIso(row.signal_time),
      })),
    );
  } catch (error) {
    sendError(res, error);
  }
}
