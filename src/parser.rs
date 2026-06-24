use rust_decimal::Decimal;
use std::str::FromStr;

pub fn parse_outcome_prices(
    raw: &str,
) -> Result<(Decimal, Decimal), Box<dyn std::error::Error>> {

    let prices: Vec<String> =
        serde_json::from_str(raw)?;

    let yes_price =
        Decimal::from_str(&prices[0])?;

    let no_price =
        Decimal::from_str(&prices[1])?;

    Ok((yes_price, no_price))
}