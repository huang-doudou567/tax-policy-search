/**
 * POST /api/search — Search tax policies
 */
import { searchTax, searchChinatax, detectIntent, resolveTaxType, INTENT_LABELS, jsonResponse, errorResponse } from "../_utils.js";

export async function onRequestPost({ request }) {
  try {
    const data = await request.json();
    const keyword = (data.keyword || "").trim();
    if (!keyword) return errorResponse("keyword required", 400);

    const scope = data.scope || "fulltext";
    const exact = !!data.exact;
    const status = data.status !== undefined ? data.status : 3;
    const dateFrom = data.date_from || null;
    const dateTo = data.date_to || null;
    const size = Math.min(data.size || 20, 50);
    const sort = data.sort || "relevance";
    const source = data.source || "npc";
    const province = data.province || "";

    const intent = detectIntent(keyword);
    const taxTypeInfo = resolveTaxType(keyword);

    let searchResult;
    if (source === "chinatax") {
      searchResult = await searchChinatax(keyword, size);
    } else {
      searchResult = await searchTax(keyword, {
        scope, exact, status, date_from: dateFrom, date_to: dateTo,
        size, sort,
      });
      // If aggregated, also fetch chinatax
      if (source === "aggregated") {
        const chinataxResult = await searchChinatax(keyword, Math.min(size, 10));
        if (chinataxResult.results && chinataxResult.results.length > 0) {
          const items = (searchResult.results || []).map(r => ({ ...r, _source: "npc", _authority_rank: 0 }));
          const ctItems = chinataxResult.results.map(r => ({
            ...r, _source: "chinatax", _authority_rank: 1,
            publish_date: r.date || "",
          }));
          searchResult = {
            ...searchResult,
            total_items: items.length + ctItems.length,
            items: [...items, ...ctItems],
            source_summary: {
              npc: searchResult.total || 0,
              chinatax: chinataxResult.total || 0,
              anysearch: 0,
            },
          };
        }
      }
    }

    return jsonResponse({
      keyword,
      intent,
      province,
      intent_label: INTENT_LABELS[intent] || intent,
      tax_type: taxTypeInfo ? taxTypeInfo.type : null,
      tax_type_aliases: taxTypeInfo ? taxTypeInfo.aliases : [],
      result: searchResult,
    });
  } catch (e) {
    return errorResponse(e.message, 500);
  }
}
