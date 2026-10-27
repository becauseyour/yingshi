// @name 母鸡资源站(MacCMS API)-增强版
// @author OpenClaw Bingbu + 梦
// @description 刮削：支持，弹幕：支持，嗅探：支持，观看记录：支持，广告：菠菜
// @dependencies: axios
// @version 1.1.3
// @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E8%A7%A3%E6%9E%90js/母鸡资源站.js

/**
 * ============================================================================
 * 母鸡资源站 OmniBox 站源（增强版）
 * 站点: https://mujiziyuan00.com
 * 
 * 更新日志：
 * - v1.1.3: 修复分类不准确（电影里混入剧集），动态重构父子分类映射。
 * ============================================================================
 */

const axios = require("axios");
const OmniBox = require("omnibox_sdk");
const runner = require("spider_runner");

const HOST = "https://mujiziyuan00.com";
const API = `${HOST}/api.php/provide/vod`;
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36";

// 注意：这里仅作为兜底展示，真正的分类关系我们会在运行时动态从源站解析
const MAIN_CATEGORIES = [
  { type_id: "7", type_name: "电影" },
  { type_id: "8", type_name: "连续剧" },
  { type_id: "9", type_name: "综艺" },
  { type_id: "40", type_name: "动漫" },
  { type_id: "39", type_name: "伦理片" }
];

const DEFAULT_BLOCKED_MAIN = ["39"];

const http = axios.create({
  timeout: 20000,
  headers: {
    "User-Agent": UA,
    "Accept": "application/json,text/plain,*/*",
    "Referer": `${HOST}/`
  },
  validateStatus: () => true
});

const CLASS_CACHE = {
  list: [],
  mapById: {},
  childMap: {}
};

function safeJson(input, fallback = {}) {
  if (!input) return fallback;
  if (typeof input === "object") return input;
  try {
    return JSON.parse(input);
  } catch {
    return fallback;
  }
}

function text(v) {
  return String(v == null ? "" : v).trim();
}

