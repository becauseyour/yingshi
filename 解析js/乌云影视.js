// @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E8%A7%A3%E6%9E%90js/乌云影视.js
// @name 乌云影视
// @author 梦
// @description 刮削：未接入，弹幕：站内弹幕接口，嗅探：不需要
// @dependencies
// @version 1.1.3
// @downloadURL https://gh-proxy.org/https://github.com/Silent1566/OmniBox-Spider/raw/refs/heads/main/影视/采集/乌云影视.js

const OmniBox = require("omnibox_sdk");
const runner = require("spider_runner");

const SITE = "https://wooyun.tv";
const DEFAULT_PAGE_SIZE = 24;
const DEFAULT_HOME_LIMIT = 12;

const SORT_OPTIONS = [
  { name: "默认", value: "default" },
  { name: "最新", value: "latest" },
  { name: "最热", value: "hot" },
  { name: "评分", value: "score" },
];

module.exports = { home, category, detail, search, play };
runner.run(module.exports);

async function home(params, context) {
  try {
    await logInfo(`[home] params=${safeJson(params)} from=${context?.from || "web"}`);
    const [menu, homeBlocks] = await Promise.all([
      fetchJson("/movie/category/menu"),
      fetchJson(`/movie/media/home/custom/classify/1/3?limit=${DEFAULT_HOME_LIMIT}`),
    ]);
    const classes = buildClasses(menu);
    const list = extractHomeList(homeBlocks).slice(0, DEFAULT_HOME_LIMIT).map(mapVod);
    const filters = buildFilters(menu, classes);
    await logInfo(`[home] class=${classes.length} list=${list.length}`);
    return { class: classes, filters, list };
  } catch (error) {
    await logError(`[home] 失败: ${error.message}`);
    return { class: [], filters: {}, list: [] };
  }
}

async function category(params, context) {
  try {
    const categoryId = String(params?.categoryId || "movie");
    const page = Number(params?.page || 1);
    const filters = params?.filters || {};
    await logInfo(`[category] categoryId=${categoryId} page=${page} filters=${safeJson(filters)} from=${context?.from || "web"}`);
    const body = buildCategoryBody(categoryId, page, filters);
    const data = await postJson("/movie/media/search", body);
    const list = ensureArray(data?.records).map(mapVod);
    const total = Number(data?.total || 0);
    const pagecount = Number(data?.pages || Math.ceil(total / DEFAULT_PAGE_SIZE) || (list.length ? page : 0));
    const currentFilters = buildCategoryReturnFilters(categoryId, filters);
    await logInfo(`[category] total=${total} pagecount=${pagecount} list=${list.length}`);
    return { page, pagecount, total, filters: currentFilters, list };
  } catch (error) {
    await logError(`[category] 失败: ${error.message}`);
    return { page: Number(params?.page || 1), pagecount: 0, total: 0, list: [] };
  }
}

async function detail(params, context) {
  try {
    const videoId = String(params?.videoId || "").trim();
    if (!videoId) return { list: [] };
    await logInfo(`[detail] videoId=${videoId} from=${context?.from || "web"}`);
    const [baseDetail, detailData, seasonData] = await Promise.all([
      fetchJson(`/movie/media/base/detail?mediaId=${encodeURIComponent(videoId)}`),
      fetchJson(`/movie/media/detail?mediaId=${encodeURIComponent(videoId)}`),
      fetchJson(`/movie/media/video/list?mediaId=${encodeURIComponent(videoId)}&lineName=&resolutionCode=`),
    ]);
    const detail = detailData || baseDetail || {};
    const seasonList = ensureArray(seasonData);
    const sources = buildPlaySources(seasonList, videoId);
    const vod = {
      vod_id: String(detail.id || videoId),
      vod_name: String(detail.title || ""),
      vod_pic: pickPoster(detail),
      type_id: String(detail.mediaType?.code || ""),
      type_name: String(detail.mediaType?.name || ""),
      vod_remarks: String(detail.episodeStatus || ""),
      vod_year: stringify(detail.releaseYear),
      vod_area: String(detail.region || ""),
      vod_actor: joinText(detail.actors),
      vod_director: joinText(detail.directors),
      vod_content: String(detail.overview || detail.description || ""),
      vod_douban_score: stringify(detail.rating),
      vod_play_sources: sources,
    };
    await logInfo(`[detail] sources=${sources.length} episodes=${sources.reduce((n, item) => n + ensureArray(item.episodes).length, 0)}`);
    return { list: [vod] };
  } catch (error) {
    await logError(`[detail] 失败: ${error.message}`);
    return { list: [] };
  }
}

