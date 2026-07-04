use crate::models::{ProbabilitySnapshot, ScrapedMarket};
use sqlx::PgPool;

pub async fn upsert_market(pool: &PgPool, scraped: &ScrapedMarket) -> Result<bool, sqlx::Error> {
    let market = &scraped.market;

    let (yes_token, no_token) = market.clob_tokens();

    let result = sqlx::query(
        r#"
        INSERT INTO markets(
            id,
            question,
            volume,
            liquidity,
            active,
            closed,
            domain,
            yes_clob_token_id,
            no_clob_token_id
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (id) DO UPDATE SET
            question = EXCLUDED.question,
            volume = EXCLUDED.volume,
            liquidity = EXCLUDED.liquidity,
            active = EXCLUDED.active,
            closed = EXCLUDED.closed,
            domain = EXCLUDED.domain,
            yes_clob_token_id = COALESCE(EXCLUDED.yes_clob_token_id, markets.yes_clob_token_id),
            no_clob_token_id = COALESCE(EXCLUDED.no_clob_token_id, markets.no_clob_token_id)
        "#
    )
    .bind(&market.id)
    .bind(&market.question)
    .bind(market.volume)
    .bind(market.liquidity)
    .bind(market.active)
    .bind(market.closed)
    .bind(&scraped.domain)
    .bind(yes_token)
    .bind(no_token)
    .execute(pool)
    .await?;

    Ok(result.rows_affected() > 0)
}

pub async fn insert_probability_snapshot_if_changed(
    pool: &PgPool,
    snapshot: &ProbabilitySnapshot,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        r#"
        INSERT INTO probability_history(
            market_id,
            question,
            yes_probability,
            no_probability
        )
        SELECT $1, $2, $3, $4
        WHERE NOT EXISTS (
            SELECT 1
            FROM probability_history
            WHERE market_id = $1
              AND yes_probability = $3
              AND no_probability = $4
              AND recorded_at = (
                  SELECT MAX(recorded_at)
                  FROM probability_history
                  WHERE market_id = $1
              )
        )
        "#
    )
    .bind(&snapshot.market_id)
    .bind(&snapshot.question)
    .bind(snapshot.yes_probability)
    .bind(snapshot.no_probability)
    .execute(pool)
    .await?;

    Ok(result.rows_affected() > 0)
}
