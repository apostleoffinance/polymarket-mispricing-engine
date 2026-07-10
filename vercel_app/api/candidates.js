import { normalizeDomain, sendError, sql, toIso, toNumber } from "../lib/db.js";

export default async function handler(req, res) {
  try {
    const db = sql();
    const domain = normalizeDomain(req.query.domain);
    const status = Array.isArray(req.query.status)
      ? req.query.status[0]
      : req.query.status;
    const limit = Math.min(Math.max(Number(req.query.limit || 30), 1), 100);

    const rows = domain
      ? status
        ? await db`
            SELECT
              id,
              parent_market_id,
              child_market_id,
              parent_question,
              child_question,
              parent_domain,
              child_domain,
              source,
              rationale,
              status,
              confidence,
              correlation_shrunk,
              lag_minutes,
              lead_correlation,
              stability_score,
              strength,
              n_observations,
              rejection_reason,
              created_at,
              updated_at
            FROM candidate_relationships
            WHERE status = ${String(status)}
              AND (parent_domain = ${domain} OR child_domain = ${domain})
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT ${limit}
          `
        : await db`
            SELECT
              id,
              parent_market_id,
              child_market_id,
              parent_question,
              child_question,
              parent_domain,
              child_domain,
              source,
              rationale,
              status,
              confidence,
              correlation_shrunk,
              lag_minutes,
              lead_correlation,
              stability_score,
              strength,
              n_observations,
              rejection_reason,
              created_at,
              updated_at
            FROM candidate_relationships
            WHERE parent_domain = ${domain} OR child_domain = ${domain}
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT ${limit}
          `
      : status
        ? await db`
            SELECT
              id,
              parent_market_id,
              child_market_id,
              parent_question,
              child_question,
              parent_domain,
              child_domain,
              source,
              rationale,
              status,
              confidence,
              correlation_shrunk,
              lag_minutes,
              lead_correlation,
              stability_score,
              strength,
              n_observations,
              rejection_reason,
              created_at,
              updated_at
            FROM candidate_relationships
            WHERE status = ${String(status)}
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT ${limit}
          `
        : await db`
            SELECT
              id,
              parent_market_id,
              child_market_id,
              parent_question,
              child_question,
              parent_domain,
              child_domain,
              source,
              rationale,
              status,
              confidence,
              correlation_shrunk,
              lag_minutes,
              lead_correlation,
              stability_score,
              strength,
              n_observations,
              rejection_reason,
              created_at,
              updated_at
            FROM candidate_relationships
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT ${limit}
          `;

    res.status(200).json(
      rows.map((row) => ({
        id: row.id,
        parent_id: row.parent_market_id,
        child_id: row.child_market_id,
        parent_question: row.parent_question,
        child_question: row.child_question,
        parent_domain: row.parent_domain,
        child_domain: row.child_domain,
        source: row.source,
        rationale: row.rationale,
        status: row.status,
        confidence: row.confidence === null ? null : toNumber(row.confidence),
        correlation_shrunk:
          row.correlation_shrunk === null ? null : toNumber(row.correlation_shrunk),
        lag_minutes: row.lag_minutes === null ? null : Number(row.lag_minutes),
        lead_correlation:
          row.lead_correlation === null ? null : toNumber(row.lead_correlation),
        stability_score:
          row.stability_score === null ? null : toNumber(row.stability_score),
        strength: row.strength === null ? null : toNumber(row.strength),
        n_observations: row.n_observations,
        rejection_reason: row.rejection_reason,
        created_at: toIso(row.created_at),
        updated_at: toIso(row.updated_at),
      })),
    );
  } catch (error) {
    if (String(error.message || error).includes("candidate_relationships")) {
      res.status(200).json([]);
      return;
    }
    sendError(res, error);
  }
}
