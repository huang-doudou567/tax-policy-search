/**
 * GET /api/text/:id — Download and extract full text of a law
 */
import { fetchDetail, extractLawText, jsonResponse, errorResponse } from "../../_utils.js";

export async function onRequest({ params }) {
  try {
    const detail = await fetchDetail(params.id);
    if (!detail.title) return errorResponse("Law not found", 404);

    const { paragraphs, sections } = await extractLawText(params.id);

    const articleCount = sections.filter(s => s.type === "article").length;

    return jsonResponse({
      detail,
      total_paragraphs: paragraphs.length,
      article_count: articleCount,
      sections,
    });
  } catch (e) {
    return errorResponse(e.message, 500);
  }
}
