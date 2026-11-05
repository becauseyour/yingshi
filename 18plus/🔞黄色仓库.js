// @name 黄色仓库
// @version 1.3.1
// @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/🔞黄色仓库.js
// @description 黄色仓库采集：镜像池 + 仅 m3u8 直链

const OmniBox = require("omnibox_sdk");

const API_POOL = [
  "https://api.hsckzy.vip/api.php/provide/vod",
  "https://hsckzy.vip/api.php/provide/vod",
  "https://hsckzy888.com/api.php/provide/vod",
  "https://hsckzy001.com/api.php/provide/vod",
  "https://hsckzy.net/api.php/provide/vod",
  "https://cj.hsckzy.vip/api.php/provide/vod",
  "https://hszyckapi.vip/api.php/provide/vod",
];
const SITE_API = process.env.SITE_API || API_POOL[0];
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
const PLAY_HEADER = {
  "User-Agent": UA,
  Referer: "https://hsckzy.vip/",
  Origin: "https://hsckzy.vip",
};

let _api = SITE_API;

function toInt(v) {
  const n = parseInt(v, 10);
  return isNaN(n) ? 0 : n;
}

async function requestSiteAPI(params = {}) {
  const bases = [_api].concat(API_POOL.filter((x) => x !== _api));
  let lastErr = null;
  for (const base of bases) {
    try {
      const url = new URL(base);
      Object.keys(params).forEach((k) => {
        if (params[k] !== undefined && params[k] !== null && params[k] !== "") {
          url.searchParams.append(k, params[k]);
        }
      });
      OmniBox.log("info", `请求: ${url.toString()}`);
      const response = await OmniBox.request(url.toString(), {
        method: "GET",
        headers: { "User-Agent": UA, Accept: "application/json" },
        timeout: 15,
      });
      if (response.statusCode !== 200) {
        lastErr = new Error(`HTTP ${response.statusCode}`);
        continue;
      }
      const data = JSON.parse(response.body || "{}");
      if (data && (data.list || data.class || data.code === 1 || data.code === 200)) {
        _api = base;
        return data;
      }
      lastErr = new Error("empty payload");
    } catch (e) {
      lastErr = e;
      OmniBox.log("warn", `镜像失败 ${base}: ${e.message}`);
    }
  }
  throw lastErr || new Error("全部镜像失败");
}

function card(item) {
  return {
    vod_id: String(item.vod_id || ""),
    vod_name: String(item.vod_name || ""),
    vod_pic: String(item.vod_pic || ""),
    type_name: String(item.type_name || ""),
    vod_remarks: String(item.vod_remarks || ""),
    vod_year: String(item.vod_year || ""),
  };
}

