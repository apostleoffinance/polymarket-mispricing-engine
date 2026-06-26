use crate::models::{ArbitrageSignal, Market, MarketRelationship, ProbabilitySnapshot};
use sqlx::PgPool;

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
            parent_market_id,
            related_market,
            related_market_id,
            relationship_type
        )
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (parent_market_id, related_market_id, relationship_type) DO NOTHING
        "#
    )
    .bind(&relationship.parent_label)
    .bind(&relationship.parent_market_id)
    .bind(&relationship.related_label)
    .bind(&relationship.related_market_id)
    .bind(&relationship.relationship_type)
    .execute(pool)
    .await?;

    Ok(result.rows_affected() > 0)
}

pub async fn insert_signal_if_changed(
    pool: &PgPool,
    signal: &ArbitrageSignal,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        r#"
        INSERT INTO arbitrage_signals(
            parent_market,
            related_market,
            expected_probability,
            observed_probability,
            edge,
            signal
        )
        SELECT $1, $2, $3, $4, $5, $6
        WHERE NOT EXISTS (
            SELECT 1
            FROM arbitrage_signals
            WHERE parent_market = $1
              AND related_market = $2
              AND expected_probability = $3
              AND observed_probability = $4
              AND edge = $5
              AND signal = $6
              AND created_at = (
                  SELECT MAX(created_at)
                  FROM arbitrage_signals
                  WHERE parent_market = $1
                    AND related_market = $2
              )
        )
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

    Ok(result.rows_affected() > 0)
}
