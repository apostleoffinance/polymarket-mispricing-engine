mod database;
mod domains;
mod fetcher;
mod http_client;
mod models;
mod normalizer;
mod parser;

use database::{insert_probability_snapshot_if_changed, upsert_market};
use fetcher::fetch_domain_markets;
use http_client::build_client;
use normalizer::normalize_market;
use sqlx::PgPool;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenvy::dotenv().ok();

    let database_url = std::env::var("DATABASE_URL")?;
    let pool = PgPool::connect(&database_url).await?;

    println!("Connected to PostgreSQL");

    let client = build_client()?;
    let scraped_markets = fetch_domain_markets(&client).await?;

    let mut markets_upserted = 0;
    let mut snapshots_inserted = 0;
    let mut snapshots_skipped = 0;

    for scraped in &scraped_markets {
        if upsert_market(&pool, scraped).await? {
            markets_upserted += 1;
        }

        let snapshot = normalize_market(&scraped.market)?;

        if insert_probability_snapshot_if_changed(&pool, &snapshot).await? {
            snapshots_inserted += 1;
            println!(
                "[{}] {} | YES={} | NO={}",
                scraped.domain,
                snapshot.question,
                snapshot.yes_probability,
                snapshot.no_probability
            );
        } else {
            snapshots_skipped += 1;
        }
    }

    println!();
    println!("Summary:");
    println!("  Domains: politics, football, crypto, macro, geopolitics");
    println!("  Markets fetched: {}", scraped_markets.len());
    println!("  Markets upserted: {markets_upserted}");
    println!("  Probability snapshots inserted: {snapshots_inserted}");
    println!("  Probability snapshots skipped (unchanged): {snapshots_skipped}");
    println!();
    println!("  Graph + signals: run `cd research_engine && uv run run_graph.py`");

    Ok(())
}
