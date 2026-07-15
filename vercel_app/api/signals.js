import { normalizeDomain, sendError, setNoStore, sql, toIso, toNumber } from "../lib/db.js";

export default async function handler(req, res) {
  try {
    setNoStore(res);
    const db = sql();
    const domain = normalizeDomain(req.query.domain);
    const limit = Math.min(Math.max(Number(req.query.limit || 20), 1), 100);

    const rows = domain
      ? await db`
          WITH latest AS (
            SELECT DISTINCT ON (s.parent_market, s.related_market)
              s.parent_market,
              parent_m.question AS parent_question,
              parent_m.domain,
              s.related_market,
              child_m.question AS child_question,
              s.expected_probability,
              s.observed_probability,
              s.edge,
              s.confidence,
              s.signal,
              s.created_at
            FROM arbitrage_signals s
            LEFT JOIN markets parent_m ON parent_m.id = s.parent_market
            LEFT JOIN markets child_m ON child_m.id = s.related_market
            WHERE s.parent_market ~ '^[0-9]+$'
              AND s.related_market ~ '^[0-9]+$'
              AND parent_m.domain = ${domain}
            ORDER BY s.parent_market, s.related_market, s.created_at DESC, s.id DESC
          ),
          ranked AS (
            SELECT
              *,
              ROW_NUMBER() OVER (
                PARTITION BY parent_market
                ORDER BY ABS(edge) DESC NULLS LAST, created_at DESC
              ) AS parent_rank,
              ROW_NUMBER() OVER (
                PARTITION BY related_market
                ORDER BY ABS(edge) DESC NULLS LAST, created_at DESC
              ) AS child_rank
            FROM latest
            WHERE signal IN ('BUY', 'SELL')
          )
          SELECT
            parent_market,
            parent_question,
            domain,
            related_market,
            child_question,
            expected_probability,
            observed_probability,
            edge,
            confidence,
            signal,
            created_at
          FROM ranked
          WHERE parent_rank <= 3
            AND child_rank <= 3
          ORDER BY ABS(edge) DESC NULLS LAST, created_at DESC
          LIMIT ${limit}
        `
      : await db`
          WITH latest AS (
            SELECT DISTINCT ON (s.parent_market, s.related_market)
              s.parent_market,
              parent_m.question AS parent_question,
              parent_m.domain,
              s.related_market,
              child_m.question AS child_question,
              s.expected_probability,
              s.observed_probability,
              s.edge,
              s.confidence,
              s.signal,
              s.created_at
            FROM arbitrage_signals s
            LEFT JOIN markets parent_m ON parent_m.id = s.parent_market
            LEFT JOIN markets child_m ON child_m.id = s.related_market
            WHERE s.parent_market ~ '^[0-9]+$'
              AND s.related_market ~ '^[0-9]+$'
            ORDER BY s.parent_market, s.related_market, s.created_at DESC, s.id DESC
          ),
          ranked AS (
            SELECT
              *,
              ROW_NUMBER() OVER (
                PARTITION BY parent_market
                ORDER BY ABS(edge) DESC NULLS LAST, created_at DESC
              ) AS parent_rank,
              ROW_NUMBER() OVER (
                PARTITION BY related_market
                ORDER BY ABS(edge) DESC NULLS LAST, created_at DESC
              ) AS child_rank
            FROM latest
            WHERE signal IN ('BUY', 'SELL')
          )
          SELECT
            parent_market,
            parent_question,
            domain,
            related_market,
            child_question,
            expected_probability,
            observed_probability,
            edge,
            confidence,
            signal,
            created_at
          FROM ranked
          WHERE parent_rank <= 3
            AND child_rank <= 3
          ORDER BY ABS(edge) DESC NULLS LAST, created_at DESC
          LIMIT ${limit}
        `;

    res.status(200).json(
      rows.map((row) => ({
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
      })),
    );
  } catch (error) {
    sendError(res, error);
  }
}
