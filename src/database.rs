use crate::models::{Market, MarketRelationship, ProbabilitySnapshot};
use sqlx::PgPool;
use crate::models::ArbitrageSignal;

pub async fn upsert_market(pool: &PgPool, market: &Market) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        r#"
        INSERT INTO markets(
            id,
            question,
            volume,
            liquidity,
            active,
            closed
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (id) DO UPDATE SET
            question = EXCLUDED.question,
            volume = EXCLUDED.volume,
            liquidity = EXCLUDED.liquidity,
            active = EXCLUDED.active,
            closed = EXCLUDED.closed
        "#
    )
    .bind(&market.id)
    .bind(&market.question)
    .bind(market.volume)
    .bind(market.liquidity)
    .bind(market.active)
    .bind(market.closed)
    .execute(pool)
    .await?;

    Ok(result.rows_affected() > 0)
}

/// Inserts a snapshot only when probabilities changed since the latest row for this market.
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

pub async fn insert_relationship(
    pool: &PgPool,
    relationship: &MarketRelationship,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        r#"
        INSERT INTO market_relationships(
            parent_market,
            related_market,
            relationship_type
        )
        VALUES ($1, $2, $3)
        ON CONFLICT (parent_market, related_market, relationship_type) DO NOTHING
        "#
    )
    .bind(&relationship.parent_market)
    .bind(&relationship.related_market)
    .bind(&relationship.relationship_type)
    .execute(pool)
    .await?;

    Ok(result.rows_affected() > 0)
}


pub async fn insert_signal(
    pool: &PgPool,
    signal: &ArbitrageSignal,
) -> Result<(), sqlx::Error> {

    sqlx::query(
        r#"
        INSERT INTO arbitrage_signals(
            parent_market,
            related_market,
            expected_probability,
            observed_probability,
            edge,
            signal
        )
        VALUES ($1,$2,$3,$4,$5,$6)
        "#
    )
    .bind(&signal.parent_market)
    .bind(&signal.related_market)
    .bind(signal.expected_probability)
    .bind(signal.observed_probability)
    .bind(signal.edge)
    .bind(&signal.signal)
    .execute(pool)
    .await?;

    Ok(())
}