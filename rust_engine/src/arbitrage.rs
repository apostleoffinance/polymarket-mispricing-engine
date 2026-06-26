use rust_decimal::Decimal;

use crate::models::ArbitrageSignal;

pub fn calculate_edge(expected: Decimal, observed: Decimal) -> Decimal {
    expected - observed
}

pub fn determine_signal(edge: Decimal) -> String {
    if edge > Decimal::new(10, 2) {
        "BUY".to_string()
    } else if edge < Decimal::new(-10, 2) {
        "SELL".to_string()
    } else {
        "HOLD".to_string()
    }
}

pub fn expected_probability(parent_probability: Decimal) -> Decimal {
    parent_probability * Decimal::new(65, 2)
}

pub fn build_signal(
    parent_market_id: &str,
    related_market_id: &str,
    parent_yes: Decimal,
    child_yes: Decimal,
) -> ArbitrageSignal {
    let expected = expected_probability(parent_yes);
    let edge = calculate_edge(expected, child_yes);
    let signal = determine_signal(edge);

    ArbitrageSignal {
        parent_market: parent_market_id.to_string(),
        related_market: related_market_id.to_string(),
        expected_probability: expected,
        observed_probability: child_yes,
        edge,
        signal,
    }
}
