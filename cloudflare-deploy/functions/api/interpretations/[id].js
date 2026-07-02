/**
 * GET /api/interpretations/:id — Search official policy interpretations
 */
import { fetchDetail, searchInterpretations, jsonResponse, errorResponse } from "../../_utils.js";

export async function onRequest({ params, request }) {
  try {
    const detail = await fetchDetail(params.id);
    if (!detail.title) return errorResponse("Law not found", 404);

    const url = new URL(request.url);
    const keyword = url.searchParams.get("keyword") || "";
    const province = url.searchParams.get("province") || "";

    const result = await searchInterpretations(detail.title, keyword, province);
    result.law_id = params.id;
    return jsonResponse(result);
  } catch (e) {
    return errorResponse(e.message, 500);
  }
}
