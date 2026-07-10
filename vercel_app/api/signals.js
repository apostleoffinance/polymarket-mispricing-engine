import {
  enrichSignalRow,
  normalizeDomain,
  sendError,
  sql,
} from "../lib/db.js";

export default async function handler(req, res) {
  try {
    const db = sql();
    const domain = normalizeDomain(req.query.domain);
    const limit = Math.min(Math.max(Number(req.query.limit || 20), 1), 100);

    const rows = domain
      ? await db`
          SELECT
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
            s.reason_json,
            s.created_at,
            r.lag_minutes,
            r.lead_correlation,
            r.stability_score,
            r.relationship_type,
            r.discovery_source
          FROM arbitrage_signals s
          LEFT JOIN markets parent_m ON parent_m.id = s.parent_market
          LEFT JOIN markets child_m ON child_m.id = s.related_market
          LEFT JOIN LATERAL (
            SELECT lag_minutes, lead_correlation, stability_score, relationship_type, discovery_source
            FROM market_relationships
            WHERE parent_market_id = s.parent_market
              AND related_market_id = s.related_market
            ORDER BY created_at DESC NULLS LAST
            LIMIT 1
          ) r ON TRUE
          WHERE s.parent_market ~ '^[0-9]+$'
            AND s.related_market ~ '^[0-9]+$'
            AND parent_m.domain = ${domain}
          ORDER BY s.created_at DESC
          LIMIT ${limit}
        `
      : await db`
          SELECT
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
            s.reason_json,
            s.created_at,
            r.lag_minutes,
            r.lead_correlation,
            r.stability_score,
            r.relationship_type,
            r.discovery_source
          FROM arbitrage_signals s
          LEFT JOIN markets parent_m ON parent_m.id = s.parent_market
          LEFT JOIN markets child_m ON child_m.id = s.related_market
          LEFT JOIN LATERAL (
            SELECT lag_minutes, lead_correlation, stability_score, relationship_type, discovery_source
            FROM market_relationships
            WHERE parent_market_id = s.parent_market
              AND related_market_id = s.related_market
            ORDER BY created_at DESC NULLS LAST
            LIMIT 1
          ) r ON TRUE
          WHERE s.parent_market ~ '^[0-9]+$'
            AND s.related_market ~ '^[0-9]+$'
          ORDER BY s.created_at DESC
          LIMIT ${limit}
        `;

    res.status(200).json(rows.map(enrichSignalRow));
  } catch (error) {
    // Fallback if lag/stability columns are not migrated yet.
    try {
      const db = sql();
      const domain = normalizeDomain(req.query.domain);
      const limit = Math.min(Math.max(Number(req.query.limit || 20), 1), 100);
      const rows = domain
        ? await db`
            SELECT
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
              s.reason_json,
              s.created_at
            FROM arbitrage_signals s
            LEFT JOIN markets parent_m ON parent_m.id = s.parent_market
            LEFT JOIN markets child_m ON child_m.id = s.related_market
            WHERE s.parent_market ~ '^[0-9]+$'
              AND s.related_market ~ '^[0-9]+$'
              AND parent_m.domain = ${domain}
            ORDER BY s.created_at DESC
            LIMIT ${limit}
          `
        : await db`
            SELECT
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
              s.reason_json,
              s.created_at
            FROM arbitrage_signals s
            LEFT JOIN markets parent_m ON parent_m.id = s.parent_market
            LEFT JOIN markets child_m ON child_m.id = s.related_market
            WHERE s.parent_market ~ '^[0-9]+$'
              AND s.related_market ~ '^[0-9]+$'
            ORDER BY s.created_at DESC
            LIMIT ${limit}
          `;
      res.status(200).json(rows.map(enrichSignalRow));
    } catch (fallbackError) {
      sendError(res, fallbackError);
    }
  }
}
