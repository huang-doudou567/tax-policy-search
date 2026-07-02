/**
 * GET /api/health
 */
import { jsonResponse } from "../_utils.js";

export function onRequest() {
  return jsonResponse({ status: "ok", time: new Date().toISOString().replace("T", " ").slice(0, 19) });
}
