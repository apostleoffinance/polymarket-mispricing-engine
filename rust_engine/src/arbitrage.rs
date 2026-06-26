use rust_decimal::Decimal;

pub fn calculate_edge(
    expected: Decimal,
    observed: Decimal,
) -> Decimal {

    expected - observed
}

pub fn determine_signal(
    edge: Decimal,
) -> String {

    if edge > Decimal::new(10, 2) {
        "BUY".to_string()
    } else if edge < Decimal::new(-10, 2) {
        "SELL".to_string()
    } else {
        "HOLD".to_string()
    }
}

pub fn expected_probability(
    parent_probability: Decimal,
) -> Decimal {

    parent_probability
        * Decimal::new(65, 2)
}