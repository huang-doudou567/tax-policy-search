/**
 * Tax Policy Search — Shared Utilities for Cloudflare Workers
 * Replicates core logic from tax_search.py / tax_detail.py / tax_web_search.py
 */

// ── Constants ───────────────────────────────────────────────────────────────
const NPC_BASE = "https://flk.npc.gov.cn";
const HEADERS_NPC = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
  Referer: "https://flk.npc.gov.cn/",
  Accept: "application/json, text/plain, */*",
  "Content-Type": "application/json",
};
const HEADERS_WEB = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
  "Accept-Language": "zh-CN,zh;q=0.9",
  Accept: "text/html,application/xhtml+xml",
};

const SXX_MAP = { 1: "已废止", 2: "已修改", 3: "现行有效", 4: "尚未生效" };

// ── 18 Tax Types ────────────────────────────────────────────────────────────
const TAX_TYPE_KEYWORDS = {
  "增值税": {
    aliases: ["增值税", "VAT", "进项税", "销项税", "留抵退税", "增值税专用发票", "增值税普通发票"],
    parent_law: "中华人民共和国增值税法", priority: 1,
  },
  "消费税": {
    aliases: ["消费税", "卷烟", "成品油", "汽车消费税"],
    parent_law: "中华人民共和国消费税法", priority: 2,
  },
  "关税": {
    aliases: ["关税", "进出口税", "反倾销税", "保税", "海关"],
    parent_law: "中华人民共和国关税法", priority: 3,
  },
  "企业所得税": {
    aliases: ["企业所得税", "应税所得", "税前扣除", "加计扣除", "高新技术企业", "小微企业", "西部大开发"],
    parent_law: "中华人民共和国企业所得税法", priority: 1,
  },
  "个人所得税": {
    aliases: ["个人所得税", "综合所得", "专项附加扣除", "年度汇算", "劳务报酬", "经营所得"],
    parent_law: "中华人民共和国个人所得税法", priority: 1,
  },
  "房产税": {
    aliases: ["房产税", "房地产税", "房屋租赁税"],
    parent_law: "中华人民共和国房产税暂行条例", priority: 4,
  },
  "土地增值税": {
    aliases: ["土地增值税", "土增税", "清算"],
    parent_law: "中华人民共和国土地增值税暂行条例", priority: 4,
  },
  "契税": {
    aliases: ["契税", "不动产登记"],
    parent_law: "中华人民共和国契税法", priority: 4,
  },
  "城镇土地使用税": {
    aliases: ["城镇土地使用税", "土地使用税"],
    parent_law: "中华人民共和国城镇土地使用税暂行条例", priority: 4,
  },
  "车船税": {
    aliases: ["车船税", "车辆购置税"],
    parent_law: "中华人民共和国车船税法", priority: 5,
  },
  "印花税": {
    aliases: ["印花税", "合同印花税", "账簿印花税"],
    parent_law: "中华人民共和国印花税法", priority: 4,
  },
  "城市维护建设税": {
    aliases: ["城市维护建设税", "城建税", "教育费附加", "地方教育附加"],
    parent_law: "中华人民共和国城市维护建设税法", priority: 4,
  },
  "资源税": {
    aliases: ["资源税", "水资源税", "矿产资源税"],
    parent_law: "中华人民共和国资源税法", priority: 4,
  },
  "环境保护税": {
    aliases: ["环境保护税", "环保税", "排污税"],
    parent_law: "中华人民共和国环境保护税法", priority: 4,
  },
  "税收征管": {
    aliases: ["税收征收管理", "税务登记", "纳税申报", "发票管理", "发票", "税务稽查", "金税四期"],
    parent_law: "中华人民共和国税收征收管理法", priority: 1,
  },
  "税收优惠": {
    aliases: ["税收优惠", "减免税", "退税", "即征即退", "先征后退", "免税"],
    parent_law: null, priority: 1,
  },
};

