// @name 乌云影视
// @author 梦
// @description 刮削：未接入，弹幕：站内弹幕接口，嗅探：不需要
// @dependencies
// @version 1.1.4
// @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E8%A7%A3%E6%9E%90js/乌云影视.js

const OmniBox = require("omnibox_sdk");
const runner = require("spider_runner");

const SITE = (process.env.WOOYUN_HOST || "https://wooyun.tv").replace(/\/$/, "");
const DEFAULT_PAGE_SIZE = 24;
const DEFAULT_HOME_LIMIT = 12;

const SORT_OPTIONS = [
  { name: "默认", value: "default" },
  { name: "最新", value: "latest" },
  { name: "最热", value: "hot" },
  { name: "评分", value: "score" },
];

const TOP_CODES = ["movie", "tv_series", "animation", "variety", "short_drama"];
const FALLBACK_NAMES = {
  movie: "电影",
  tv_series: "电视剧",
  animation: "动画",
  variety: "综艺",
  short_drama: "短剧",
};

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
    // 框架可能把筛选条件放在 extend 或 filters 里
    const filters = params?.extend || params?.filters || {};
    await logInfo(`[category] categoryId=${categoryId} page=${page} filters=${safeJson(filters)} from=${context?.from || "web"}`);
    const body = buildCategoryBody(categoryId, page, filters);
    await logInfo(`[category] body=${safeJson(body)}`);
    const data = await postJson("/movie/media/search", body);
    const list = extractRecords(data).map(mapVod);
    const total = Number(data?.total || 0);
    const pagecount = Number(data?.pages || Math.ceil(total / DEFAULT_PAGE_SIZE) || (list.length ? page : 0));
    await logInfo(`[category] total=${total} pagecount=${pagecount} list=${list.length}`);
    return { page, pagecount, total, filters: buildCategoryReturnFilters(categoryId, filters), list };
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
    const seasonList = ensureArray(seasonData?.records || seasonData);
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
    if (!keyword) return emptyPage(page);
    await logInfo(`[search] keyword=${keyword} page=${page} quick=${params?.quick ? 1 : 0} from=${context?.from || "web"}`);
    const data = await postJson("/movie/media/search", {
      menuCodeList: [],
      pageIndex: String(page),
      pageSize: DEFAULT_PAGE_SIZE,
      searchKey: keyword,
      sortCode: "",
      topCode: "",
    });
    const list = extractRecords(data).map(mapVod);
    const total = Number(data?.total || 0);
    const pagecount = Number(data?.pages || Math.ceil(total / DEFAULT_PAGE_SIZE) || (list.length ? page : 0));
    await logInfo(`[search] total=${total} pagecount=${pagecount} list=${list.length}`);
    return { page, pagecount, total, list };
  } catch (error) {
    await logError(`[search] 失败: ${error.message}`);
    return emptyPage(Number(params?.page || 1));
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
      finalUrl = findPlayUrl(ensureArray(seasonData?.records || seasonData), { videoId, seasonNo, epNo });
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
      urls: [{ name: payload.name || "播放", url: finalUrl }],
    };
  } catch (error) {
    await logError(`[play] 失败: ${error.message}`);
    return emptyPlay(String(params?.flag || "乌云影视"));
  }
}

// ==================== 播放地址处理 ====================

// 站点会把海外线路包装成 /gen_overseas/<真实地址>，播放前需还原
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

// ==================== 分类与筛选 ====================

function buildClasses(menu) {
  const yearGroup = ensureArray(menu).find((item) => item?.nameEn === "year");
  const yearChildren = ensureArray(yearGroup?.children);
  const lastYear = yearChildren.find((item) => item?.code === "LAST_YEAR");
  const thisYear = yearChildren.find((item) => item?.code === "THIS_YEAR");

  const rootMenus = extractRootMenus(menu);
  const classes = TOP_CODES.map((code) => {
    const found = rootMenus.find((item) => item?.code === code);
    return found
      ? { type_id: String(found.code), type_name: String(found.name || found.nameEn || code) }
      : { type_id: code, type_name: FALLBACK_NAMES[code] || code };
  });

  if (thisYear) classes.push({ type_id: thisYear.code, type_name: thisYear.name || "今年" });
  if (lastYear) classes.push({ type_id: lastYear.code, type_name: lastYear.name || "去年" });
  return classes;
}

function extractRootMenus(menu) {
  if (Array.isArray(menu) && menu.length && menu[0] && Object.prototype.hasOwnProperty.call(menu[0], "code")) {
    return ensureArray(menu).filter((item) => item && typeof item === "object");
  }
  return [];
}