async function search(params, context) {
  try {
    const keyword = String(params?.keyword || "").trim();
    const page = Number(params?.page || 1);
    if (!keyword) return { page, pagecount: 0, total: 0, list: [] };
    await logInfo(`[search] keyword=${keyword} page=${page} from=${context?.from || "web"}`);
    const data = await postJson("/movie/media/search", { keyword, page, pageSize: DEFAULT_PAGE_SIZE });
    const list = ensureArray(data?.records).map(mapVod);
    const total = Number(data?.total || 0);
    const pagecount = Number(data?.pages || Math.ceil(total / DEFAULT_PAGE_SIZE) || (list.length ? page : 0));
    return { page, pagecount, total, list };
  } catch (error) {
    await logError(`[search] 失败: ${error.message}`);
    return { page: Number(params?.page || 1), pagecount: 0, total: 0, list: [] };
  }
}

async function play(params, context) {
  try {
    const playId = String(params?.playId || "").trim();
    const flag = String(params?.flag || "乌云影视");
    if (!playId) return emptyPlay(flag);
    await logInfo(`[play] playId=${playId} flag=${flag} from=${context?.from || "web"}`);
    const payload = decodePlayId(playId);
    const mediaId = payload.mediaId;
    const videoId = payload.videoId;
    const seasonNo = payload.seasonNo;
    const epNo = payload.epNo;
    const directUrl = payload.playUrl;
    let finalUrl = directUrl;
    if (!finalUrl && mediaId) {
      const seasonData = await fetchJson(`/movie/media/video/list?mediaId=${encodeURIComponent(mediaId)}&lineName=&resolutionCode=`);
      finalUrl = findPlayUrl(ensureArray(seasonData), { videoId, seasonNo, epNo });
    }
    if (!finalUrl) {
      await logWarn(`[play] 未找到播放地址 playId=${playId}`);
      return emptyPlay(flag);
    }
    finalUrl = unwrapOverseas(finalUrl);
    const referer = playReferer(finalUrl);
    await logInfo(`[play] resolved=${finalUrl}`);
    return {
      parse: 0,
      header: { Referer: referer, Origin: new URL(referer).origin, "User-Agent": UA },
      urls: [{ name: payload.name || "播放", url: finalUrl }]
    };
  } catch (error) {
    await logError(`[play] 失败: ${error.message}`);
    return emptyPlay(String(params?.flag || "乌云影视"));
  }
}

function unwrapOverseas(url) {
  if (!url) return url;
  const m = String(url).match(/\/gen_overseas\/(https?:\/\/.+)/i);
  if (m) return m[1];
  return url;
}

function playReferer(url) {
  try {
    const u = new URL(url);
    return u.origin + "/";
  } catch (e) {
    return SITE + "/";
  }
}

function buildClasses(menu) {
  const yearGroup = ensureArray(menu).find((item) => item?.nameEn === "year");
  const yearChildren = ensureArray(yearGroup?.children);
  const lastYear = yearChildren.find((item) => item?.code === "LAST_YEAR");
  const thisYear = yearChildren.find((item) => item?.code === "THIS_YEAR");
  const rootMenus = extractRootMenus(menu);
  const preferredCodes = ["movie", "tv_series", "animation", "variety", "short_drama"];
  const fallbackNames = { movie: "电影", tv_series: "电视剧", animation: "动画", variety: "综艺", short_drama: "短剧" };
  const classes = [];
  for (const code of preferredCodes) {
    const found = rootMenus.find((item) => item?.code === code);
    classes.push({ type_id: code, type_name: found?.name || fallbackNames[code] || code });
  }
  return classes;
}

function extractRootMenus(menu) {
  return ensureArray(menu).filter((item) => item?.code && !item?.nameEn);
}

function buildFilters(menu, classes) {
  const filters = {};
  for (const c of classes) {
    filters[c.type_id] = [{ key: "sort", name: "排序", value: SORT_OPTIONS }];
  }
  return filters;
}

function buildCategoryBody(categoryId, page, filters) {
  return { mediaType: categoryId, page, pageSize: DEFAULT_PAGE_SIZE, sort: filters?.sort || "default" };
}

function buildCategoryReturnFilters(categoryId, filters) {
  return [{ key: "sort", name: "排序", value: SORT_OPTIONS }];
}

function extractHomeList(homeBlocks) {
  const result = [];
  const seen = new Set();
  const blocks = ensureArray(homeBlocks);
  for (const block of blocks) {
    for (const item of ensureArray(block?.mediaResources)) {
      const id = String(item?.id || "");
      if (!id || seen.has(id)) continue;
      seen.add(id);
      result.push(item);
    }
  }
  return result;
}