// ── Intent Detection ────────────────────────────────────────────────────────
export function detectIntent(query) {
  const q = query.trim();
  if (/发票|开票|红冲|抵扣认证|发票遗失/.test(q)) return "invoice";
  if (/风险|会不会被查|预警|金税|合规|稽查|会被罚款|合规吗|违规/.test(q)) return "risk_check";
  if (/申报|汇算清缴|截止日期|怎么申报|年度汇算|预缴|报送|备案/.test(q)) return "filing_guide";
  if (/符合条件|能不能享受|符不符合|是否适用|可以抵扣吗|适用吗|资格|能享受|可以享受/.test(q)) return "eligibility";
  return "policy_lookup";
}

export function resolveTaxType(query) {
  const q = query.trim();
  let best = null, bestLen = 0;
  for (const [taxType, info] of Object.entries(TAX_TYPE_KEYWORDS)) {
    for (const alias of info.aliases) {
      if (q.includes(alias) && alias.length > bestLen) {
        best = { type: taxType, matched_alias: alias, ...info };
        bestLen = alias.length;
      }
    }
  }
  return best;
}

// ── NPC API: Search ─────────────────────────────────────────────────────────
export async function searchTax(keyword, opts = {}) {
  const searchRange = opts.scope === "fulltext" ? 2 : 1;
  const searchType = opts.exact ? 1 : 2;
  const status = opts.status !== undefined && opts.status !== null ? opts.status : 3;
  const page = opts.page || 1;
  const size = Math.min(opts.size || 20, 50);
  const sort = opts.sort || "relevance";

  const sxx = status !== null && status !== undefined ? [status] : [];
  let gbrq = [];
  if (opts.date_from && opts.date_to) {
    gbrq = [opts.date_from, opts.date_to];
  } else if (opts.date_from) {
    gbrq = [opts.date_from, "2099-12-31"];
  }

  const sortParam = sort === "date"
    ? { order: "-1", sort: "gbrq" }
    : { order: "", sort: "" };

  const payload = {
    searchRange,
    searchType,
    searchContent: keyword,
    pageNum: page,
    pageSize: size,
    orderByParam: sortParam,
    flfgCodeId: [],
    zdjgCodeId: [],
    sxx,
    gbrq,
    sxrq: [],
    gbrqYear: [],
    xgzlSearch: false,
  };

  const ts = new Date().toISOString().replace("T", " ").slice(0, 19);
  try {
    const r = await fetch(`${NPC_BASE}/law-search/search/list`, {
      method: "POST",
      headers: HEADERS_NPC,
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(`NPC API HTTP ${r.status}`);
    const data = await r.json();
    const outer = data.data || data;
    const total = outer.total || 0;
    const rows = outer.rows || outer.list || [];

    const results = rows.map((item) => ({
      id: item.bbbs || "",
      title: stripHtml(item.flfgname || item.title || ""),
      publish_date: item.gbrq || "",
      effective_date: item.sxrq || "",
      status_code: item.sxx || 0,
      status: SXX_MAP[item.sxx] || `未知(${item.sxx})`,
      issuing_authority: item.zdjgName || "",
      category: item.flxz || "",
    }));

    return {
      keyword, scope: opts.scope || "title",
      search_type: searchType === 1 ? "exact" : "fuzzy",
      total, page, page_size: size,
      results, searched_at: ts, _from_cache: false,
    };
  } catch (e) {
    return {
      keyword, scope: opts.scope || "title",
      search_type: "fuzzy", total: 0, page: 1, page_size: size,
      results: [], searched_at: ts, _from_cache: false, _error: e.message,
    };
  }
}

// ── NPC API: Detail ─────────────────────────────────────────────────────────
export async function fetchDetail(bbbsId) {
  const url = `${NPC_BASE}/law-search/search/flfgDetails?bbbs=${bbbsId}`;
  try {
    const r = await fetch(url, { headers: HEADERS_NPC });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const d = data.data || data;
    return {
      id: bbbsId,
      title: d.title || d.flfgname || "",
      category: d.flxz || "",
      publish_date: d.gbrq || "",
      effective_date: d.sxrq || "",
      status_code: d.sxx || 0,
      status: SXX_MAP[d.sxx] || "未知",
      issuing_authority: d.zdjgName || "",
      oss_files: {
        docx: d.ossWordPath || "",
        pdf: d.ossPdfPath || "",
      },
      content_tree: d.contentTree || [],
      fetched_at: new Date().toISOString().replace("T", " ").slice(0, 19),
    };
  } catch (e) {
    return { id: bbbsId, title: "", error: e.message };
  }
}

// ── NPC: Get Download URL ───────────────────────────────────────────────────
export async function getDownloadUrl(bbbsId, fmt = "docx") {
  const url = `${NPC_BASE}/law-search/download/pc?format=${fmt}&bbbs=${bbbsId}`;
  try {
    const r = await fetch(url, { headers: HEADERS_NPC });
    if (!r.ok) return null;
    const data = await r.json();
    return (data.data && data.data.url) || null;
  } catch {
    return null;
  }
}

// ── Minimal ZIP / DOCX text extractor ───────────────────────────────────────
async function parseDocxText(docxBuffer) {
  try {
    const bytes = new Uint8Array(docxBuffer);
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const len = bytes.length;

    // Find EOCD signature
    function findEocd() {
      for (let i = len - 22; i >= Math.max(0, len - 65557); i--) {
        if (view.getUint32(i, true) === 0x06054b50) {
          return i;
        }
      }
      return -1;
    }

    const eocdOff = findEocd();
    if (eocdOff < 0) return [];

    const cdOff = view.getUint32(eocdOff + 16, true);
    const cdSize = view.getUint32(eocdOff + 12, true);
    const totalEntries = view.getUint16(eocdOff + 10, true);

    // Parse central directory to find word/document.xml
    let targetLocalHeader = -1, targetCompressedSize = 0, targetMethod = 0;

    let pos = cdOff;
    for (let i = 0; i < totalEntries; i++) {
      const sig = view.getUint32(pos, true);
      if (sig !== 0x02014b50) break;

      const method = view.getUint16(pos + 10, true);
      const compressedSize = view.getUint32(pos + 20, true);
      const fileNameLen = view.getUint16(pos + 28, true);
      const extraLen = view.getUint16(pos + 30, true);
      const commentLen = view.getUint16(pos + 32, true);
      const localHeaderOff = view.getUint32(pos + 42, true);

      const nameBytes = bytes.slice(pos + 46, pos + 46 + fileNameLen);
      const name = new TextDecoder().decode(nameBytes);

      if (name === "word/document.xml") {
        targetLocalHeader = localHeaderOff;
        targetCompressedSize = compressedSize;
        targetMethod = method;
        break;
      }

      pos += 46 + fileNameLen + extraLen + commentLen;
    }

    if (targetLocalHeader < 0) return [];

    // Parse local file header
    const lhPos = targetLocalHeader;
    const fileNameLenLocal = view.getUint16(lhPos + 26, true);
    const extraLenLocal = view.getUint16(lhPos + 28, true);
    const dataStart = lhPos + 30 + fileNameLenLocal + extraLenLocal;

    let xmlBytes = bytes.slice(dataStart, dataStart + targetCompressedSize);

    // Decompress if deflated
    if (targetMethod === 8) {
      const ds = new DecompressionStream("deflate");
      const writer = ds.writable.getWriter();
      const reader = ds.readable.getReader();
      writer.write(xmlBytes);
      writer.close();

      const chunks = [];
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
      }
      const totalLen = chunks.reduce((s, c) => s + c.length, 0);
      xmlBytes = new Uint8Array(totalLen);
      let off = 0;
      for (const c of chunks) { xmlBytes.set(c, off); off += c.length; }
    }

    const xml = new TextDecoder().decode(xmlBytes);
    // Extract text from XML paragraphs
    const paragraphs = [];
    const paraRe = /<w:p[ >][\s\S]*?<\/w:p>/g;
    let pm;
    while ((pm = paraRe.exec(xml)) !== null) {
      const texts = [];
      const tRe = /<w:t[^>]*>([^<]*)<\/w:t>/g;
      let tm;
      while ((tm = tRe.exec(pm[0])) !== null) {
        texts.push(tm[1]);
      }
      const para = texts.join("").trim();
      if (para) paragraphs.push(para);
    }
    return paragraphs;
  } catch {
    return [];
  }
}

// ── Extract law text (download + parse) ────────────────────────────────────
export async function extractLawText(bbbsId) {
  // Step 1: Get download URL
  const dlUrl = await getDownloadUrl(bbbsId, "docx");
  if (!dlUrl) return { paragraphs: [], sections: [] };

  // Step 2: Download DOCX
  try {
    const r = await fetch(dlUrl, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        Referer: "https://flk.npc.gov.cn/",
      },
    });
    if (!r.ok) return { paragraphs: [], sections: [] };
    const buf = await r.arrayBuffer();
    const paragraphs = await parseDocxText(buf);

    // Classify
    const chapterRe = /^第[一二三四五六七八九十百千]+章/;
    const articleRe = /^第[一二三四五六七八九十百千\d]+条\s/;
    const headingRe = /^第[一二三四五六七八九十百千]+[章节条]|^目[\s　]*[录录]/;

    const sections = [];
    let currentChapter = "";
    for (const p of paragraphs) {
      if (chapterRe.test(p)) {
        currentChapter = p;
        sections.push({ type: "chapter", text: p });
      } else if (articleRe.test(p)) {
        sections.push({ type: "article", text: p, chapter: currentChapter });
      } else if (headingRe.test(p)) {
        sections.push({ type: "heading", text: p });
      } else {
        sections.push({ type: "body", text: p });
      }
    }
    return { paragraphs, sections };
  } catch {
    return { paragraphs: [], sections: [] };
  }
}

