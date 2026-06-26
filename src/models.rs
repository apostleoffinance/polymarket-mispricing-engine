use rust_decimal::Decimal;
use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct Market {
    pub id: String,
    pub question: String,

    // Polymarket's Gamma API commonly returns these as JSON strings.
    #[serde(with = "rust_decimal::serde::str")]
    pub volume: Decimal,

    #[serde(with = "rust_decimal::serde::str")]
    pub liquidity: Decimal,

    #[serde(rename = "outcomePrices")]
    pub outcome_prices: String,

    pub active: bool,
    pub closed: bool,
}


#[derive(Debug)]
pub struct ProbabilitySnapshot {
    pub market_id: String,
    pub question: String,
    pub yes_probability: Decimal,
    pub no_probability: Decimal,
}

#[derive(Debug)]
pub struct MarketRelationship {
    pub parent_market: String,
    pub related_market: String,
    pub relationship_type: String,
}

#[derive(Debug)]

pub struct ArbitrageSignal {

    pub parent_market: String,
    pub related_market: String,
    pub expected_probability: Decimal,
    pub observed_probability: Decimal,
    pub edge: Decimal,
    pub signal: String,
}