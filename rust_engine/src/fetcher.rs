use std::collections::HashMap;
use std::str::FromStr;

use reqwest::Client;
use reqwest::StatusCode;
use rust_decimal::Decimal;
use serde::Deserialize;

use crate::domains::DOMAIN_TAGS;
use crate::http_client::get_with_retry;
use crate::models::{Market, ScrapedMarket};

const GAMMA_EVENTS_URL: &str = "https://gamma-api.polymarket.com/events";
const PAGE_SIZE: usize = 100;
const MAX_PAGES_PER_DOMAIN: usize = 50;

#[derive(Debug, Deserialize)]
struct GammaEvent {
    markets: Vec<GammaMarket>,
}

/// Gamma nested markets sometimes omit string `volume`/`liquidity` but include `*Num`.
#[derive(Debug, Deserialize)]
struct GammaMarket {
    id: String,
    #[serde(default)]
    question: String,
    #[serde(rename = "outcomePrices", default)]
    outcome_prices: String,
    #[serde(rename = "clobTokenIds", default)]
    clob_token_ids: String,
    #[serde(default)]
    active: bool,
    #[serde(default)]
    closed: bool,
    volume: Option<String>,
    #[serde(rename = "volumeNum")]
    volume_num: Option<f64>,
    liquidity: Option<String>,
    #[serde(rename = "liquidityNum")]
    liquidity_num: Option<f64>,
}

impl GammaMarket {
    fn into_market(self) -> Market {
        Market {
            id: self.id,
            question: self.question,
            volume: decimal_field(self.volume, self.volume_num),
            liquidity: decimal_field(self.liquidity, self.liquidity_num),
            outcome_prices: self.outcome_prices,
            clob_token_ids: self.clob_token_ids,
            active: self.active,
            closed: self.closed,
        }
    }
}

fn decimal_field(string_value: Option<String>, numeric_value: Option<f64>) -> Decimal {
    if let Some(value) = string_value {
        if let Ok(parsed) = Decimal::from_str(&value) {
            return parsed;
        }
    }

    numeric_value
        .and_then(Decimal::from_f64_retain)
        .unwrap_or_default()
}

/// Fetch active markets from Polymarket, scoped to politics, football, crypto,
/// macro, and geopolitics event tags. Deduplicates by market id (first tag wins).
pub async fn fetch_domain_markets(
    client: &Client,
) -> Result<Vec<ScrapedMarket>, Box<dyn std::error::Error>> {
    let mut by_id: HashMap<String, ScrapedMarket> = HashMap::new();
    let mut domain_counts: HashMap<&str, usize> = HashMap::new();

    for (domain, tag_slug) in DOMAIN_TAGS {
        let mut domain_new = 0usize;

        for page in 0..MAX_PAGES_PER_DOMAIN {
            let offset = page * PAGE_SIZE;
            let url = format!(
                "{GAMMA_EVENTS_URL}?tag_slug={tag_slug}&active=true&closed=false&limit={PAGE_SIZE}&offset={offset}"
            );

            let body = match get_with_retry(client, &url, 3).await {
                Ok(body) => body,
                Err(error) if error.status() == Some(StatusCode::UNPROCESSABLE_ENTITY) => {
                    break;
                }
                Err(error) => return Err(error.into()),
            };
            let events: Vec<GammaEvent> = serde_json::from_str(&body)?;
            let page_len = events.len();

            if page_len == 0 {
                break;
            }

            for event in events {
                for raw in event.markets {
                    let market = raw.into_market();
                    if !market.active || market.closed || !market.has_prices() {
                        continue;
                    }

                    if by_id.contains_key(&market.id) {
                        continue;
                    }

                    domain_new += 1;
                    by_id.insert(
                        market.id.clone(),
                        ScrapedMarket {
                            market,
                            domain: domain.to_string(),
                        },
                    );
                }
            }

            if page_len < PAGE_SIZE {
                break;
            }
        }

        domain_counts.insert(domain, domain_new);
    }

    println!("Markets fetched by domain:");
    for (domain, tag_slug) in DOMAIN_TAGS {
        println!(
            "  {domain} (tag={tag_slug}): {}",
            domain_counts.get(domain).copied().unwrap_or(0)
        );
    }

    Ok(by_id.into_values().collect())
}