function buildFilters(menu, classes) {
  const optionMap = buildFilterValueMap(menu);
  const result = {};
  for (const cls of ensureArray(classes)) {
    result[String(cls.type_id)] = buildFilterArrayForClass(String(cls.type_id), optionMap);
  }
  return result;
}

function buildFilterArrayForClass(categoryId, optionMap) {
  const list = [];

  if (optionMap.year.length) {
    list.push({ key: "year", name: "年份", init: "", value: [{ name: "全部", value: "" }, ...optionMap.year] });
  }
  if (optionMap.region.length) {
    list.push({ key: "region", name: "地区", init: "", value: [{ name: "全部", value: "" }, ...optionMap.region] });
  }
  if (optionMap.genre.length && TOP_CODES.includes(categoryId)) {
    list.push({ key: "genre", name: "类型", init: "", value: [{ name: "全部", value: "" }, ...optionMap.genre] });
  }
  if (optionMap.language.length) {
    list.push({ key: "lang", name: "语言", init: "", value: [{ name: "全部", value: "" }, ...optionMap.language] });
  }
  list.push({ key: "sort", name: "排序", init: "default", value: SORT_OPTIONS });
  return list;
}

function buildFilterValueMap(menu) {
  const groups = ensureArray(menu);
  const result = { genre: [], region: [], year: [], language: [], other: [] };

  for (const group of groups) {
    const nameEn = String(group?.nameEn || "");
    const values = ensureArray(group?.children)
      .map((item) => ({
        name: String(item?.name || item?.nameEn || item?.code || ""),
        value: String(item?.code || ""),
      }))
      .filter((item) => item.name && item.value && !["THIS_YEAR", "LAST_YEAR"].includes(item.value));

    if (nameEn === "genre") result.genre = values;
    else if (nameEn === "region") result.region = values;
    else if (nameEn === "year") result.year = values;
    else if (nameEn === "language") result.language = values;
    else if (nameEn === "other") result.other = values;
  }
  return result;
}

// 分类检索请求体：站点要求 menuCodeList / pageIndex / searchKey / sortCode / topCode
function buildCategoryBody(categoryId, page, filters) {
  const body = {
    menuCodeList: [],
    pageIndex: String(page),
    pageSize: DEFAULT_PAGE_SIZE,
    searchKey: "",
    sortCode: filters?.sort && filters.sort !== "default" ? String(filters.sort) : "",
    topCode: mapTopCode(categoryId),
  };

  const menuCodeList = [];
  if (!TOP_CODES.includes(categoryId)) menuCodeList.push(categoryId);
  for (const item of [filters?.genre, filters?.region, filters?.year, filters?.lang, filters?.other]) {
    if (item && !menuCodeList.includes(String(item))) menuCodeList.push(String(item));
  }
  body.menuCodeList = menuCodeList;
  return body;
}

function buildCategoryReturnFilters(categoryId, filters) {
  return {
    categoryId,
    ...Object.fromEntries(
      Object.entries({
        genre: filters?.genre || "",
        region: filters?.region || "",
        year: filters?.year || "",
        lang: filters?.lang || "",
        other: filters?.other || "",
        sort: filters?.sort || "default",
      }).filter(([, value]) => value !== undefined)
    ),
  };
}

function mapTopCode(categoryId) {
  const topCodeMap = {
    movie: "movie",
    tv_series: "tv_series",
    animation: "animation",
    variety: "variety",
    short_drama: "short_drama",
    THIS_YEAR: "movie",
    LAST_YEAR: "movie",
  };
  return topCodeMap[categoryId] || "movie";
}

// ==================== 数据解析 ====================

// 首页区块：接口返回 { records: [...] } 或直接是数组
function extractHomeList(homeBlocks) {
  const blocks = ensureArray(homeBlocks?.records || homeBlocks);
  const result = [];
  const seen = new Set();
  for (const block of blocks) {
    for (const item of ensureArray(block?.mediaResources || block?.list || block?.records)) {
      const id = String(item?.id || item?.mediaId || "");
      if (!id || seen.has(id)) continue;
      seen.add(id);
      result.push(item);
    }
  }
  return result;
}

// 检索结果：兼容 records / list / rows / content 等字段名
function extractRecords(data) {
  if (Array.isArray(data)) return data;
  if (!data || typeof data !== "object") return [];
  return ensureArray(data.records || data.list || data.rows || data.content || data.items);
}