// ── chinatax.gov.cn search ─────────────────────────────────────────────────
export async function searchChinatax(keyword, size = 10) {
  const ts = new Date().toISOString().replace("T", " ").slice(0, 19);
  try {
    const params = new URLSearchParams({
      searchword: keyword,
      keyword: keyword,
      perpage: String(size),
      page: "1",
      orderby: "-crtime",
    });
    const url = `https://www.chinatax.gov.cn/was5/web/search?${params.toString()}`;
    const r = await fetch(url, { headers: HEADERS_WEB });
    if (r.status !== 200) return _baiduFallback(keyword, size);
    const html = await r.text();

    const results = [];
    const seenUrls = new Set();

    // Extract result blocks
    const blockRe = /<(?:li|div)[^>]*(?:class="[^"]*result[^"]*"|class="[^"]*item[^"]*")[^>]*>([\s\S]*?)<\/(?:li|div)>/gi;
    let blocks = [];
    let bm;
    while ((bm = blockRe.exec(html)) !== null) blocks.push(bm[1]);

    if (blocks.length === 0) {
      // Fallback: any li/div with chinatax links
      const allBlocks = [];
      const anyBlockRe = /<(?:li|div)[^>]*>([\s\S]*?)<\/(?:li|div)>/gi;
      let am;
      while ((am = anyBlockRe.exec(html)) !== null) {
        if (am[1].includes("chinatax.gov.cn")) allBlocks.push(am[1]);
      }
      blocks = allBlocks;
    }

    const linkRe = /<a[^>]*href="([^"]*chinatax\.gov\.cn[^"]*)"[^>]*>([\s\S]*?)<\/a>/gi;
    const dateRe = /(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)/;
    const docNumRe = /(国家税务总局公告\d{4}年第\d+号|财税\[\d{4}\]\d+号|税总发\[\d{4}\]\d+号|财政部税务总局\d{4}年第\d+号)/;

    for (const block of blocks) {
      let lm;
      while ((lm = linkRe.exec(block)) !== null) {
        const href = lm[1].trim();
        const titleRaw = lm[2];
        if (seenUrls.has(href)) continue;
        seenUrls.add(href);

        const title = titleRaw.replace(/<[^>]+>/g, "").trim();
        if (title.length < 5) continue;

        const dm = dateRe.exec(block);
        const dateStr = (dm ? dm[1] : "").replace(/年/g, "-").replace(/月/g, "-").replace(/日/g, "");

        const dnm = docNumRe.exec(block);
        const docNum = dnm ? dnm[1] : "";

        results.push({ title, url: href, date: dateStr, document_number: docNum, source: "chinatax.gov.cn" });
        if (results.length >= size) break;
      }
      if (results.length >= size) break;
    }

    return {
      keyword, total: results.length, results,
      searched_at: ts, source: "chinatax.gov.cn", _from_cache: false,
    };
  } catch {
    return { keyword, total: 0, results: [], searched_at: ts, source: "chinatax.gov.cn", _error: "Failed" };
  }
}

