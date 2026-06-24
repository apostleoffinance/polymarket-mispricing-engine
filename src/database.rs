use crate::models::{Market, ProbabilitySnapshot};
use sqlx::PgPool;
use crate::models::MarketRelationship;

pub async fn insert_market(
    pool: &PgPool,
    market: &Market,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        r#"
        INSERT INTO markets(
            id,
            question,
            volume,
            liquidity,
            active,
            closed
        )
        VALUES ($1,$2,$3,$4,$5,$6)
        ON CONFLICT (id)
        DO NOTHING
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

    Ok(())
}

pub async fn insert_probability_snapshot(
    pool: &PgPool,
    snapshot: &ProbabilitySnapshot,
) -> Result<(), sqlx::Error> {

    sqlx::query(
        r#"
        INSERT INTO probability_history(
            market_id,
            question,
            yes_probability,
            no_probability
        )
        VALUES ($1,$2,$3,$4)
        "#
    )
    .bind(&snapshot.market_id)
    .bind(&snapshot.question)
    .bind(snapshot.yes_probability)
    .bind(snapshot.no_probability)
    .execute(pool)
    .await?;

    Ok(())
}


pub async fn insert_relationship(
    pool: &PgPool,
    relationship: &MarketRelationship,
) -> Result<(), sqlx::Error> {

    sqlx::query(
        r#"
        INSERT INTO market_relationships(
            parent_market,
            related_market,
            relationship_type
        )
        VALUES ($1,$2,$3)
        "#
    )
    .bind(&relationship.parent_market)
    .bind(&relationship.related_market)
    .bind(&relationship.relationship_type)
    .execute(pool)
    .await?;

    Ok(())
}