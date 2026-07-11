export default function handler(_req, res) {
  res.status(200).json({
    status: "ok",
    version: 1,
    runtime: "vercel",
    features: ["domains", "domain_filter"],
  });
}
