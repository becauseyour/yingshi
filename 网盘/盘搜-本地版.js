// @name 盘搜
// @author becauseyour
// @description 对接本地盘搜，搜索网盘分享链接
// @version 1.4.0
// @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%BD%91%E7%9B%98/%E7%9B%98%E6%90%9C.js

const OmniBox = require("omnibox_sdk");

// ==================== 配置 ====================
const PANSOU_API = process.env.PANSOU_API || "http://192.168.2.1:17080";

function detectType(url) {
  if (!url) return "other";
  const u = String(url).toLowerCase();
  if (u.includes("baidu.com") || u.includes("pan.baidu")) return "baidu";
  if (u.includes("quark.cn") || u.includes("quark")) return "quark";
  if (u.includes("aliyundrive") || u.includes("alipan") || u.includes("aliyun")) return "aliyun";
  if (u.includes("189.cn") || u.includes("cloud.189")) return "tianyi";
  if (u.includes("115.com") || u.includes("anxia")) return "115";
  if (u.includes("123pan") || u.includes("123yun") || /\/123/.test(u)) return "123";
  if (u.includes("caiyun.139") || u.includes("139.com")) return "mobile";
  if (u.includes("uc.cn") || u.includes("drive.uc")) return "uc";
  if (u.includes("xunlei") || u.includes("thunder")) return "xunlei";
  return "other";
}

async function searchPansou(keyword) {
  const url = `${PANSOU_API}/api/search`;
  OmniBox.log("info", `[盘搜] 搜索 ${keyword} -> ${url}`);

  const res = await OmniBox.request(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      kw: keyword,
      res: "merge",
      src: "all",
    }),
  });

  let body = res.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch (e) { body = {}; }
  }

  // 兼容多种返回结构
  const data = body?.data || body || {};
  return data;
}

async function home(params) {
  return {
    class: [{ type_id: "search", type_name: "搜索" }],
    list: [],
    filters: {},
  };
}

async function category(params) {
  return { list: [], page: 1, pagecount: 0, total: 0 };
}

async function search(params) {
  const keyword = (params.keyword || params.wd || params.key || "").trim();
  const page = parseInt(params.page || "1", 10);

  if (!keyword || page > 1) {
    return { list: [], page, pagecount: 1, total: 0 };
  }

  try {
    const data = await searchPansou(keyword);
    const list = [];

    // 优先使用 merged_by_type（推荐格式）
    const merged = data.merged_by_type || data.mergedByType || {};
    for (const [type, items] of Object.entries(merged)) {
      if (!Array.isArray(items)) continue;
      for (const item of items) {
        const url = item.url || item.link;
        if (!url) continue;
        list.push({
          vod_id: url,
          vod_name: item.note || item.title || keyword,
          vod_pic: (item.images && item.images[0]) || "",
          vod_remarks: type + (item.password ? ` 提取码:${item.password}` : ""),
          vod_tag: type,
        });
      }
    }

    // 如果没有 merged，再尝试 results
    if (list.length === 0 && Array.isArray(data.results)) {
      for (const item of data.results) {
        const links = item.links || [];
        for (const lk of links) {
          const url = lk.url || lk.link;
          if (!url) continue;
          list.push({
            vod_id: url,
            vod_name: item.title || keyword,
            vod_pic: (item.images && item.images[0]) || "",
            vod_remarks: (lk.type || detectType(url)) + (lk.password ? ` 提取码:${lk.password}` : ""),
            vod_tag: lk.type || detectType(url),
          });
        }
      }
    }

    OmniBox.log("info", `[盘搜] 找到 ${list.length} 条`);
    return { list, page: 1, pagecount: 1, total: list.length };
  } catch (e) {
    OmniBox.log("error", `[盘搜] 搜索失败: ${e.message || e}`);
    return { list: [], page: 1, pagecount: 0, total: 0 };
  }
}

async function detail(params) {
  const id = params.id || params.vod_id || "";
  if (!id) return { list: [] };

  const typ = detectType(id);
  return {
    list: [
      {
        vod_id: id,
        vod_name: id.split("/").pop() || "分享链接",
        vod_pic: "",
        vod_remarks: typ,
        vod_play_sources: [
          {
            name: typ,
            episodes: [{ name: "打开分享链接", playId: id }],
          },
        ],
      },
    ],
  };
}

async function play(params) {
  const url = params.playId || params.id || params.url || "";
  if (!url) return { parse: 0, url: "" };

  // 直接返回分享链接，由 OmniBox 网盘模块解析
  return {
    parse: 0,
    url: url,
    header: {},
  };
}

module.exports = { home, category, search, detail, play };

const runner = require("spider_runner");
runner.run(module.exports);