async function _baiduFallback(keyword, size) {
  const ts = new Date().toISOString().replace("T", " ").slice(0, 19);
  try {
    const url = `https://www.baidu.com/s?wd=site%3Achinatax.gov.cn+${encodeURIComponent(keyword)}&rn=${size}`;
    const r = await fetch(url, { headers: HEADERS_WEB });
    if (r.status !== 200) return { keyword, total: 0, results: [], searched_at: ts, source: "chinatax.gov.cn" };
    const html = await r.text();
    const linkRe = /<a[^>]*href="(https?:\/\/[^"]*chinatax\.gov\.cn[^"]*)"[^>]*>([\s\S]*?)<\/a>/gi;
    const results = [];
    const seen = new Set();
    let lm;
    while ((lm = linkRe.exec(html)) !== null) {
      const href = lm[1], title = lm[2].replace(/<[^>]+>/g, "").trim();
      if (seen.has(href) || title.length < 5) continue;
      seen.add(href);
      results.push({ title, url: href, source: "chinatax.gov.cn (Baidu)" });
      if (results.length >= size) break;
    }
    return { keyword, total: results.length, results, searched_at: ts, source: "chinatax.gov.cn (Baidu)", _from_cache: false };
  } catch {
    return { keyword, total: 0, results: [], searched_at: ts };
  }
}

