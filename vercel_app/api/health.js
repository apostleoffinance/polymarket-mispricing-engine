export default function handler(_req, res) {
  res.status(200).json({
    status: "ok",
    version: 4,
    runtime: "vercel",
    features: [
      "domains",
      "domain_filter",
      "signal_explanations",
      "lead_lag",
      "stability",
      "candidates",
      "source_summaries",
      "enrichment_panel",
    ],
  });
}
