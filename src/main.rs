use serde::Deserialize;
use rust_decimal::Decimal;
use sqlx::PgPool;

#[derive(Debug, Deserialize)]
struct Market {
    id: String,
    question: String,
    volume: Decimal,
    liquidity: Decimal,
    active: bool,
    closed: bool,
}


async fn insert_market(
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
    .bind(&market.volume)
    .bind(&market.liquidity)
    .bind(market.active)
    .bind(market.closed)
    .execute(pool)
    .await?;

    Ok(())
}


#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {

    // Connection string
    dotenvy::dotenv().ok();

    let database_url =
        std::env::var("DATABASE_URL")?;

    // Connect to Postgres
    let pool = PgPool::connect(&database_url)
        .await?;

    println!("Connected to PostgreSQL");

    let url =
        "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=100";

    let markets: Vec<Market> = reqwest::get(url)
        .await?
        .json()
        .await?;

    // println!("{:#?}", markets);
    for market in &markets {

        insert_market(
            &pool,
            market
        )
        .await?;
    
        println!(
            "Stored Market {} - {}",
            market.id,
            market.question
        );
    }

    Ok(())
}