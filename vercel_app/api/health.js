import { setNoStore } from "../lib/db.js";

export default function handler(_req, res) {
  setNoStore(res);
  res.status(200).json({
    status: "ok",
    version: 2,
    runtime: "vercel",
    features: ["domains", "domain_filter", "no_store", "latest_signal_state"],
  });
}
