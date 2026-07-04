use rust_decimal::Decimal;
use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct Market {
    pub id: String,
    pub question: String,

    #[serde(with = "rust_decimal::serde::str")]
    pub volume: Decimal,

    #[serde(with = "rust_decimal::serde::str")]
    pub liquidity: Decimal,

    #[serde(rename = "outcomePrices")]
    pub outcome_prices: String,

    #[serde(rename = "clobTokenIds", default)]
    pub clob_token_ids: String,

    pub active: bool,
    pub closed: bool,
}

impl Market {
    pub fn has_prices(&self) -> bool {
        !self.outcome_prices.is_empty() && self.outcome_prices != "[]"
    }

    pub fn clob_tokens(&self) -> (Option<String>, Option<String>) {
        if self.clob_token_ids.is_empty() || self.clob_token_ids == "[]" {
            return (None, None);
        }

        let parsed: Result<Vec<String>, _> = serde_json::from_str(&self.clob_token_ids);
        match parsed {
            Ok(ids) if ids.len() >= 2 => (Some(ids[0].clone()), Some(ids[1].clone())),
            Ok(ids) if ids.len() == 1 => (Some(ids[0].clone()), None),
            _ => (None, None),
        }
    }
}

#[derive(Debug, Clone)]
pub struct ScrapedMarket {
    pub market: Market,
    pub domain: String,
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
    pub parent_label: String,
    pub parent_market_id: String,
    pub related_label: String,
    pub related_market_id: String,
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