function buildPlaySources(seasons, mediaId) {
  const seasonList = ensureArray(seasons);
  const multipleSeason = seasonList.length > 1;
  return seasonList.map((season, seasonIndex) => {
    const seasonNo = season?.seasonNo ?? seasonIndex + 1;
    const videoList = ensureArray(season?.videoList);
    const episodes = videoList.map((video, videoIndex) => {
      const epNo = Number(video?.epNo ?? videoIndex + 1);
      const name = formatEpisodeName(video, videoIndex, multipleSeason);
      return { name, playId: encodePlayId({ mediaId, seasonNo, epNo, videoId: video?.id, playUrl: video?.playUrl, name }) };
    });
    return { name: multipleSeason ? `第${seasonNo}季` : (season?.lineName || season?.title || "乌云影视"), episodes };
  }).filter((item) => item.episodes.length > 0);
}

function formatEpisodeName(video, index, multipleSeason) {
  const epNo = Number(video?.epNo ?? index + 1);
  const remark = String(video?.remark || "").trim();
  if (epNo <= 0) return remark || "正片";
  const prefix = `第${epNo}集`;
  return remark ? `${prefix} ${remark}` : prefix;
}

function mapVod(item) {
  return {
    vod_id: String(item?.id || ""),
    vod_name: String(item?.title || ""),
    vod_pic: pickPoster(item),
    type_id: String(item?.mediaType?.code || ""),
    type_name: String(item?.mediaType?.name || ""),
    vod_remarks: String(item?.episodeStatus || item?.remark || ""),
    vod_year: stringify(item?.releaseYear),
    vod_douban_score: stringify(item?.rating),
    vod_actor: joinText(item?.actors),
    vod_director: joinText(item?.directors),
  };
}

function pickPoster(item) {
  return String(item?.posterUrlS3 || item?.posterUrl || item?.thumbUrlS3 || item?.thumbUrl || "");
}

function findPlayUrl(seasons, target) {
  for (const season of ensureArray(seasons)) {
    if (target?.seasonNo != null && Number(season?.seasonNo) !== Number(target.seasonNo)) continue;
    for (const video of ensureArray(season?.videoList)) {
      if (target?.videoId != null && Number(video?.id) === Number(target.videoId)) return String(video?.playUrl || "");
      if (target?.epNo != null && Number(video?.epNo) === Number(target.epNo)) return String(video?.playUrl || "");
    }
  }
  const firstSeason = ensureArray(seasons)[0];
  const firstVideo = ensureArray(firstSeason?.videoList)[0];
  return String(firstVideo?.playUrl || "");
}

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

async function fetchJson(path) {
  const url = path.startsWith("http") ? path : `${SITE}${path}`;
  const res = await OmniBox.request(url, {
    method: "GET",
    headers: { Accept: "application/json, text/plain, */*", Referer: `${SITE}/`, Origin: SITE, "User-Agent": UA },
  });
  if (res.statusCode !== 200) throw new Error(`GET ${path} => HTTP ${res.statusCode}`);
  const json = JSON.parse(res.body || "{}");
  if (json && json.code && json.code !== 200 && json.isSuccess === false) throw new Error(`GET ${path} => ${json.resultMsg || json.code}`);
  return json?.data;
}

async function postJson(path, body) {
  const url = `${SITE}${path}`;
  const res = await OmniBox.request(url, {
    method: "POST",
    headers: { Accept: "application/json, text/plain, */*", Referer: `${SITE}/`, Origin: SITE, "User-Agent": UA, "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (res.statusCode !== 200) throw new Error(`POST ${path} => HTTP ${res.statusCode}`);
  const json = JSON.parse(res.body || "{}");
  if (json && json.code && json.code !== 200 && json.isSuccess === false) throw new Error(`POST ${path} => ${json.resultMsg || json.code}`);
  return json?.data;
}

function encodePlayId(obj) {
  try { return Buffer.from(JSON.stringify(obj)).toString("base64"); } catch (e) { return ""; }
}

function decodePlayId(s) {
  try { return JSON.parse(Buffer.from(s, "base64").toString("utf-8")); } catch (e) { return {}; }
}

function emptyPlay(flag) {
  return { parse: 0, header: {}, urls: [] };
}

function ensureArray(v) { return Array.isArray(v) ? v : []; }
function stringify(v) { return v == null ? "" : String(v); }
function joinText(v) { return Array.isArray(v) ? v.map(x => x?.name || x).filter(Boolean).join(" / ") : String(v || ""); }
function safeJson(v) { try { return JSON.stringify(v); } catch (e) { return ""; } }
async function logInfo(m) { try { await OmniBox.log("info", m); } catch (e) {} }
async function logWarn(m) { try { await OmniBox.log("warn", m); } catch (e) {} }
async function logError(m) { try { await OmniBox.log("error", m); } catch (e) {} }
