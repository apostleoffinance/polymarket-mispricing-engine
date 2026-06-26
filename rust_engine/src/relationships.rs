use std::collections::HashMap;

pub fn build_relationships(
) -> HashMap<String, Vec<String>> {

    let mut graph =
        HashMap::new();

    graph.insert(
        "Trump Wins".to_string(),
        vec![
            "Republican Senate".to_string(),
            "Republican House".to_string(),
            "Trump Popular Vote".to_string(),
            "Trump Electoral College".to_string(),
        ],
    );

    graph.insert(
        "Bitcoin > 200k".to_string(),
        vec![
            "Bitcoin ETF Inflows".to_string(),
            "MicroStrategy Market Cap".to_string(),
            "Coinbase Revenue".to_string(),
        ],
    );

    graph.insert(
        "Fed Cuts Rates".to_string(),
        vec![
            "S&P 500".to_string(),
            "Nasdaq".to_string(),
            "Bitcoin".to_string(),
        ],
    );

    graph
}