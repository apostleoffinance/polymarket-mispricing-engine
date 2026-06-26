mod database;
mod http_client;
mod models;
mod parser;
mod normalizer;
mod relationships;
mod arbitrage;

use database::{
    insert_probability_snapshot_if_changed, insert_relationship, upsert_market,
};
use http_client::{build_client, get_with_retry};
use models::{Market, MarketRelationship};
use normalizer::normalize_market;
use relationships::build_relationships;
use sqlx::PgPool;
use arbitrage::{
    calculate_edge,
    determine_signal,
    expected_probability,
};
use database::insert_signal;
use models::ArbitrageSignal;
use rust_decimal_macros::dec;

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

    let mut markets_upserted = 0;
    let mut snapshots_inserted = 0;
    let mut snapshots_skipped = 0;

    for market in &markets {
        if upsert_market(&pool, market).await? {
            markets_upserted += 1;
        }

        let snapshot = normalize_market(market)?;

        if insert_probability_snapshot_if_changed(&pool, &snapshot).await? {
            snapshots_inserted += 1;
            println!(
                "{} | YES={} | NO={}",
                snapshot.question, snapshot.yes_probability, snapshot.no_probability
            );
        } else {
            snapshots_skipped += 1;
        }
    }

    let graph = build_relationships();
    let mut relationships_inserted = 0;
    let mut relationships_skipped = 0;

    for (parent, children) in graph {
        for child in children {
            let relationship = MarketRelationship {
                parent_market: parent.clone(),
                related_market: child,
                relationship_type: "positive".to_string(),
            };

            if insert_relationship(&pool, &relationship).await? {
                relationships_inserted += 1;
                println!("Relationship: {} -> {}", relationship.parent_market, relationship.related_market);
            } else {
                relationships_skipped += 1;
            }
        }
    }

    let parent_probability = dec!(0.70);
    let observed_probability = dec!(0.15);
    let expected =
        expected_probability(
            parent_probability
        );
    let edge =
        calculate_edge(
            expected,
            observed_probability
        );
    let signal =
        determine_signal(edge);

        let arbitrage_signal =
        ArbitrageSignal {
    
            parent_market:
                "Trump Wins".to_string(),
    
            related_market:
                "Republican Senate".to_string(),
    
            expected_probability:
                expected,

            observed_probability,
            edge,
            signal,
        };

        insert_signal(
            &pool,
            &arbitrage_signal
        )
        .await?;


    println!();
    println!("Summary:");
    println!("  Markets fetched: {}", markets.len());
    println!("  Markets upserted: {markets_upserted}");
    println!("  Probability snapshots inserted: {snapshots_inserted}");
    println!("  Probability snapshots skipped (unchanged): {snapshots_skipped}");
    println!("  Relationships inserted: {relationships_inserted}");
    println!("  Relationships skipped (already exist): {relationships_skipped}");
    println!("{:#?}", arbitrage_signal);

    Ok(())
}
