/// Template for a parent → child market relationship.
/// Keywords are matched case-insensitively against scraped market questions.
pub struct RelationshipTemplate {
    pub parent_label: &'static str,
    pub parent_keywords: &'static [&'static str],
    pub child_label: &'static str,
    pub child_keywords: &'static [&'static str],
}

pub fn relationship_templates() -> Vec<RelationshipTemplate> {
    vec![
        // 2028 Democratic nomination cluster (common in active markets feed)
        RelationshipTemplate {
            parent_label: "Newsom 2028",
            parent_keywords: &["newsom", "2028"],
            child_label: "AOC 2028",
            child_keywords: &["ocasio", "2028"],
        },
        RelationshipTemplate {
            parent_label: "Newsom 2028",
            parent_keywords: &["newsom", "2028"],
            child_label: "Wes Moore 2028",
            child_keywords: &["wes moore", "2028"],
        },
        RelationshipTemplate {
            parent_label: "Newsom 2028",
            parent_keywords: &["newsom", "2028"],
            child_label: "Warnock 2028",
            child_keywords: &["warnock", "2028"],
        },
        // 2026 World Cup cluster
        RelationshipTemplate {
            parent_label: "France World Cup",
            parent_keywords: &["france", "world cup"],
            child_label: "England World Cup",
            child_keywords: &["england", "world cup"],
        },
        RelationshipTemplate {
            parent_label: "France World Cup",
            parent_keywords: &["france", "world cup"],
            child_label: "Portugal World Cup",
            child_keywords: &["portugal", "world cup"],
        },
        RelationshipTemplate {
            parent_label: "England World Cup",
            parent_keywords: &["england", "world cup"],
            child_label: "Morocco World Cup",
            child_keywords: &["morocco", "world cup"],
        },
        // Geopolitical cluster
        RelationshipTemplate {
            parent_label: "Xi out before 2027",
            parent_keywords: &["xi jinping", "2027"],
            child_label: "Putin out by 2026",
            child_keywords: &["putin", "2026"],
        },
        // Legacy templates (active when these markets appear in the feed)
        RelationshipTemplate {
            parent_label: "Trump Wins",
            parent_keywords: &["trump", "president"],
            child_label: "Republican Senate",
            child_keywords: &["republican", "senate"],
        },
        RelationshipTemplate {
            parent_label: "Bitcoin > 200k",
            parent_keywords: &["bitcoin", "200"],
            child_label: "Bitcoin ETF",
            child_keywords: &["bitcoin", "etf"],
        },
        RelationshipTemplate {
            parent_label: "Fed Cuts Rates",
            parent_keywords: &["fed", "rate cut"],
            child_label: "S&P 500",
            child_keywords: &["s&p 500"],
        },
    ]
}
