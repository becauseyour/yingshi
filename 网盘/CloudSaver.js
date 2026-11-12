// @name CloudSaver
// @author 
// @description 对接本地 CloudSaver，搜索网盘分享链接
// @version 1.0.0
// @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%BD%91%E7%9B%98/CloudSaver.js

const OmniBox = require("omnibox_sdk");

// ==================== 配置 ====================
// 优先环境变量，没有则用默认值（本地 CloudSaver）
const CLOUDSAVER_API = process.env.CLOUDSAVER_API || "http://192.168.2.1:6683";
const CLOUDSAVER_USER = process.env.CLOUDSAVER_USER || "root";
const CLOUDSAVER_PASS = process.env.CLOUDSAVER_PASS || "chen120qi";

let _token = null;
let _tokenExpire = 0;

async function login() {
  if (_token && Date.now() < _tokenExpire) {
    return _token;
  }
  const url = `${CLOUDSAVER_API}/api/user/login`;
  OmniBox.log("info", `[CloudSaver] 登录 ${url}`);
  const res = await OmniBox.request(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: { username: CLOUDSAVER_USER, password: CLOUDSAVER_PASS },
  });
  const body = typeof res.body === "string" ? JSON.parse(res.body) : res.body;
  if (!body || !body.data || !body.data.token) {
    throw new Error("登录失败: " + JSON.stringify(body).slice(0, 200));
  }
  _token = body.data.token;
  _tokenExpire = Date.now() + 5 * 60 * 60 * 1000; // 5h
  OmniBox.log("info", "[CloudSaver] 登录成功");
  return _token;
}

async function searchCloud(keyword) {
  const token = await login();
  const url = `${CLOUDSAVER_API}/api/search?keyword=${encodeURIComponent(keyword)}`;
  OmniBox.log("info", `[CloudSaver] 搜索 ${keyword}`);
  const res = await OmniBox.request(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });
  const body = typeof res.body === "string" ? JSON.parse(res.body) : res.body;
  return body && body.data ? body.data : [];
}

function extractLinks(item) {
  const links = [];
  if (Array.isArray(item.links)) {
    for (const l of item.links) {
      if (typeof l === "string") links.push({ url: l, type: detectType(l) });
      else if (l && l.url) links.push({ url: l.url, type: l.type || detectType(l.url), password: l.password });
    }
  }
  const text = (item.content || "") + " " + (item.title || "");
  const re = /https?:\/\/[^\s<>"']+/g;
  let m;
  while ((m = re.exec(text))) {
    const u = m[0];
    if (/pan\.|quark|baidu|aliyun|189\.cn|115|123|caiyun/.test(u) && !links.some((x) => x.url === u)) {
      links.push({ url: u, type: detectType(u) });
    }
  }
  return links;
}

function detectType(url) {
  if (!url) return "unknown";
  if (url.includes("baidu.com")) return "baidu";
  if (url.includes("quark.cn")) return "quark";
  if (url.includes("aliyundrive") || url.includes("alipan")) return "aliyun";
  if (url.includes("189.cn")) return "tianyi";
  if (url.includes("115.com") || url.includes("anxia")) return "115";
  if (url.includes("123")) return "123";
  if (url.includes("caiyun.139")) return "mobile";
  return "other";
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
  const keyword = (params.keyword || params.wd || "").trim();
  const page = parseInt(params.page || "1", 10);
  if (!keyword || page > 1) {
    return { list: [], page, pagecount: 1, total: 0 };
  }

  try {
    const raw = await searchCloud(keyword);
    const list = [];
    const arr = Array.isArray(raw) ? raw : raw.list || raw.results || [];
    for (const item of arr) {
      const links = extractLinks(item);
      if (!links.length) continue;
      const title = item.title || item.name || keyword;
      const pic = (item.images && item.images[0]) || "";
      for (const lk of links) {
        list.push({
          vod_id: lk.url,
          vod_name: title,
          vod_pic: pic,
          vod_remarks: lk.type,
          vod_tag: lk.type,
        });
      }
    }
    OmniBox.log("info", `[CloudSaver] 找到 ${list.length} 条`);
    return { list, page: 1, pagecount: 1, total: list.length };
  } catch (e) {
    OmniBox.log("error", `[CloudSaver] 搜索失败: ${e.message}`);
    return { list: [], page: 1, pagecount: 0, total: 0 };
  }
}

async function detail(params) {
  const id = params.id || params.vod_id || "";
  if (!id) return { list: [] };
  return {
    list: [
      {
        vod_id: id,
        vod_name: id.split("/").pop() || "分享链接",
        vod_pic: "",
        vod_remarks: detectType(id),
        vod_play_sources: [
          {
            name: detectType(id),
            episodes: [{ name: "打开链接", playId: id }],
          },
        ],
      },
    ],
  };
}

async function play(params) {
  const url = params.playId || params.id || params.url || "";
  if (!url) return { parse: 0, url: "" };
  return {
    parse: 0,
    url: url,
    header: {},
  };
}

module.exports = { home, category, search, detail, play };

const runner = require("spider_runner");
runner.run(module.exports);
