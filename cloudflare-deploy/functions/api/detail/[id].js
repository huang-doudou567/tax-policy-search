/**
 * GET /api/detail/:id
 */
import { fetchDetail, jsonResponse, errorResponse } from "../../_utils.js";

export async function onRequest({ params }) {
  try {
    const detail = await fetchDetail(params.id);
    if (!detail.title) return errorResponse("Law not found", 404);
    return jsonResponse({ detail });
  } catch (e) {
    return errorResponse(e.message, 500);
  }
}