// ── Bing interpretation search ──────────────────────────────────────────────
export async function searchInterpretations(lawTitle, keyword = "", province = "") {
  let sources;
  if (province) {
    sources = [`${province}.chinatax.gov.cn`, "chinatax.gov.cn", "www.gov.cn"];
  } else {
    sources = ["chinatax.gov.cn", "fgk.chinatax.gov.cn", "mof.gov.cn", "www.gov.cn"];
  }

  const titleShort = lawTitle.replace("中华人民共和国", "").trim();
  const queries = [
    `${lawTitle} 解读 答记者问`,
    `${titleShort} 政策解读`,
    `${lawTitle} 官方解读`,
  ];
  if (keyword && keyword !== lawTitle) {
    queries.unshift(`${keyword} 政策解读 官方`);
  }

  const allResults = [];
  const seenUrls = new Set();

  // Search each source + query combo (sequential to avoid rate limits)
  const tasks = [];
  for (const site of sources) {
    for (const q of queries.slice(0, 3)) {
      tasks.push(_bingSiteSearch(site, q, 4));
    }
  }

  const resultsPerTask = await Promise.all(tasks);
  for (const items of resultsPerTask) {
    for (const item of items) {
      if (!seenUrls.has(item.url)) {
        seenUrls.add(item.url);
        allResults.push(item);
      }
    }
  }

  return {
    law_title: lawTitle,
    keyword,
    total: allResults.length,
    sources: allResults.slice(0, 12),
    searched_at: new Date().toISOString().replace("T", " ").slice(0, 19),
  };
}

