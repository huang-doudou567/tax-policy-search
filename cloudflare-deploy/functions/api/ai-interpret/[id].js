/**
 * GET /api/ai-interpret/:id — AI interpretation (demo mode)
 */
import { fetchDetail, jsonResponse, errorResponse } from "../../_utils.js";

export async function onRequest({ params, request }) {
  try {
    const detail = await fetchDetail(params.id);
    if (!detail.title) return errorResponse("Law not found", 404);

    const url = new URL(request.url);
    const keyword = url.searchParams.get("keyword") || "";
    const ts = new Date().toISOString().replace("T", " ").slice(0, 19);

    return jsonResponse({
      law_id: params.id,
      law_title: detail.title,
      keyword,
      interpretation: `## Demo 限制\n\nAI 解读功能在在线 Demo 中暂不可用。\n\n**原因**：AI 解读需要 Claude Code CLI 本地运行环境，无法在 Cloudflare Workers 中使用。\n\n**如需体验完整功能**，请克隆项目到本地运行：\n\n\`\`\`bash\ncd tax-policy-search\npip install flask requests urllib3\npython scripts/tax_server.py\n# 浏览器访问 http://localhost:5080\n\`\`\`\n\n## 适用主体\n建议查看「法规原文」和「官方解读」标签页获取权威信息。\n\n## 核心要点\n- 本 Demo 连接 NPC 国家法律法规数据库实时查询\n- 可浏览法规原文、章节结构、法条分类\n- 可搜索国家税务总局、财政部等官方解读\n- 支持多数据源聚合搜索`,
      model: "Demo (AI 不可用)",
      generated_at: ts,
      disclaimer: "AI 生成内容仅供参考，以官方政策文件和主管税务机关解释为准。",
    });
  } catch (e) {
    return errorResponse(e.message, 500);
  }
}