function toM3u8(url) {
  if (!url) return "";
  let u = String(url).trim();
  // share 页转直链
  const m = u.match(/\/share\/([^?&#]+)/i);
  if (m && !/\.m3u8/i.test(u)) {
    return `https://hsm3.hwzcfz.com/${m[1].replace(/\/+$/, "")}/index.m3u8`;
  }
  return u;
}

function isMedia(url) {
  return /\.(m3u8|mp4)(\?|$)/i.test(url || "") || /\/index\.m3u8/i.test(url || "");
}

function convertToPlaySources(vodPlayFrom, vodPlayUrl) {
  const names = String(vodPlayFrom || "")
    .split("$$$")
    .map((s) => s.trim())
    .filter(Boolean);
  const urls = String(vodPlayUrl || "")
    .split("$$$")
    .map((s) => s.trim())
    .filter(Boolean);
  const sources = [];
  const n = Math.max(names.length, urls.length);
  for (let i = 0; i < n; i++) {
    const sourceName = names[i] || `线路${i + 1}`;
    const block = urls[i] || "";
    const episodes = [];
    for (const seg of block.split("#")) {
      const s = seg.trim();
      if (!s) continue;
      let name, playId;
      if (s.includes("$")) {
        const idx = s.indexOf("$");
        name = s.slice(0, idx).trim() || "正片";
        playId = toM3u8(s.slice(idx + 1).trim());
      } else {
        name = "正片";
        playId = toM3u8(s);
      }
      if (playId) episodes.push({ name, playId });
    }
    if (episodes.length) {
      sources.push({ name: sourceName.replace(/-\d+$/, ""), episodes });
    }
  }
  // m3u8 优先
  sources.sort((a, b) => {
    const au = (a.episodes[0] || {}).playId || "";
    const bu = (b.episodes[0] || {}).playId || "";
    return (isMedia(au) ? 0 : 1) - (isMedia(bu) ? 0 : 1);
  });
  // 若存在 m3u8，丢掉非媒体线路，减少点到 share 页
  const media = sources.filter((s) => isMedia((s.episodes[0] || {}).playId || ""));
  return media.length ? media : sources;
}

async function home() {
  try {
    const response = await requestSiteAPI({ ac: "list", pg: "1" });
    const classes = (response.class || []).map((c) => ({
      type_id: String(c.type_id || ""),
      type_name: String(c.type_name || ""),
    })).filter((c) => c.type_id && c.type_name);
    const list = (response.list || []).map(card).filter((x) => x.vod_id);
    return { class: classes, list, filters: {} };
  } catch (e) {
    OmniBox.log("error", `home: ${e.message}`);
    return { class: [], list: [], filters: {} };
  }
}

async function category(params) {
  try {
    const tid = String((params && params.categoryId) || "");
    const page = toInt((params && params.page) || 1) || 1;
    const response = await requestSiteAPI({
      ac: "videolist",
      t: tid,
      pg: String(page),
    });
    return {
      list: (response.list || []).map(card).filter((x) => x.vod_id),
      page: toInt(response.page) || page,
      pagecount: toInt(response.pagecount) || page,
      limit: toInt(response.limit) || 20,
      total: toInt(response.total) || 0,
    };
  } catch (e) {
    OmniBox.log("error", `category: ${e.message}`);
    return { list: [], page: 1, pagecount: 0, limit: 20, total: 0 };
  }
}

async function detail(params) {
  try {
    const videoId = String((params && params.videoId) || "");
    if (!videoId) return { list: [] };
    const response = await requestSiteAPI({ ac: "detail", ids: videoId });
    const item = (response.list || [])[0];
    if (!item) return { list: [] };
    const sources = convertToPlaySources(item.vod_play_from, item.vod_play_url);
    return {
      list: [
        {
          vod_id: String(item.vod_id || videoId),
          vod_name: String(item.vod_name || ""),
          vod_pic: String(item.vod_pic || ""),
          type_name: String(item.type_name || ""),
          vod_year: String(item.vod_year || ""),
          vod_remarks: String(item.vod_remarks || ""),
          vod_actor: String(item.vod_actor || ""),
          vod_content: String(item.vod_content || "").replace(/<[^>]+>/g, ""),
          vod_play_sources: sources,
        },
      ],
    };
  } catch (e) {
    OmniBox.log("error", `detail: ${e.message}`);
    return { list: [] };
  }
}

async function search(params) {
  try {
    const keyword = String((params && (params.keyword || params.wd)) || "").trim();
    const page = toInt((params && params.page) || 1) || 1;
    if (!keyword) return { list: [], page: 1, pagecount: 0, total: 0 };
    const response = await requestSiteAPI({
      ac: "list",
      wd: keyword,
      pg: String(page),
    });
    return {
      list: (response.list || []).map(card).filter((x) => x.vod_id),
      page: toInt(response.page) || page,
      pagecount: toInt(response.pagecount) || page,
      total: toInt(response.total) || 0,
    };
  } catch (e) {
    OmniBox.log("error", `search: ${e.message}`);
    return { list: [], page: 1, pagecount: 0, total: 0 };
  }
}

async function play(params) {
  try {
    let playId = String((params && (params.playId || params.url)) || "").trim();
    if (!playId) return { urls: [], parse: 0, header: PLAY_HEADER };
    playId = toM3u8(playId);
    const media = isMedia(playId);
    return {
      urls: [{ name: "播放", url: playId }],
      parse: media ? 0 : 1,
      header: PLAY_HEADER,
    };
  } catch (e) {
    OmniBox.log("error", `play: ${e.message}`);
    return { urls: [], parse: 0, header: PLAY_HEADER };
  }
}

module.exports = { home, category, detail, search, play };
