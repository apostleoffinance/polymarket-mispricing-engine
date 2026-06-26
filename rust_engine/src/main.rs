mod arbitrage;
mod database;
mod http_client;
mod models;
mod normalizer;
mod parser;
mod relationships;
mod resolver;

use arbitrage::build_signal;
use database::{
    insert_probability_snapshot_if_changed, insert_relationship, insert_signal_if_changed,
    upsert_market,
};
use http_client::{build_client, get_with_retry};
use models::MarketRelationship;
use normalizer::normalize_market;
use relationships::relationship_templates;
use resolver::resolve_relationships;
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
    let markets: Vec<models::Market> = serde_json::from_str(&body)?;

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

    let templates = relationship_templates();
    let resolved = resolve_relationships(&markets, &templates);

    let mut relationships_inserted = 0;
    let mut relationships_skipped = 0;
    let relationships_unresolved = templates.len() - resolved.len();

    for edge in &resolved {
        let relationship = MarketRelationship {
            parent_label: edge.parent_label.clone(),
            parent_market_id: edge.parent_market_id.clone(),
            related_label: edge.related_label.clone(),
            related_market_id: edge.related_market_id.clone(),
            relationship_type: "positive".to_string(),
        };

        if insert_relationship(&pool, &relationship).await? {
            relationships_inserted += 1;
            println!(
                "Relationship: {} ({}) -> {} ({})",
                relationship.parent_label,
                relationship.parent_market_id,
                relationship.related_label,
                relationship.related_market_id
            );
        } else {
            relationships_skipped += 1;
        }
    }

    let mut signals_inserted = 0;
    let mut signals_skipped = 0;
    let mut signals_evaluated = 0;

    for edge in &resolved {
        let parent = markets
            .iter()
            .find(|market| market.id == edge.parent_market_id);
        let child = markets
            .iter()
            .find(|market| market.id == edge.related_market_id);

        let (Some(parent), Some(child)) = (parent, child) else {
            continue;
        };

        let parent_snapshot = normalize_market(parent)?;
        let child_snapshot = normalize_market(child)?;

        let arbitrage_signal = build_signal(
            &edge.parent_market_id,
            &edge.related_market_id,
            parent_snapshot.yes_probability,
            child_snapshot.yes_probability,
        );

        signals_evaluated += 1;

        if insert_signal_if_changed(&pool, &arbitrage_signal).await? {
            signals_inserted += 1;
            println!(
                "Signal {} -> {} | parent_yes={} child_yes={} edge={} {}",
                edge.parent_label,
                edge.related_label,
                parent_snapshot.yes_probability,
                child_snapshot.yes_probability,
                arbitrage_signal.edge,
                arbitrage_signal.signal
            );
        } else {
            signals_skipped += 1;
        }
    }

    println!();
    println!("Summary:");
    println!("  Markets fetched: {}", markets.len());
    println!("  Markets upserted: {markets_upserted}");
    println!("  Probability snapshots inserted: {snapshots_inserted}");
    println!("  Probability snapshots skipped (unchanged): {snapshots_skipped}");
    println!("  Relationships resolved: {}", resolved.len());
    println!("  Relationships unresolved: {relationships_unresolved}");
    println!("  Relationships inserted: {relationships_inserted}");
    println!("  Relationships skipped (already exist): {relationships_skipped}");
    println!("  Arbitrage signals evaluated: {signals_evaluated}");
    println!("  Arbitrage signals inserted: {signals_inserted}");
    println!("  Arbitrage signals skipped (unchanged): {signals_skipped}");

    Ok(())
}
