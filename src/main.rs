mod database;
mod http_client;
mod models;
mod parser;
mod normalizer;
mod relationships;

use database::{insert_market, insert_probability_snapshot, insert_relationship};
use http_client::{build_client, get_with_retry};
use models::{Market, MarketRelationship};
use normalizer::normalize_market;
use relationships::build_relationships;
use sqlx::PgPool;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenvy::dotenv().ok();

    let database_url = std::env::var("DATABASE_URL")?;

    let pool = PgPool::connect(&database_url).await?;

    println!("Connected to PostgreSQL");

    let url =
        "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=100";

    let client = build_client()?;
    let body = get_with_retry(&client, url, 3).await?;
    let markets: Vec<Market> = serde_json::from_str(&body)?;

    for market in markets {
        // Store raw market metadata (id, question, volume, liquidity, active, closed)
        insert_market(&pool, &market).await?;

        // Store normalized probabilities snapshot (yes/no)
        let snapshot = normalize_market(&market)?;

        insert_probability_snapshot(&pool, &snapshot).await?;

        println!(
            "{} | YES={} | NO={}",
            snapshot.question, snapshot.yes_probability, snapshot.no_probability
        );
    }

    let graph =
    build_relationships();

    for (parent, children) in graph {

        for child in children {
    
            let relationship =
                MarketRelationship {
    
                    parent_market:
                        parent.clone(),
    
                    related_market:
                        child,
    
                    relationship_type:
                        "positive".to_string(),
                };
    
            insert_relationship(
                &pool,
                &relationship
            )
            .await?;
        }
    }

    Ok(())
}
