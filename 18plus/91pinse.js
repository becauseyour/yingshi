// @name 91pinse.com
// @version 1.3.0
// @description 91pinse.com 爬虫：最新/热门/榜单/搜索；播放走官方 playback API 取 m3u8
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/91pinse.js
// @changelog v1.3.0 去掉失效 hop 代理；详情去掉尾斜杠；play 直调 /api/videos/{id}/playback
// @changelog v1.2.0 双端分流：Web用sniffVideo，客户端embed+parse:1
// @dependencies cheerio
// @downloadURL https://raw.githubusercontent.com/GD2021/omnibox_rules/refs/heads/main/NEW/91pinse.js

const OmniBox = require("omnibox_sdk");
const cheerio = require("cheerio");
const runner = require("spider_runner");

const HOST = "https://91pinse.com";
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";

const CLASSES = [
  { type_id: "latest", type_name: "最新视频" },
  { type_id: "hot", type_name: "热门视频" },
  { type_id: "rank", type_name: "热门榜单" },
];

function log(level, msg) {
  try {
    OmniBox.log(level, "[91pinse] " + msg);
  } catch (_) {}
}

function cleanText(html) {
  return String(html || "")
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function absUrl(url) {
  const v = String(url || "").trim();
  if (!v) return "";
  if (v.startsWith("//")) return "https:" + v;
  if (/^https?:\/\//i.test(v)) return v;
  if (v.startsWith("/")) return HOST + v;
  return HOST + "/" + v.replace(/^\/+/, "");
}

function processImageUrl(imageUrl) {
  return absUrl(imageUrl);
}

async function httpGet(url, referer) {
  const headers = {
    "User-Agent": UA,
    Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    Connection: "keep-alive",
    Referer: referer || HOST + "/",
  };
  const res = await OmniBox.request(url, { method: "GET", headers, timeout: 15000 });
  const status = Number(res?.statusCode || 0);
  if (status && (status < 200 || status >= 400)) {
    throw new Error("HTTP " + status + " @ " + url);
  }
  return String(res?.body || "");
}

async function httpPostJson(url, bodyObj, referer) {
  const headers = {
    "User-Agent": UA,
    Accept: "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    Origin: HOST,
    Referer: referer || HOST + "/",
  };
  const res = await OmniBox.request(url, {
    method: "POST",
    headers,
    body: JSON.stringify(bodyObj || {}),
    timeout: 15000,
  });
  const status = Number(res?.statusCode || 0);
  if (status && (status < 200 || status >= 400)) {
    throw new Error("HTTP " + status + " @ " + url);
  }
  const text = String(res?.body || "");
  try {
    return JSON.parse(text);
  } catch (_) {
    return {};
  }
}

function parseList(html) {
  const $ = cheerio.load(html);
  const list = [];
  const seenIds = {};

  $("div.group").each(function () {
    const $group = $(this);
    const $a = $group.find("a[href*='/v/']").first();
    if (!$a.length) return;

    const href = $a.attr("href") || "";
    const idMatch = href.match(/\/v\/(\d+)/);
    if (!idMatch) return;
    const id = idMatch[1];
    if (id.length < 5) return;
    if (seenIds[id]) return;
    seenIds[id] = true;

    const $img = $group.find("img").first();
    const title = cleanText($img.attr("alt") || $a.attr("title") || "");
    const remarks = cleanText($group.find("span").first().text() || "");
    const pic = processImageUrl($img.attr("src") || $img.attr("data-src") || "");

    list.push({
      vod_id: id,
      vod_name: title || "Video " + id,
      vod_pic: pic,
      type_id: "latest",
      type_name: "最新视频",
      vod_remarks: remarks,
      vod_year: "",
      vod_director: "",
      vod_actor: "",
      vod_content: "",
    });
  });

  // 兜底：任意 /v/{id} 卡片
  if (!list.length) {
    $("a[href*='/v/']").each(function () {
      const href = $(this).attr("href") || "";
      const idMatch = href.match(/\/v\/(\d{5,})/);
      if (!idMatch) return;
      const id = idMatch[1];
      if (seenIds[id]) return;
      seenIds[id] = true;
      const $img = $(this).find("img").first();
      list.push({
        vod_id: id,
        vod_name: cleanText($img.attr("alt") || $(this).attr("title") || "") || "Video " + id,
        vod_pic: processImageUrl($img.attr("src") || ""),
        type_id: "latest",
        type_name: "最新视频",
        vod_remarks: "",
      });
    });
  }

  return list;
}

function parsePageCount(html, currentPage) {
  const pages = [];
  const re = /[?&]page=(\d+)/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    const n = parseInt(m[1], 10);
    if (n > 0) pages.push(n);
  }
  const textPages = [];
  const re2 = /(\d{1,6})\s*页/g;
  while ((m = re2.exec(html)) !== null) textPages.push(parseInt(m[1], 10));

  const maxLink = pages.length ? Math.max.apply(null, pages) : 0;
  const maxText = textPages.length ? Math.max.apply(null, textPages) : 0;
  // 站内分页链接常带一个超大末页数字，优先用合理上限；没有则 current+1
  let pagecount = Math.max(currentPage || 1, maxText || 0);
  if (maxLink > 0 && maxLink < 100000) {
    pagecount = Math.max(pagecount, maxLink > 50000 ? currentPage + 1 : maxLink);
  }
  if (pagecount < (currentPage || 1)) pagecount = currentPage || 1;
  // 列表满页时至少允许翻下一页
  return pagecount;
}

function buildListUrl(categoryId, page) {
  const pg = Math.max(1, Number(page) || 1);
  const id = String(categoryId || "latest");
  let path = "/v/";
  if (id === "hot") path = "/v/hot/";
  else if (id === "rank") path = "/rank/current-hot";
  else if (id === "latest") path = "/v/";
  else path = "/" + id.replace(/^\//, "");

  if (pg > 1) {
    return HOST + path + (path.includes("?") ? "&" : "?") + "page=" + pg;
  }
  return HOST + path;
}

async function home(params, context) {
  try {
    const html = await httpGet(HOST + "/v/");
    const list = parseList(html).slice(0, 24);
    log("info", "home list=" + list.length);
    return { class: CLASSES, list };
  } catch (e) {
    log("error", "home failed: " + e.message);
    return { class: CLASSES, list: [] };
  }
}

async function category(params, context) {
  try {
    const id = String(params.t || params.categoryId || params.id || "latest");
    const pg = parseInt(params.pg || params.page || 1, 10) || 1;
    const url = buildListUrl(id, pg);
    const html = await httpGet(url);
    const list = parseList(html);
    let pagecount = parsePageCount(html, pg);
    if (list.length >= 18) pagecount = Math.max(pagecount, pg + 1);
    log("info", "category id=" + id + " page=" + pg + " list=" + list.length);
    return { list, page: pg, pagecount, total: list.length };
  } catch (e) {
    log("error", "category failed: " + e.message);
    return { list: [], page: 1, pagecount: 1 };
  }
}

async function search(params, context) {
  try {
    const keyword = String(params.keyword || params.wd || "").trim();
    if (!keyword) return { list: [], page: 1, pagecount: 0 };
    const pg = parseInt(params.pg || params.page || 1, 10) || 1;
    let url = HOST + "/v/search?keyword=" + encodeURIComponent(keyword);
    if (pg > 1) url += "&page=" + pg;
    const html = await httpGet(url);
    const list = parseList(html);
    let pagecount = parsePageCount(html, pg);
    if (list.length >= 18) pagecount = Math.max(pagecount, pg + 1);
    log("info", "search kw=" + keyword + " list=" + list.length);
    return { list, page: pg, pagecount, total: list.length };
  } catch (e) {
    log("error", "search failed: " + e.message);
    return { list: [], page: 1, pagecount: 0 };
  }
}

async function detail(params, context) {
  try {
    let id = String(params.videoId || params.id || params.ids || "").trim();
    if (Array.isArray(params.videoId || params.id || params.ids)) {
      id = String((params.videoId || params.id || params.ids)[0] || "");
    }
    // 兼容完整 URL / 带斜杠
    const m = id.match(/\/v\/(\d+)/);
    if (m) id = m[1];
    id = id.replace(/\/+$/, "");
    if (!id) return { list: [] };

    // 注意：尾斜杠会 404，必须是 /v/{id}
    const detailUrl = HOST + "/v/" + id;
    const html = await httpGet(detailUrl, HOST + "/");
    const $ = cheerio.load(html);

    let title =
      cleanText($("meta[property='og:title']").attr("content") || "") ||
      cleanText($("h1").first().text()) ||
      "";
    title = title.replace(/\s*后续完整版请进群\s*$/, "").trim();
    title = title.replace(/\s*-\s*91PinSe.*$/i, "").trim();

    const pic = processImageUrl(
      $("meta[property='og:image']").attr("content") ||
        $("#player").attr("poster") ||
        ""
    );

    let duration = "";
    const jsonLd = (html.match(/"duration"\s*:\s*"([^"]+)"/) || [])[1] || "";
    if (jsonLd) duration = jsonLd.replace(/^PT/i, "").toLowerCase();
    if (!duration) {
      const dm = cleanText($("timer, .duration, [class*=duration]").first().text()).match(
        /(\d+:\d+(?::\d+)?)/
      );
      if (dm) duration = dm[1];
    }

    let author = "";
    const authorMatch = html.match(/href\s*=\s*["']\/v\/author\/[^"']+["'][^>]*>([^<]+)<\/a>/);
    if (authorMatch) author = cleanText(authorMatch[1]);

    return {
      list: [
        {
          vod_id: id,
          vod_name: title || "Video " + id,
          vod_pic: pic,
          type_id: "latest",
          type_name: "最新视频",
          vod_remarks: duration,
          vod_year: "",
          vod_director: "",
          vod_actor: author,
          vod_content: "",
          link: detailUrl,
          vod_play_sources: [
            {
              name: "HLS 线路",
              episodes: [{ name: duration || "播放", playId: id }],
            },
          ],
        },
      ],
    };
  } catch (e) {
    log("error", "detail failed: " + e.message);
    return { list: [] };
  }
}

async function play(params, context) {
  try {
    let raw = String(params.playId || params.url || "").trim();
    if (!raw) return { urls: [], parse: 0, header: {} };

    let id = raw;
    const m = raw.match(/\/v\/(\d+)/);
    if (m) id = m[1];
    id = id.replace(/\/+$/, "");
    // 纯数字 id
    if (!/^\d+$/.test(id)) {
      // 可能是已是直链
      if (/^https?:\/\//i.test(raw) && /\.(m3u8|mp4)(\?|$)/i.test(raw)) {
        return {
          urls: [{ name: "HLS 线路", url: raw }],
          parse: 0,
          header: { "User-Agent": UA, Referer: HOST + "/" },
        };
      }
      return { urls: [], parse: 0, header: {} };
    }

    const detailUrl = HOST + "/v/" + id;
    const apiUrl = HOST + "/api/videos/" + id + "/playback";
    const data = await httpPostJson(apiUrl, {}, detailUrl);
    const playUrl = String(data.url || data.fallback_url || "").trim();

    if (playUrl && /^https?:\/\//i.test(playUrl)) {
      log("info", "play id=" + id + " url=" + playUrl.slice(0, 80));
      return {
        urls: [{ name: "HLS 线路", url: playUrl }],
        parse: 0,
        header: {
          "User-Agent": UA,
          Referer: detailUrl,
          Origin: HOST,
        },
      };
    }

    // 兜底：嗅探详情页
    try {
      const sniff = await OmniBox.sniffVideo(detailUrl, {
        "User-Agent": UA,
        Referer: HOST + "/",
      });
      if (sniff && sniff.url) {
        return {
          urls: [{ name: "HLS 线路", url: sniff.url }],
          parse: 0,
          header: sniff.header || { "User-Agent": UA, Referer: detailUrl },
        };
      }
    } catch (e) {
      log("warn", "sniff fallback failed: " + e.message);
    }

    // 最后透传详情页让客户端解析
    return {
      urls: [{ name: "HLS 线路", url: detailUrl }],
      parse: 1,
      header: { "User-Agent": UA, Referer: HOST + "/" },
    };
  } catch (e) {
    log("error", "play failed: " + e.message);
    return { urls: [], parse: 0, header: {} };
  }
}

module.exports = { home, category, search, detail, play };
runner.run(module.exports);
