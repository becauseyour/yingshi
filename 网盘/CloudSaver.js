// @name CloudSaver
// @author becauseyour
// @description 对接本地/自建 CloudSaver，搜索网盘分享链接（支持百度/夸克/阿里/115/天翼等）
// @version 1.0.1
// @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%BD%91%E7%9B%98/CloudSaver.js

const OmniBox = require("omnibox_sdk");

// ==================== 配置（已按你的本地 CloudSaver 填好） ====================
// 优先环境变量，没有则用下面默认值
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
    body: JSON.stringify({ username: CLOUDSAVER_USER, password: CLOUDSAVER_PASS }),
  });
  let body = res.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch (e) { body = {}; }
  }
  // 兼容多种返回结构
  const token = body?.data?.token || body?.token || body?.data?.accessToken;
  if (!token) {
    throw new Error("登录失败: " + JSON.stringify(body).slice(0, 300));
  }
  _token = token;
  _tokenExpire = Date.now() + 5 * 60 * 60 * 1000; // 5小时
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
  let body = res.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch (e) { body = {}; }
  }
  // 兼容 data / data.list / 直接数组
  if (Array.isArray(body)) return body;
  if (body?.data) {
    if (Array.isArray(body.data)) return body.data;
    if (Array.isArray(body.data.list)) return body.data.list;
    if (Array.isArray(body.data.results)) return body.data.results;
  }
  return [];
}

function detectType(url) {
  if (!url) return "unknown";
  const u = url.toLowerCase();
  if (u.includes("baidu.com") || u.includes("pan.baidu")) return "baidu";
  if (u.includes("quark.cn") || u.includes("quark")) return "quark";
  if (u.includes("aliyundrive") || u.includes("alipan") || u.includes("aliyun")) return "aliyun";
  if (u.includes("189.cn") || u.includes("cloud.189")) return "tianyi";
  if (u.includes("115.com") || u.includes("anxia") || u.includes("115cdn")) return "115";
  if (u.includes("123pan") || u.includes("123yun") || /123/.test(u)) return "123";
  if (u.includes("caiyun.139") || u.includes("139.com")) return "mobile";
  if (u.includes("uc.cn") || u.includes("drive.uc")) return "uc";
  if (u.includes("xunlei") || u.includes("thunder")) return "xunlei";
  return "other";
}

function extractLinks(item) {
  const links = [];
  const seen = new Set();

  const push = (url, password) => {
    if (!url || typeof url !== "string" || seen.has(url)) return;
    if (!/^https?:\/\//i.test(url)) return;
    seen.add(url);
    links.push({ url, type: detectType(url), password: password || "" });
  };

  // 优先 cloudLinks（CloudSaver 标准字段）
  if (Array.isArray(item.cloudLinks)) {
    item.cloudLinks.forEach((l) => push(typeof l === "string" ? l : l?.url || l?.link));
  }
  // links 字段
  if (Array.isArray(item.links)) {
    item.links.forEach((l) => {
      if (typeof l === "string") push(l);
      else if (l && (l.url || l.link)) push(l.url || l.link, l.password || l.pwd);
    });
  }
  // 单 link
  if (item.link) push(item.link);

  // 从 content / description / title 再抓一遍
  const text = [item.content, item.description, item.title, item.completeTitle]
    .filter(Boolean)
    .join("\n");
  const re = /https?:\/\/[^\s<>"'，。！？、]+/gi;
  let m;
  while ((m = re.exec(text))) {
    const u = m[0].replace(/[.,;!?)]+$/, "");
    if (/pan\.|quark|baidu|aliyun|189\.cn|115|123|caiyun|uc\.cn|xunlei/.test(u)) {
      push(u);
    }
  }

  return links;
}

async function home(params) {
  return {
    class: [{ type_id: "search", type_name: "搜索网盘" }],
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
  if (!keyword) {
    return { list: [], page: 1, pagecount: 0, total: 0 };
  }
  if (page > 1) {
    return { list: [], page, pagecount: 1, total: 0 };
  }

  try {
    const raw = await searchCloud(keyword);
    const list = [];
    for (const item of raw) {
      const links = extractLinks(item);
      if (!links.length) continue;
      const title = item.title || item.completeTitle || item.name || keyword;
      const pic = item.image || (item.images && item.images[0]) || "";
      for (const lk of links) {
        list.push({
          vod_id: lk.url,
          vod_name: title,
          vod_pic: pic,
          vod_remarks: lk.type + (lk.password ? ` 提取码:${lk.password}` : ""),
          vod_tag: lk.type,
        });
      }
    }
    OmniBox.log("info", `[CloudSaver] 找到 ${list.length} 条`);
    return { list, page: 1, pagecount: 1, total: list.length };
  } catch (e) {
    OmniBox.log("error", `[CloudSaver] 搜索失败: ${e.message || e}`);
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
  // 直接返回分享链接，由 OmniBox 网盘模块解析播放
  return {
    parse: 0,
    url: url,
    header: {},
  };
}

module.exports = { home, category, search, detail, play };

const runner = require("spider_runner");
runner.run(module.exports);