function fixUrl(url) {
  const u = text(url);
  if (!u || u === "<nil>") return "";
  if (/^https?:\/\//i.test(u)) return u;
  if (u.startsWith("//")) return `https:${u}`;
  if (u.startsWith("/")) return `${HOST}${u}`;
  return `${HOST}/${u}`;
}

function b64Encode(obj) {
  try {
    return Buffer.from(JSON.stringify(obj || {}), "utf8").toString("base64");
  } catch {
    return "";
  }
}

function b64Decode(str) {
  try {
    return JSON.parse(Buffer.from(String(str || ""), "base64").toString("utf8"));
  } catch {
    return {};
  }
}

function getBlockedMainSet() {
  const env = text(process.env.MUJI_BLOCKED_MAIN);
  const raw = env ? env.split(",").map((s) => s.trim()).filter(Boolean) : DEFAULT_BLOCKED_MAIN;
  return new Set(raw);
}

function updateClassCache(classList) {
  const classes = Array.isArray(classList)
    ? classList.map((c) => ({
        type_id: text(c.type_id),
        type_pid: text(c.type_pid),
        type_name: text(c.type_name)
      })).filter((c) => c.type_id && c.type_name)
    : [];

  if (!classes.length) return;

  const mapById = {};
  const childMap = {};
  
  // 动态构建分类树
  classes.forEach((c) => {
    mapById[c.type_id] = c;
    const pid = c.type_pid || "0";
    if (!childMap[pid]) childMap[pid] = [];
    childMap[pid].push(c);
  });

  CLASS_CACHE.list = classes;
  CLASS_CACHE.mapById = mapById;
  CLASS_CACHE.childMap = childMap;
}

async function fetchApi(params = {}) {
  try {
    const res = await http.get(API, { params });
    const data = safeJson(res.data, {});
    if (Array.isArray(data.class)) updateClassCache(data.class);
    return data;
  } catch (error) {
    await OmniBox.log("warn", `fetchApi 失败: ${error.message}`);
    return {};
  }
}

async function ensureClassCache() {
  if (Array.isArray(CLASS_CACHE.list) && CLASS_CACHE.list.length > 0) return;
  await fetchApi({ ac: "list", pg: 1 });
}

// 核心修复 1：动态解析父类ID
function resolveMainTypeId(typeId, fallbackMain = "") {
  const t = text(typeId);
  if (!t) return text(fallbackMain);
  
  // 优先从动态缓存中找它的父级
  const mapById = CLASS_CACHE.mapById || {};
  let cur = mapById[t];
  let guard = 0;
  
  while (cur && guard < 10) {
    guard += 1;
    // 如果它没有父级，或者父级是0，说明它本身就是一级分类
    if (!cur.type_pid || cur.type_pid === "0" || cur.type_pid === cur.type_id) {
      return cur.type_id;
    }
    // 如果它的名字正好是我们要的主分类，直接返回
    if (MAIN_CATEGORIES.some((m) => m.type_id === cur.type_id)) {
       return cur.type_id;
    }
    cur = mapById[cur.type_pid];
  }

  // 如果动态找不到，回退到默认的兜底
  if (MAIN_CATEGORIES.some((m) => m.type_id === t)) return t;
  return text(fallbackMain);
}

function isMainBlocked(mainTypeId) {
  return getBlockedMainSet().has(text(mainTypeId));
}

// 核心修复 2：识别并剔除混入电影的剧集
function isTvShowName(vodName, typeName) {
  const name = text(vodName);
  const tname = text(typeName);
  
  // 如果分类名已经标明了是剧集/动漫/综艺，不算错放
  if (/剧|动漫|综艺|纪录|动画/i.test(tname)) return false;

  // 匹配常见的电视剧特征词
  const tvKeywords = [
    /第\s*[\d一二三四五六七八九十百]+\s*[集话期回]/,
    /全\s*[\d一二三四五六七八九十百]+\s*[集话期回]/,
    /更新至\s*\d+\s*[集话期回]/,
    /共\s*\d+\s*[集话期回]/,
    /\bEP?\d+\b/i,
    /\bS\d{1,2}E\d{1,2}\b/i,
    /电视剧|连续剧|网剧/
  ];
  
  return tvKeywords.some(regex => regex.test(name));
}

// 获取主分类列表
function buildMainClasses() {
  if (CLASS_CACHE.list.length === 0) {
    // 如果缓存还没拉回来，先用兜底
    return MAIN_CATEGORIES.filter((c) => !isMainBlocked(c.type_id));
  }
  
  // 从源站的真实分类树里，找出真正的顶级分类（type_pid == 0）
  const topLevel = CLASS_CACHE.list.filter(c => !c.type_pid || c.type_pid === "0");
  
  // 如果源站没返回顶级分类，依然用兜底
  if (topLevel.length === 0) {
     return MAIN_CATEGORIES.filter((c) => !isMainBlocked(c.type_id));
  }
  
  // 将顶级分类映射成前端要的格式，并过滤屏蔽
  return topLevel
    .filter(c => !isMainBlocked(c.type_id))
    .map(c => ({ type_id: c.type_id, type_name: c.type_name }));
}

function buildFiltersForMain(mainTypeId) {
  const key = text(mainTypeId);
  // 动态获取该父分类下的所有子分类
  const children = (CLASS_CACHE.childMap?.[key] || [])
    .filter((c) => c.type_id !== key)
    .map((c) => ({ type_id: c.type_id, type_name: c.type_name }));
    
  if (!children.length) return [];
  
  return [{
    key: "subtype",
    name: "子分类",
    init: "",
    value: [{ name: "全部", value: "" }, ...children.map((c) => ({ name: c.type_name, value: c.type_id }))]
  }];
}

function getChildTypeIds(mainTypeId) {
  const key = text(mainTypeId);
  return (CLASS_CACHE.childMap?.[key] || [])
    .filter((c) => c.type_id && c.type_id !== key)
    .map((c) => c.type_id);
}

async function enrichVideosWithDetails(rawList, mainTypeId = "") {
  if (!Array.isArray(rawList) || rawList.length === 0) return [];

  const videos = rawList.map((item) => {
    const typeId = text(item.type_id || "");
    const resolvedMainType = resolveMainTypeId(typeId, item.type_id_1 || "");
    return {
      vod_id: text(item.vod_id),
      vod_name: text(item.vod_name),
      vod_pic: fixUrl(item.vod_pic),
      vod_remarks: text(item.vod_remarks || item.type_name || ""),
      type_id: typeId,
      type_name: text(item.type_name || ""),
      main_type_id: resolvedMainType,
      vod_year: text(item.vod_year || ""),
      vod_douban_score: text(item.vod_douban_score || ""),
      _needDetail: !item.vod_pic || item.vod_pic === "<nil>" || item.vod_pic === ""
    };
  });

  // 【核心过滤】如果我们在电影分类里，干掉明显的剧集
  const isMovieContext = (text(mainTypeId) === "7" || text(mainTypeId) === "电影");
  const filteredVideos = videos.filter(v => {
    if (isMovieContext && isTvShowName(v.vod_name, v.type_name)) {
      return false; 
    }
    return true;
  });

  // 批量补全图片
  const needDetailVideos = filteredVideos.filter(v => v._needDetail);
  if (needDetailVideos.length > 0) {
    const batchSize = 20;
    for (let i = 0; i < needDetailVideos.length; i += batchSize) {
      const batch = needDetailVideos.slice(i, i + batchSize);
      const ids = batch.map(v => v.vod_id).join(",");
      try {
        const detailData = await fetchApi({ ac: "detail", ids });
        if (Array.isArray(detailData.list)) {
          detailData.list.forEach(detailItem => {
            const vid = text(detailItem.vod_id);
            const target = filteredVideos.find(v => v.vod_id === vid);
            if (target) {
              const pic = fixUrl(detailItem.vod_pic);
              if (pic) target.vod_pic = pic;
            }
          });
        }
      } catch (error) {}
    }
  }

  const finalList = await Promise.all(filteredVideos.map(async (v) => {
    delete v._needDetail;
    if (!v.vod_pic && v.vod_id) {
      try {
        const metadata = await OmniBox.getScrapeMetadata(v.vod_id);
        if (metadata?.scrapeData) {
          const sd = metadata.scrapeData;
          const posterPath = sd.posterPath || sd.poster_path;
          if (posterPath) v.vod_pic = `https://wsrv.nl/?url=image.tmdb.org/t/p/w300${posterPath}`;
        }
      } catch (e) {}
    }
    return v;
  }));

  return finalList;
}

function buildResourceId(vodId) { return text(vodId); }
function buildEpisodeFileId(vodId, flag, epName, idx) { return `${text(vodId)}#${text(flag)}#${idx}`; }

function parsePlaySources(vodPlayFrom, vodPlayUrl, vodId, vodName = "") {
  const fromArr = text(vodPlayFrom).split("$$$").map((s) => s.trim()).filter(Boolean);
  const urlArr = text(vodPlayUrl).split("$$$").map((s) => s.trim()).filter(Boolean);
  const sourceCount = Math.max(fromArr.length, urlArr.length);
  const sources = [];
  const videoFiles = [];
  const cleanVodName = text(vodName).replace(/[\s\.]+/g, '.');

  for (let i = 0; i < sourceCount; i += 1) {
    const flag = fromArr[i] || `线路${i + 1}`;
    const group = urlArr[i] || "";
    const episodesRaw = group.split("#").map((s) => s.trim()).filter(Boolean);

    const episodes = episodesRaw.map((item, idx) => {
      let epName = `第${idx + 1}集`;
      let epUrl = item;
      const cut = item.indexOf("$");
      if (cut > -1) {
        epName = text(item.slice(0, cut)) || epName;
        epUrl = text(item.slice(cut + 1));
      }

      const fileId = buildEpisodeFileId(vodId, flag, epName, idx + 1);
      videoFiles.push({
        fid: fileId,
        file_id: fileId,
        file_name: `${cleanVodName}.S01E${String(idx + 1).padStart(2, '0')}`,
        name: epName,
        format_type: "video"
      });

      const playId = b64Encode({
        resourceId: buildResourceId(vodId),
        vodId: text(vodId),
        name: vodName,
        flag,
        epName,
        episodeIndex: idx + 1,
        fileId,
        url: epUrl
      });

      return { name: epName, playId, _fileId: fileId };
    });

    if (episodes.length > 0) {
      sources.push({ name: flag, episodes });
    }
  }
  return { sources, videoFiles };
}

async function enrichPlaySourcesWithMetadata(playSources, resourceId) {
  try {
    const metadata = await OmniBox.getScrapeMetadata(resourceId);
    const scrapeData = metadata?.scrapeData || null;
    const videoMappings = Array.isArray(metadata?.videoMappings) ? metadata.videoMappings : [];

    if (!playSources.length || !videoMappings.length) return { playSources, scrapeData, metadata };

    const mappingMap = new Map();
    for (const m of videoMappings) {
      if (m?.fileId) mappingMap.set(String(m.fileId), m);
    }

    for (const source of playSources) {
      for (const ep of source.episodes || []) {
        const lookupKey = String(ep._fileId || "");
        const mapping = mappingMap.get(lookupKey);
        if (!mapping) continue;
        if (mapping.episodeName) ep.episodeName = mapping.episodeName;
        if (mapping.seasonNumber != null) ep._seasonNumber = mapping.seasonNumber;
        if (mapping.episodeNumber != null) ep._episodeNumber = mapping.episodeNumber;
      }

      const hasOrdering = (source.episodes || []).some((ep) => ep._episodeNumber != null);
      if (hasOrdering) {
        source.episodes.sort((a, b) => {
          const sa = Number(a._seasonNumber || 0);
          const sb = Number(b._seasonNumber || 0);
          if (sa !== sb) return sa - sb;
          return Number(a._episodeNumber || 0) - Number(b._episodeNumber || 0);
        });
      }

      for (const ep of source.episodes || []) {
        delete ep._seasonNumber;
        delete ep._episodeNumber;
        delete ep._fileId;
      }
    }
    return { playSources, scrapeData, metadata };
  } catch (error) {
    for (const source of playSources) {
      for (const ep of source.episodes || []) delete ep._fileId;
    }
    return { playSources, scrapeData: null, metadata: null };
  }
}

function getFilterSubtype(params) {
  return text(params?.filters?.subtype || params?.filter?.subtype || params?.extend?.subtype || params?.ext?.subtype || "");
}

function isAllSelection(value) {
  const v = text(value).toLowerCase();
  return !v || v === "0" || v === "-1" || v === "all" || v === "全部";
}

function inferTypeName(mainTypeId, rawTypeName) {
  const hit = MAIN_CATEGORIES.find((m) => m.type_id === text(mainTypeId));
  return hit?.type_name || text(rawTypeName || "");
}

function buildScrapeKeyword(item) { return text(item.vod_name); }

function buildDanmakuFileName(scrapeData, mapping, fallbackTitle, fallbackEpName) {
  if (!scrapeData) return `${fallbackTitle || ""} ${fallbackEpName || ""}`.trim();
  const title = text(scrapeData.title || fallbackTitle || "");
  const scrapeType = text(scrapeData.scrapeType || scrapeData.type || "").toLowerCase();
  const seasonAirYear = text(scrapeData.seasonAirYear || scrapeData.releaseDate || "").slice(0, 4);
  if (mapping && (mapping.episodeNumber != null || mapping.seasonNumber != null || scrapeType === "tv")) {
    const season = Number(mapping?.seasonNumber || 1);
    const episode = Number(mapping?.episodeNumber || 1);
    const yearPart = seasonAirYear ? `.${seasonAirYear}` : "";
    return `${title}${yearPart}.S${String(season).padStart(2, "0")}E${String(episode).padStart(2, "0")}`;
  }
  return title || `${fallbackTitle || ""} ${fallbackEpName || ""}`.trim();
}

// 核心修复 3：请求时动态拼装真实的子分类ID列表
async function fetchMainAllByChildren(mainTypeId, page) {
  const childTypeIds = getChildTypeIds(mainTypeId);
  
  // 如果没有子分类，直接查询父分类
  if (!childTypeIds.length) {
    const direct = await fetchApi({ ac: "list", t: text(mainTypeId), pg: page });
    const rawList = (Array.isArray(direct.list) ? direct.list : []).filter((it) => !isMainBlocked(it.main_type_id || it.type_id));
    // 【注意】这里传入 mainTypeId 上下文，用于过滤错误的剧集
    const list = await enrichVideosWithDetails(rawList, mainTypeId); 
    return { list, page: Number(direct.page || page || 1), pagecount: Number(direct.pagecount || page || 1), total: Number(direct.total || list.length || 0), limit: Number(direct.limit || 20) };
  }

  // 如果有多级分类，同时并发请求
  const results = await Promise.all(childTypeIds.map((tid) => fetchApi({ ac: "list", t: tid, pg: page })));
  const mergedRaw = [];
  let total = 0, pagecount = 0, limit = 20;
  
  results.forEach((data) => {
    const arr = Array.isArray(data.list) ? data.list : [];
    mergedRaw.push(...arr);
    total += Number(data.total || 0);
    pagecount = Math.max(pagecount, Number(data.pagecount || 0));
    if (Number(data.limit || 0) > 0) limit = Number(data.limit);
  });

  const seen = new Set();
  const uniqueRaw = mergedRaw.filter((it) => {
    if (!it.vod_id || seen.has(it.vod_id)) return false;
    seen.add(it.vod_id);
    return true;
  });

  // 【注意】这里传入 mainTypeId 上下文，用于过滤错误的剧集
  const list = await enrichVideosWithDetails(uniqueRaw, mainTypeId);
  list.sort((a, b) => Number(b.vod_id || 0) - Number(a.vod_id || 0));
  return { list, page, pagecount: pagecount || page, total: total || list.length, limit };
}

async function home(params, context) {
  await ensureClassCache(); // 必须先拉取分类缓存
  const data = await fetchApi({ ac: "list", pg: 1 });
  const classes = buildMainClasses();
  
  // 首页的 `全部` 标签，不需要过度过滤
  const rawList = (Array.isArray(data.list) ? data.list : []).filter((it) => !isMainBlocked(it.main_type_id || it.type_id));
  const list = await enrichVideosWithDetails(rawList, ""); 
  
  const filters = {};
  classes.forEach((m) => {
    const f = buildFiltersForMain(m.type_id);
    if (f.length) filters[m.type_id] = f;
  });
  return { class: classes, filters, list };
}

async function category(params, context) {
  const page = parseInt(params?.page || "1", 10) || 1;
  const mainTypeId = text(params?.categoryId || params?.type_id || "");
  const subtype = getFilterSubtype(params);
  await ensureClassCache();

  if (isMainBlocked(mainTypeId)) return { list: [], page, pagecount: 0, total: 0, limit: 20 };

  let result;
  if (!isAllSelection(subtype)) {
    // 指定了子分类，直接查询该子分类
    const data = await fetchApi({ ac: "list", t: subtype, pg: page });
    const rawList = (Array.isArray(data.list) ? data.list : []).filter((it) => !isMainBlocked(it.main_type_id || it.type_id));
    // 传入 mainTypeId，如果是在“电影”分类下选子分类，依然会过滤剧集
    const list = await enrichVideosWithDetails(rawList, mainTypeId);
    result = { list, page: Number(data.page || page || 1), pagecount: Number(data.pagecount || page || 1), total: Number(data.total || list.length || 0), limit: Number(data.limit || 20) };
  } else {
    // 选择了“全部”，触发聚合
    result = await fetchMainAllByChildren(mainTypeId, page);
  }

  const f = buildFiltersForMain(mainTypeId);
  if (f.length && page === 1) result.filters = f;
  return result;
}

async function search(params, context) {
  const keyword = text(params?.keyword || params?.wd || "");
  const page = parseInt(params?.page || "1", 10) || 1;
  if (!keyword) return { list: [], page: 1, pagecount: 0, total: 0 };

  const data = await fetchApi({ ac: "list", wd: keyword, pg: page });
  // 搜索不需要过滤，搜到什么就是什么
  const rawList = (Array.isArray(data.list) ? data.list : []).filter((it) => !isMainBlocked(it.main_type_id || it.type_id));
  const list = await enrichVideosWithDetails(rawList, "");

  return { list, page: Number(data.page || page || 1), pagecount: Number(data.pagecount || page || 1), total: Number(data.total || list.length || 0), limit: Number(data.limit || 20) };
}

async function detail(params, context) {
  try {
    const videoId = text(params?.videoId || "");
    if (!videoId) return { list: [] };

    const data = await fetchApi({ ac: "detail", ids: videoId });
    const item = Array.isArray(data.list) && data.list.length ? data.list[0] : null;
    if (!item) return { list: [] };

    const mainTypeId = resolveMainTypeId(item.type_id, item.type_id_1 || "");
    if (isMainBlocked(mainTypeId)) return { list: [] };

    const resourceId = buildResourceId(videoId);
    const { sources, videoFiles } = parsePlaySources(item.vod_play_from, item.vod_play_url, videoId, item.vod_name);

    let scrapeData = null;
    if (videoFiles.length > 0) {
      try {
        await OmniBox.processScraping(resourceId, buildScrapeKeyword(item), text(item.vod_name), videoFiles);
      } catch (error) {
        await OmniBox.log("warn", `[detail] processScraping 失败: ${error.message}`);
      }
    }

    const enriched = await enrichPlaySourcesWithMetadata(sources, resourceId);
    const playSources = enriched.playSources;
    scrapeData = enriched.scrapeData;

    const posterPath = scrapeData?.posterPath || scrapeData?.poster_path || scrapeData?.poster;
    const originalPic = fixUrl(item.vod_pic);
    const finalPic = originalPic || (posterPath ? `https://wsrv.nl/?url=image.tmdb.org/t/p/w500${posterPath}` : "");

    const vod = {
      vod_id: text(item.vod_id),
      vod_name: text(scrapeData?.title || item.vod_name),
      vod_pic: finalPic,
      vod_remarks: text(item.vod_remarks),
      vod_year: text((scrapeData?.releaseDate || item.vod_year || "").slice?.(0, 4) || item.vod_year || ""),
      vod_area: text(item.vod_area),
      vod_lang: text(item.vod_lang),
      vod_director: text(item.vod_director || scrapeData?.credits?.crew?.filter?.((x) => x.job === "Director").map?.((x) => x.name).join(",") || ""),
      vod_actor: text(item.vod_actor || scrapeData?.credits?.cast?.slice?.(0, 8).map?.((x) => x.name).join(",") || ""),
      vod_class: text(item.vod_class || inferTypeName(mainTypeId, item.type_name || "")),
      vod_content: text(scrapeData?.overview || item.vod_content).replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim(),
      vod_play_sources: playSources,
      vod_douban_score: text(scrapeData?.voteAverage != null ? Number(scrapeData.voteAverage).toFixed(1) : (item.vod_douban_score || ""))
    };

    return { list: [vod] };
  } catch (error) {
    await OmniBox.log("error", `detail 失败: ${error.message}`);
    return { list: [] };
  }
}

async function play(params, context) {
  try {
    const playId = text(params?.playId || "");
    const meta = b64Decode(playId);
    const url = fixUrl(meta.url || "");
    const resourceId = text(meta.resourceId || "");
    const fileId = text(meta.fileId || "");
    const vodId = text(meta.vodId || "");
    const title = text(meta.name || params?.title || "");
    const epName = text(meta.epName || "");

    if (!url) {
      return { urls: [], parse: 1, header: { "User-Agent": UA, "Referer": `${HOST}/` }, danmaku: [] };
    }

    let danmaku = [];
    let scrapeData = null;
    let mapping = null;

    if (resourceId && fileId) {
      try {
        const metadata = await OmniBox.getScrapeMetadata(resourceId);
        scrapeData = metadata?.scrapeData || null;
        const mappings = Array.isArray(metadata?.videoMappings) ? metadata.videoMappings : [];
        mapping = mappings.find((m) => String(m?.fileId || "") === fileId) || null;

        const fileName = buildDanmakuFileName(scrapeData, mapping, title, epName);
        if (fileName) {
          danmaku = await OmniBox.getDanmakuByFileName(fileName);
        }
      } catch (error) {
        await OmniBox.log("warn", `[play] 弹幕匹配失败: ${error.message}`);
      }
    }

    const parse = /\.(m3u8|mp4|flv|webm)(\?|$)/i.test(url) ? 0 : 1;
    const header = { "User-Agent": UA, "Referer": `${HOST}/` };
return { urls: [{ name: epName || meta.flag || "播放", url }], parse, header, danmaku: Array.isArray(danmaku) ? danmaku : [] };
  } catch (error) {
    await OmniBox.log("error", `play 失败: ${error.message}`);
    return { urls: [], parse: 1, header: { "User-Agent": UA, "Referer": `${HOST}/` }, danmaku: [] };
  }
}

module.exports = { home, category, search, detail, play };
runner.run(module.exports);