function buildPlaySources(seasons, mediaId) {
  const seasonList = ensureArray(seasons);
  const multipleSeason = seasonList.length > 1;
  return seasonList
    .map((season, seasonIndex) => {
      const seasonNo = season?.seasonNo ?? seasonIndex + 1;
      const videoList = ensureArray(season?.videoList || season?.videos || season?.episodes);
      const episodes = videoList.map((video, videoIndex) => {
        const epNo = Number(video?.epNo ?? videoIndex + 1);
        const name = formatEpisodeName(video, videoIndex, multipleSeason);
        return {
          name,
          playId: encodePlayId({
            mediaId,
            seasonNo,
            epNo,
            videoId: video?.id,
            playUrl: video?.playUrl,
            name,
          }),
        };
      });
      return {
        name: multipleSeason ? `第${seasonNo}季` : (season?.lineName || season?.title || "乌云影视"),
        episodes,
      };
    })
    .filter((item) => item.episodes.length > 0);
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
    vod_id: String(item?.id || item?.mediaId || ""),
    vod_name: String(item?.title || item?.name || ""),
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
  return String(item?.posterUrlS3 || item?.posterUrl || item?.thumbUrlS3 || item?.thumbUrl || item?.cover || "");
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

// ==================== 请求层 ====================

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

async function fetchJson(path) {
  const url = path.startsWith("http") ? path : `${SITE}${path}`;
  const res = await OmniBox.request(url, {
    method: "GET",
    headers: {
      Accept: "application/json, text/plain, */*",
      Referer: `${SITE}/`,
      Origin: SITE,
      "User-Agent": UA,
    },
  });

  if (res.statusCode !== 200) {
    throw new Error(`GET ${path} => HTTP ${res.statusCode} body=${String(res.body || "").slice(0, 200)}`);
  }

  const json = parseJson(res.body);
  assertApiOk(json, `GET ${path}`);
  return json?.data ?? (json && typeof json === "object" && !("data" in json) ? json : undefined);
}

async function postJson(path, body) {
  const url = `${SITE}${path}`;
  const res = await OmniBox.request(url, {
    method: "POST",
    headers: {
      Accept: "application/json, text/plain, */*",
      Referer: `${SITE}/`,
      Origin: SITE,
      "User-Agent": UA,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (res.statusCode !== 200) {
    throw new Error(`POST ${path} => HTTP ${res.statusCode} body=${String(res.body || "").slice(0, 200)}`);
  }

  const json = parseJson(res.body);
  assertApiOk(json, `POST ${path}`);
  return json?.data ?? (json && typeof json === "object" && !("data" in json) ? json : undefined);
}

function parseJson(body) {
  try {
    return JSON.parse(body || "{}");
  } catch (e) {
    throw new Error(`响应非 JSON: ${String(body || "").slice(0, 200)}`);
  }
}

function assertApiOk(json, where) {
  if (!json || typeof json !== "object") return;
  if (json.isSuccess === false || (json.code != null && ![0, 200].includes(Number(json.code)))) {
    throw new Error(`${where} => ${json.resultMsg || json.message || json.msg || `code=${json.code}`}`);
  }
}

function encodePlayId(payload) {
  try {
    return Buffer.from(JSON.stringify(payload), "utf8").toString("base64");
  } catch (e) {
    return "";
  }
}

function decodePlayId(playId) {
  try {
    return JSON.parse(Buffer.from(playId, "base64").toString("utf8"));
  } catch (e) {
    try {
      return JSON.parse(Buffer.from(playId, "base64url").toString("utf8"));
    } catch (err) {
      return { mediaId: playId };
    }
  }
}

// ==================== 工具函数 ====================

function ensureArray(value) {
  return Array.isArray(value) ? value : [];
}

function stringify(value) {
  return value == null ? "" : String(value);
}

function joinText(value) {
  return ensureArray(value)
    .map((item) => (item && typeof item === "object" ? item.name || item.title || "" : item))
    .filter(Boolean)
    .join(" / ");
}

function emptyPage(page) {
  return { page, pagecount: 0, total: 0, list: [] };
}

function emptyPlay(flag) {
  return { parse: 0, header: {}, urls: [] };
}

function safeJson(value) {
  try {
    return JSON.stringify(value || {});
  } catch (e) {
    return "{}";
  }
}

async function logInfo(msg) {
  try { await OmniBox.log("info", msg); } catch (e) {}
}

async function logWarn(msg) {
  try { await OmniBox.log("warn", msg); } catch (e) {}
}

async function logError(msg) {
  try { await OmniBox.log("error", msg); } catch (e) {}
}
