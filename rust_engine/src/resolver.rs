use crate::models::Market;
use crate::relationships::RelationshipTemplate;

pub fn find_market_by_keywords<'a>(
    markets: &'a [Market],
    keywords: &[&str],
) -> Option<&'a Market> {
    markets.iter().find(|market| {
        let question = market.question.to_lowercase();
        keywords
            .iter()
            .all(|keyword| question.contains(&keyword.to_lowercase()))
    })
}

pub struct ResolvedRelationship {
    pub parent_label: String,
    pub parent_market_id: String,
    pub related_label: String,
    pub related_market_id: String,
}

pub fn resolve_relationships(
    markets: &[Market],
    templates: &[RelationshipTemplate],
) -> Vec<ResolvedRelationship> {
    let mut resolved = Vec::new();

    for template in templates {
        let Some(parent) = find_market_by_keywords(markets, template.parent_keywords) else {
            continue;
        };
        let Some(child) = find_market_by_keywords(markets, template.child_keywords) else {
            continue;
        };

        // Avoid matching the same market for both parent and child.
        if parent.id == child.id {
            continue;
        }

        resolved.push(ResolvedRelationship {
            parent_label: template.parent_label.to_string(),
            parent_market_id: parent.id.clone(),
            related_label: template.child_label.to_string(),
            related_market_id: child.id.clone(),
        });
    }

    resolved
}
