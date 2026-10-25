// @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E8%A7%A3%E6%9E%90js/人人影视PRO.js
// @name 人人影视PRO
// @author 梦
// @description 页面解析：首页/分类/播放页已接入；播放页直接解析 Artplayer 的 m3u8 地址与剧集列表
// @dependencies cheerio
// @version 1.1.2
// @downloadURL https://gh-proxy.org/https://github.com/Silent1566/OmniBox-Spider/raw/refs/heads/main/影视/采集/人人影视PRO.js

const OmniBox = require("omnibox_sdk");
const runner = require("spider_runner");
const cheerio = require("cheerio");

const BASE_URL = "https://www.renren.pro";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36";

const CLASS_LIST = [
  { type_id: "all", type_name: "影视库" }
];

const CATEGORY_PATH = {
  all: "/list/all"
};

module.exports = { home, category, detail, search, play };
runner.run(module.exports);

function getBodyText(res) {
  const body = res && typeof res === "object" && "body" in res ? res.body : res;
  if (Buffer.isBuffer(body) || body instanceof Uint8Array) return body.toString();
  return String(body || "");
}

function absUrl(url, base = BASE_URL) {
  const value = String(url || "").trim();
  if (!value) return "";
  if (/^https?:\/\//i.test(value)) return value;
  if (value.startsWith("//")) return `https:${value}`;
  try {
    return new URL(value, /^https?:\/\//i.test(base) ? base : `${BASE_URL}/`).toString();
  } catch {
    if (value.startsWith("/")) return `${BASE_URL}${value}`;
    return `${BASE_URL}/${value.replace(/^\/+/, "")}`;
  }
}

function stripHtml(text) {
  return String(text || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

function dedupeBy(list, keyFn) {
  const seen = new Set();
  const out = [];
  for (const item of list || []) {
    const key = keyFn(item);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

async function fetchText(url, options = {}) {
  const res = await OmniBox.request(url, {
    method: options.method || "GET",
    headers: {
      "User-Agent": UA,
      Referer: options.referer || `${BASE_URL}/`,
      ...(options.headers || {})
    },
    timeout: options.timeout || 20000,
    body: options.body
  });

  if (!res || Number(res.statusCode) < 200 || Number(res.statusCode) >= 400) {
    throw new Error(`HTTP ${res?.statusCode || "unknown"} @ ${url}`);
  }

  return getBodyText(res);
}

function parseVodCards(html) {
  const $ = cheerio.load(html, { decodeEntities: false });
  const list = [];

  $("a[href^='/play/']").each((_, el) => {
    const $a = $(el);
    const href = $a.attr("href") || "";
    if (!/^\/play\//.test(href)) return;

    const title = $a.attr("title") || stripHtml($a.text()) || stripHtml($a.find(".module-poster-item-title, .module-item-title, .title").first().text());
    if (!title) return;

    const card = $a.closest(".module-item, .module-item-cover, .module-list-item, .vod-item, .video-item");
    const img = card.find("img").first().length ? card.find("img").first() : $a.find("img").first();
    const pic = img.attr("data-src") || img.attr("data-original") || img.attr("src") || "";
    const remarks = stripHtml(card.find(".module-item-note, .remarks, .video-serial, .public-list-prb, .module-item-text").first().text());
    const vodId = href.replace(/^\//, "");

    list.push({
      vod_id: vodId,
      vod_name: title,
      vod_pic: absUrl(pic),
      vod_remarks: remarks
    });
  });

  return dedupeBy(list, (item) => item.vod_id);
}

async function resolvePosterByPlayId(playId) {
  const normalizedId = String(playId || "").replace(/^https?:\/\/[^/]+\//, "").replace(/^\//, "");
  if (!normalizedId) return "";

  const pages = [`${BASE_URL}/`, `${BASE_URL}/list/all`];
  for (const url of pages) {
    try {
      const html = await fetchText(url);
      const cards = parseVodCards(html);
      const hit = cards.find((item) => item.vod_id === normalizedId && item.vod_pic);
      if (hit?.vod_pic) return hit.vod_pic;
    } catch (e) {
      await OmniBox.log("warn", `[人人影视][poster] url=${url} message=${e.message}`);
    }
  }
  return "";
}

function parseEpisodeLinks(html, pageUrl) {
  const $ = cheerio.load(html, { decodeEntities: false });
  const list = [];
  $(".module-blocklist a[href^='/play/']").each((_, el) => {
    const $a = $(el);
    const href = $a.attr("href") || "";
    const name = stripHtml($a.text()) || stripHtml($a.attr("title") || "");
    if (!href || !name) return;
    list.push({ name, playId: absUrl(href, pageUrl) });
  });
  return dedupeBy(list, (item) => item.playId);
}

function extractPlayUrl(html) {
  const raw = String(html || "");
  const hit = raw.match(/url:\s*"([^"]+\.m3u8[^"]*)"/i) || raw.match(/url":"([^"]+\.m3u8[^"]*)"/i);
  if (!hit) return "";
  return String(hit[1] || "").replace(/\\\//g, "/").trim();
}

async function home(params, context) {
  try {
    const html = await fetchText(`${BASE_URL}/`);
    const list = parseVodCards(html).slice(0, 40);
    await OmniBox.log("info", `[人人影视][home] list=${list.length}`);
    return { class: CLASS_LIST, list };
  } catch (e) {
    await OmniBox.log("error", `[人人影视][home] ${e.message}`);
    return { class: CLASS_LIST, list: [] };
  }
}

async function category(params, context) {
  try {
    const categoryId = String(params?.categoryId || "all").trim();
    const page = Math.max(1, Number(params?.page || 1) || 1);
    const basePath = CATEGORY_PATH[categoryId] || CATEGORY_PATH.all;
    const url = page > 1 ? `${absUrl(basePath)}?page=${page}` : absUrl(basePath);
    const html = await fetchText(url);
    const list = parseVodCards(html);
    const pageNums = [...html.matchAll(/[?&]page=(\d+)/g)].map((m) => Number(m[1]));
    const pagecount = Math.max(page, ...(pageNums.length ? pageNums : [page]));
    await OmniBox.log("info", `[人人影视][category] category=${categoryId} page=${page} list=${list.length} pagecount=${pagecount}`);
    return { page, pagecount, total: list.length, list };
  } catch (e) {
    await OmniBox.log("error", `[人人影视][category] ${e.message}`);
    return { page: 1, pagecount: 0, total: 0, list: [] };
  }
}

async function detail(params, context) {
  try {
    const videoId = String(params?.videoId || "").trim();
    if (!videoId) return { list: [] };

    const detailUrl = /^https?:\/\//i.test(videoId) ? videoId : `${BASE_URL}/${videoId.replace(/^\//, "")}`;
    const html = await fetchText(detailUrl);
    const $ = cheerio.load(html, { decodeEntities: false });

    const pageTitle = stripHtml($("title").first().text());
    const vodName = stripHtml($(".title-link").first().text()) || pageTitle.replace(/\s*-\s*第\d+集.*$/, "").replace(/\s*-\s*免费在线观看.*$/, "").trim();
    const poster = $(".video-cover img, .module-item-pic img, img").first();
    let vodPic = absUrl(poster.attr("data-src") || poster.attr("src") || "");
    if (!vodPic || /\/public\/statics\/images\/renren\.png$/i.test(vodPic) || /\/public\/.+\.gif$/i.test(vodPic)) {
      vodPic = await resolvePosterByPlayId(videoId);
    }
    const tagList = $(".video-info-aux .tag-link").map((_, el) => stripHtml($(el).text())).get().filter(Boolean);
    const typeName = tagList[0] || "";
    const vodLang = tagList[1] || "";
    const vodArea = tagList[2] || "";
    const sideTitle = stripHtml($(".title-info").first().text());
    const metaDesc = stripHtml($("meta[name='description']").attr("content") || "");
    const headings = $("h1, h2, h3, h4").map((_, el) => stripHtml($(el).text())).get().filter(Boolean);
    const episodeMatch = (pageTitle.match(/第\d+集/) || [])[0] || (headings.find((t) => /第\d+集/.test(t)) || "");
    const remarks = [typeName, vodLang, vodArea, episodeMatch].filter(Boolean).join(" · ");
    const vodContent = [sideTitle, metaDesc].filter(Boolean).join("\n");
    const yearMatch = html.match(/20\d{2}/);
    const vodYear = yearMatch ? yearMatch[0] : "";

    const episodes = parseEpisodeLinks(html, detailUrl);
    const vodPlaySources = episodes.length ? [{ name: "在线播放", episodes }] : [];

    await OmniBox.log("info", `[人人影视][detail] videoId=${videoId} episodes=${episodes.length}`);
    return {
      list: [
        {
          vod_id: videoId.replace(/^https?:\/\/[^/]+\//, ""),
          vod_name: vodName,
          vod_pic: vodPic,
          type_name: typeName,
          vod_area: vodArea,
          vod_year: vodYear,
          vod_subtitle: vodLang,
          vod_content: vodContent,
          vod_remarks: remarks,
          vod_play_sources: vodPlaySources
        }
      ]
    };
  } catch (e) {
    await OmniBox.log("error", `[人人影视][detail] ${e.message}`);
    return { list: [] };
  }
}

async function search(params, context) {
  try {
    const keyword = String(params?.keyword || params?.wd || "").trim();
    const page = Math.max(1, Number(params?.page || 1) || 1);
    if (!keyword) return { page, pagecount: 0, total: 0, list: [] };

    const url = `${BASE_URL}/search?wd=${encodeURIComponent(keyword)}`;
    const html = await fetchText(url);
    const list = parseVodCards(html);
    await OmniBox.log("info", `[人人影视][search] keyword=${keyword} list=${list.length}`);
    return { page, pagecount: 1, total: list.length, list };
  } catch (e) {
    await OmniBox.log("error", `[人人影视][search] ${e.message}`);
    return { page: 1, pagecount: 0, total: 0, list: [] };
  }
}

async function play(params, context) {
  try {
    const playId = String(params?.playId || "").trim();
    if (!playId) return { urls: [], parse: 0, header: {} };

    const html = await fetchText(playId, { referer: `${BASE_URL}/` });
    const playUrl = extractPlayUrl(html);
    await OmniBox.log("info", `[人人影视][play] playId=${playId} url=${playUrl}`);

    if (!/^https?:\/\//i.test(playUrl)) {
      return {
        urls: [{ name: "播放页", url: playId }],
        parse: 1,
        header: { "User-Agent": UA, Referer: playId }
      };
    }

    return {
      urls: [{ name: "默认线路", url: playUrl }],
      parse: 0,
      header: { "User-Agent": UA, Referer: playId }
    };
  } catch (e) {
    await OmniBox.log("error", `[人人影视][play] ${e.message}`);
    return { urls: [], parse: 0, header: {} };
  }
}