async function _bingSiteSearch(site, query, n = 5) {
  const fullQ = `site:${site} ${query}`;
  const url = `https://www.bing.com/search?q=${encodeURIComponent(fullQ)}&count=${n}`;
  try {
    const r = await fetch(url, { headers: HEADERS_WEB });
    if (r.status !== 200) return [];
    const html = await r.text();

    const blockRe = /<li class="b_algo"[^>]*>([\s\S]*?)<\/li>/gi;
    const results = [];
    let bm;
    while ((bm = blockRe.exec(html)) !== null) {
      const block = bm[1];
      let tm = /<h2[^>]*><a[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a><\/h2>/i.exec(block);
      if (!tm) tm = /<a[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/i.exec(block);
      if (!tm) continue;

      const href = tm[1];
      const title = tm[2].replace(/<[^>]+>/g, "").trim();
      if (!href.includes(site.replace("www.", ""))) continue;
      if (title.length < 5) continue;

      const dm = /(\d{4}[-/]\d{1,2}[-/]\d{1,2})/.exec(block);
      const dateStr = dm ? dm[1] : "";

      let snippet = "";
      const sm = /<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>([\s\S]*?)<\/p>/i.exec(block);
      if (sm) snippet = sm[1].replace(/<[^>]+>/g, "").trim().slice(0, 200);

      results.push({
        title, url: href, date: dateStr,
        source: site,
        source_label: _sourceLabel(site),
        snippet,
      });
      if (results.length >= n) break;
    }
    return results;
  } catch {
    return [];
  }
}

function _sourceLabel(site) {
  const labels = {
    "fgk.chinatax.gov.cn": "税务法规库",
    "chinatax.gov.cn": "国家税务总局",
    "mof.gov.cn": "财政部",
    "npc.gov.cn": "全国人大",
    "gov.cn": "中国政府网",
  };
  for (const [k, v] of Object.entries(labels)) {
    if (site.includes(k)) return v;
  }
  const m = site.match(/^([a-z]+)\.chinatax\.gov\.cn$/);
  if (m) {
    const provNames = {
      beijing: "北京税务", shanghai: "上海税务", tianjin: "天津税务",
      chongqing: "重庆税务", guangdong: "广东税务", shenzhen: "深圳税务",
      zhejiang: "浙江税务", jiangsu: "江苏税务", shandong: "山东税务",
      sichuan: "四川税务", hubei: "湖北税务", hunan: "湖南税务",
      henan: "河南税务", hebei: "河北税务", fujian: "福建税务",
      xiamen: "厦门税务", anhui: "安徽税务", liaoning: "辽宁税务",
      dalian: "大连税务", jilin: "吉林税务", heilongjiang: "黑龙江税务",
      jiangxi: "江西税务", shanxi: "山西税务", shaanxi: "陕西税务",
      gansu: "甘肃税务", qinghai: "青海税务", yunnan: "云南税务",
      guizhou: "贵州税务", guangxi: "广西税务", hainan: "海南税务",
      neimenggu: "内蒙古税务", ningxia: "宁夏税务", xinjiang: "新疆税务",
      xizang: "西藏税务", qingdao: "青岛税务", ningbo: "宁波税务",
    };
    return provNames[m[1]] || `${m[1]}税务`;
  }
  return site;
}

// ── Helpers ─────────────────────────────────────────────────────────────────
function stripHtml(s) {
  if (!s) return "";
  return s.replace(/<[^>]+>/g, "");
}

export function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
    },
  });
}

export function errorResponse(msg, status = 400) {
  return jsonResponse({ error: msg }, status);
}

// Intent label map
export const INTENT_LABELS = {
  policy_lookup: "政策查询",
  filing_guide: "申报指导",
  risk_check: "合规风险",
  eligibility: "资格判定",
  invoice: "发票处理",
};
