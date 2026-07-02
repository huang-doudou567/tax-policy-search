/**
 * GET /api/quick-tax-types
 */
import { jsonResponse } from "../_utils.js";

export function onRequest() {
  return jsonResponse([
    { label: "增值税", icon: "📊", keyword: "增值税" },
    { label: "企业所得税", icon: "🏢", keyword: "企业所得税" },
    { label: "个人所得税", icon: "👤", keyword: "个人所得税" },
    { label: "消费税", icon: "🛒", keyword: "消费税" },
    { label: "关税", icon: "🚢", keyword: "关税" },
    { label: "房产税", icon: "🏠", keyword: "房产税" },
    { label: "印花税", icon: "📝", keyword: "印花税" },
    { label: "契税", icon: "🔑", keyword: "契税" },
    { label: "土地增值税", icon: "🏗️", keyword: "土地增值税" },
    { label: "税收优惠", icon: "🎁", keyword: "税收优惠" },
    { label: "发票管理", icon: "🧾", keyword: "发票管理办法" },
    { label: "税收征管", icon: "⚖️", keyword: "税收征收管理法" },
  ]);
}
