use crate::models::{
    Market,
    ProbabilitySnapshot,
};

use crate::parser::parse_outcome_prices;

pub fn normalize_market(
    market: &Market,
) -> Result<
    ProbabilitySnapshot,
    Box<dyn std::error::Error>
> {

    let (
        yes_probability,
        no_probability
    ) = parse_outcome_prices(
        &market.outcome_prices
    )?;

    Ok(
        ProbabilitySnapshot {
            market_id:
                market.id.clone(),

            question:
                market.question.clone(),

            yes_probability,

            no_probability,
        }
    )
}