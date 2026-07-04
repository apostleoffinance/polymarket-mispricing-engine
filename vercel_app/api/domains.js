import {
  DOMAINS,
  fetchBacktestByDomain,
  fetchLiveByDomain,
  sendError,
  sql,
} from "../lib/db.js";

export default async function handler(_req, res) {
  try {
    const db = sql();
    const live = await fetchLiveByDomain(db);
    const { latestRunId, rows: backtest } = await fetchBacktestByDomain(db);

    const categories = [...new Set([...Object.keys(live), ...Object.keys(backtest), ...DOMAINS])]
      .filter((domain) => domain !== "unknown")
      .sort();

    if (live.unknown || backtest.unknown) {
      categories.push("unknown");
    }

    res.status(200).json({
      categories,
      live,
      backtest,
      latest_run_id: latestRunId,
    });
  } catch (error) {
    sendError(res, error);
  }
}
