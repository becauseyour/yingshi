// @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E8%A7%A3%E6%9E%90js/磁力熊.js
// @name 磁力熊
// @author 梦
// @description 磁力资源站：域名已切 cilixiong.org；支持首页/分类/详情/搜索与磁力线路
// @dependencies cheerio
// @version 1.0.3
// @downloadURL https://gh-proxy.org/https://github.com/Silent1566/OmniBox-Spider/raw/refs/heads/main/影视/磁力/磁力熊.js

const OmniBox = require("omnibox_sdk");
const runner = require("spider_runner");
const cheerio = require("cheerio");

const BASE_URL = "https://www.cilixiong.org";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36";
const DETAIL_CACHE_TTL = Number(process.env.CILIXIONG_DETAIL_CACHE_TTL || 1800);
const LIST_CACHE_TTL = Number(process.env.CILIXIONG_LIST_CACHE_TTL || 900);
const SEARCH_CACHE_TTL = Number(process.env.CILIXIONG_SEARCH_CACHE_TTL || 900);
const SOURCE_NAMES_CONFIG = (process.env.SOURCE_NAMES_CONFIG || "本地代理;服务端代理;直连")
  .split(";")
  .map((s) => s.trim())
  .filter(Boolean);
const MAGNET_LOCAL_SCHEME = String(process.env.MAGNET_LOCAL_SCHEME || "").trim();
const MAGNET_PROXY_API = String(process.env.MAGNET_PROXY_API || "").trim();

const CATEGORY_CONFIG = [
  { id: "movie", name: "电影", path: "/movie/" },
  { id: "tv", name: "剧集", path: "/drama/" },
  { id: "top250", name: "豆瓣电影Top250", path: "/top250/" },
  { id: "imdbtop250", name: "IMDB Top250", path: "/s/imdbtop250/" },
  { id: "suspense", name: "高分悬疑片", path: "/s/suspense/" },
  { id: "comedy", name: "高分喜剧片", path: "/s/comedy/" },
  { id: "biopic", name: "高分传记片", path: "/s/biopic/" },
  { id: "romance", name: "高分爱情片", path: "/s/romance/" },
  { id: "crime", name: "高分犯罪片", path: "/s/crime/" },
  { id: "horror", name: "高分恐怖片", path: "/s/horror/" },
  { id: "adventure", name: "高分冒险片", path: "/s/adventure/" },
  { id: "martial", name: "高分武侠片", path: "/s/martial/" },
  { id: "fantasy", name: "高分奇幻片", path: "/s/fantasy/" },
  { id: "history", name: "高分历史片", path: "/s/history/" },
  { id: "war", name: "高分战争片", path: "/s/war/" },
  { id: "musical", name: "高分歌舞片", path: "/s/musical/" },
  { id: "disaster", name: "高分灾难片", path: "/s/disaster/" },
  { id: "west", name: "高分西部片", path: "/s/west/" },
  { id: "music", name: "高分音乐片", path: "/s/music/" },
  { id: "sci-fi", name: "高分科幻片", path: "/s/sci-fi/" },
  { id: "action", name: "高分动作片", path: "/s/action/" },
  { id: "animation", name: "高分动画片", path: "/s/animation/" },
  { id: "documentary", name: "高分纪录片", path: "/s/documentary/" },
  { id: "unpopular", name: "冷门佳片", path: "/s/unpopular/" },
];

const CATEGORY_MAP = new Map(CATEGORY_CONFIG.map((item) => [item.id, item]));

module.exports = { home, category, detail, search, play };
runner.run(module.exports);

async function requestText(url, options = {}, redirectCount = 0) {
  await OmniBox.log("info", `[磁力熊][request] ${options.method || "GET"} ${url}`);
  const res = await OmniBox.request(url, {
    method: options.method || "GET",
    headers: {
      "User-Agent": UA,
      "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
      Referer: BASE_URL + "/",
      ...(options.headers || {}),
    },
    body: options.body,
    timeout: options.timeout || 20000,
  });
  const statusCode = Number(res?.statusCode || 0);
  if ([301, 302, 303, 307, 308].includes(statusCode) && redirectCount < 5) {
    const location = res?.headers?.location || res?.headers?.Location || res?.headers?.LOCATION;
    if (location) {
      const nextUrl = absoluteUrl(location);
      await OmniBox.log("info", `[磁力熊][redirect] ${url} -> ${nextUrl}`);
      return await requestText(nextUrl, options, redirectCount + 1);
    }
  }
  if (!res || statusCode !== 200) {
    throw new Error(`HTTP ${res?.statusCode || "unknown"} @ ${url}`);
  }
  return String(res.body || "");
}

async function getCachedText(cacheKey, ttl, producer) {
  try {
    const cached = await OmniBox.getCache(cacheKey);
    if (cached) return String(cached);
  } catch (_) {}
  const value = await producer();
  try {
    await OmniBox.setCache(cacheKey, String(value), ttl);
  } catch (_) {}
  return value;
}

function normalizeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function stripHtml(value) {
  return normalizeText(String(value || "").replace(/<[^>]+>/g, " "));
}

function absoluteUrl(url) {
  try {
    return new URL(url, BASE_URL).toString();
  } catch (_) {
    return String(url || "");
  }
}

function decodeMaybeGarbled(text) {
  const raw = String(text || "");
  if (!/[ÃÂÐÑ]/.test(raw) && !/ç|è|ä|å|æ|é|ê|ë|ï|î|ô|û|ù/.test(raw)) return raw;
  try {
    return Buffer.from(raw, "latin1").toString("utf8");
  } catch (_) {
    return raw;
  }
}

function extractBgImage(style) {
  const match = String(style || "").match(/url\(['"]?([^'")]+)['"]?\)/i);
  return match ? absoluteUrl(match[1]) : "";
}

function mapCard($, el, fallbackTypeName = "") {
  const node = $(el);
  const href = node.find("a[href]").first().attr("href") || "";
  const title = decodeMaybeGarbled(normalizeText(node.find("h2").first().text()));
  const score = normalizeText(node.find(".rank").first().text());
  const year = normalizeText(node.find(".small").first().text());
  const pic = extractBgImage(node.find(".card-img").first().attr("style"));
  const id = String(href || "").match(/\/(movie|tv|drama)\/(\d+)\.html/i)?.[2] || href;
  return {
    vod_id: absoluteUrl(href),
    vod_name: title,
    vod_pic: pic,
    vod_year: year,
    vod_remarks: [score, year].filter(Boolean).join(" / "),
    type_name: fallbackTypeName,
    _id: id,
  };
}

function buildCategoryUrl(categoryId, page, filter = {}) {
  const category = CATEGORY_MAP.get(String(categoryId || "movie")) || CATEGORY_CONFIG[0];
  const currentPage = Math.max(1, Number(page) || 1);
  const categoryPath = category.path;
  if (categoryId === "movie" || categoryId === "tv") {
    const klass = String(filter.class || "0").trim() || "0";
    const area = String(filter.area || "0").trim() || "0";
    if (klass === "0" && area === "0") {
      if (currentPage === 1) return absoluteUrl(categoryPath);
      return absoluteUrl(`${categoryPath}index_${currentPage}.html`);
    }
    // 剧集分类前缀为 2，电影为 1（站点路径约定）
    const prefix = categoryId === "tv" ? "2" : "1";
    return absoluteUrl(`/${prefix}-${klass}-${area}-(${currentPage}-1).html`);
  }
  if (currentPage === 1) return absoluteUrl(categoryPath);
  return absoluteUrl(`${categoryPath}index_${currentPage}.html`);
}

function parseDetailMeta(htmlText) {
  const $ = cheerio.load(htmlText);
  const detailBlock = $(".mv_detail").first();
  const title = decodeMaybeGarbled(normalizeText(detailBlock.find("h1").first().text()));
  const pic = absoluteUrl($("meta[property='og:image']").attr("content") || "");
  const content = decodeMaybeGarbled(normalizeText($("meta[property='og:description']").attr("content") || $("meta[name='description']").attr("content") || ""));
  const metaMap = {};
  detailBlock.find("p").each((_, p) => {
    const text = decodeMaybeGarbled(stripHtml($(p).html() || $(p).text()));
    if (!text) return;
    const idx = text.indexOf("：");
    if (idx > 0) {
      metaMap[text.slice(0, idx)] = text.slice(idx + 1).trim();
    }
  });
  return {
    title,
    pic,
    content,
    score: metaMap["豆瓣评分"] || "",
    alias: metaMap["又名"] || "",
    date: metaMap["上映日期"] || "",
    type: metaMap["类型"] || "",
    duration: metaMap["片长"] || "",
    area: metaMap["上映地区"] || "",
    actors: metaMap["主演"] || "",
    update: metaMap["最后更新于"] || "",
  };
}

function parseResourceEpisodes(htmlText) {
  const $ = cheerio.load(htmlText);
  const episodes = [];
  const seen = new Set();
  $("a[href]").each((_, a) => {
    const href = ($(a).attr("href") || "").trim();
    if (!href) return;
    let seedType = "";
    if (href.startsWith("magnet:")) seedType = "magnet";
    else if (href.startsWith("ed2k://")) seedType = "ed2k";
    else if (/\.torrent($|\?)/i.test(href)) seedType = "torrent";
    else return;
    const rawName = decodeMaybeGarbled(normalizeText($(a).text())) || `${seedType}资源`;
    const quality = normalizeText((rawName.match(/(4K|2160P|1080P|720P|WEB-DL|BluRay|BD|HDR|REMUX)/i) || [])[1] || "");
    const size = normalizeText((rawName.match(/\[(\d+(?:\.\d+)?\s*[GMTK]B?)\]/i) || [])[1] || "");
    const episodeName = size ? rawName.replace(/\s*\[[^\]]+\]\s*$/,'').trim() || rawName : rawName;
    const key = `${seedType}@@${href}`;
    if (seen.has(key)) return;
    seen.add(key);
    const prefix = seedType === "magnet" ? "🧲磁力" : seedType === "ed2k" ? "⚡电驴" : "🧩种子";
    episodes.push({
      name: episodeName,
      playId: href,
      _sortKey: rawName,
      _prefix: quality ? `${prefix}·${quality}` : prefix,
    });
  });
  episodes.sort((a, b) => String(a._sortKey).localeCompare(String(b._sortKey), "zh-Hans-CN"));
  const groups = new Map();
  for (const ep of episodes) {
    const key = ep._prefix;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({ name: ep.name, playId: ep.playId });
  }
  return Array.from(groups.entries()).map(([name, episodes]) => ({ name, episodes }));
}

function buildPlayUrls(meta) {
  const link = String(meta?.link || meta?.url || "").trim();
  const urls = [];
  if (MAGNET_LOCAL_SCHEME) {
    const localName = SOURCE_NAMES_CONFIG[0] || "本地代理";
    const localUrl = MAGNET_LOCAL_SCHEME.includes("{")
      ? MAGNET_LOCAL_SCHEME.replaceAll("{url}", encodeURIComponent(link))
      : `${MAGNET_LOCAL_SCHEME}${encodeURIComponent(link)}`;
    urls.push({ name: localName, url: localUrl });
  }
  if (MAGNET_PROXY_API) {
    const proxyName = SOURCE_NAMES_CONFIG[1] || "服务端代理";
    const joiner = MAGNET_PROXY_API.includes("?") ? "&" : "?";
    urls.push({ name: proxyName, url: `${MAGNET_PROXY_API}${joiner}url=${encodeURIComponent(link)}` });
  }
  const directName = SOURCE_NAMES_CONFIG[SOURCE_NAMES_CONFIG.length - 1] || "直连";
  urls.push({ name: directName, url: link });
  return urls;
}

async function home() {
  try {
    const html = await getCachedText("cilixiong:home", LIST_CACHE_TTL, () => requestText(absoluteUrl("/")));
    const $ = cheerio.load(html);
    const list = $(".col").slice(1, 13).toArray().map((el) => mapCard($, el, "电影")).filter((item) => item.vod_id && item.vod_name);
    await OmniBox.log("info", `[磁力熊][home] list=${list.length}`);
    return {
      class: CATEGORY_CONFIG.map(({ id, name }) => ({ type_id: id, type_name: name })),
      list,
      filters: {
        movie: [
          {
            key: "class",
            name: "类型",
            value: [
              { name: "全部", value: "0" }, { name: "剧情", value: "1" }, { name: "喜剧", value: "2" }, { name: "惊悚", value: "3" },
              { name: "动作", value: "4" }, { name: "爱情", value: "5" }, { name: "犯罪", value: "6" }, { name: "恐怖", value: "7" },
              { name: "冒险", value: "8" }, { name: "悬疑", value: "9" }, { name: "科幻", value: "10" }, { name: "家庭", value: "11" },
              { name: "奇幻", value: "12" }, { name: "动画", value: "13" }, { name: "战争", value: "14" }, { name: "历史", value: "15" },
              { name: "传记", value: "16" }, { name: "音乐", value: "17" }, { name: "歌舞", value: "18" }, { name: "运动", value: "19" },
              { name: "西部", value: "20" }, { name: "灾难", value: "21" }, { name: "古装", value: "22" },
              { name: "同性", value: "24" }, { name: "儿童", value: "25" }, { name: "纪录片", value: "26" },
            ],
          },
          {
            key: "area",
            name: "地区",
            value: [
              { name: "全部", value: "0" }, { name: "大陆", value: "1" }, { name: "香港", value: "2" }, { name: "台湾", value: "3" },
              { name: "美国", value: "4" }, { name: "日本", value: "5" }, { name: "韩国", value: "6" }, { name: "英国", value: "7" },
              { name: "法国", value: "8" }, { name: "德国", value: "9" }, { name: "印度", value: "10" }, { name: "泰国", value: "11" },
              { name: "丹麦", value: "12" }, { name: "瑞典", value: "13" }, { name: "巴西", value: "14" }, { name: "加拿大", value: "15" },
              { name: "俄罗斯", value: "16" }, { name: "意大利", value: "17" }, { name: "比利时", value: "18" }, { name: "爱尔兰", value: "19" },
              { name: "西班牙", value: "20" }, { name: "澳大利亚", value: "21" }, { name: "波兰", value: "22" }, { name: "土耳其", value: "23" },
              { name: "越南", value: "24" },
            ],
          },
        ],
        tv: [
          {
            key: "class",
            name: "类型",
            value: [
              { name: "全部", value: "0" }, { name: "剧情", value: "1" }, { name: "喜剧", value: "2" }, { name: "惊悚", value: "3" },
              { name: "动作", value: "4" }, { name: "爱情", value: "5" }, { name: "犯罪", value: "6" }, { name: "恐怖", value: "7" },
              { name: "冒险", value: "8" }, { name: "悬疑", value: "9" }, { name: "科幻", value: "10" }, { name: "家庭", value: "11" },
              { name: "奇幻", value: "12" }, { name: "动画", value: "13" }, { name: "战争", value: "14" }, { name: "历史", value: "15" },
              { name: "传记", value: "16" }, { name: "音乐", value: "17" }, { name: "歌舞", value: "18" }, { name: "运动", value: "19" },
              { name: "西部", value: "20" }, { name: "灾难", value: "21" }, { name: "古装", value: "22" },
              { name: "同性", value: "24" }, { name: "儿童", value: "25" }, { name: "纪录片", value: "26" },
            ],
          },
          {
            key: "area",
            name: "地区",
            value: [
              { name: "全部", value: "0" }, { name: "大陆", value: "1" }, { name: "香港", value: "2" }, { name: "台湾", value: "3" },
              { name: "美国", value: "4" }, { name: "日本", value: "5" }, { name: "韩国", value: "6" }, { name: "英国", value: "7" },
              { name: "法国", value: "8" }, { name: "德国", value: "9" }, { name: "印度", value: "10" }, { name: "泰国", value: "11" },
              { name: "丹麦", value: "12" }, { name: "瑞典", value: "13" }, { name: "巴西", value: "14" }, { name: "加拿大", value: "15" },
              { name: "俄罗斯", value: "16" }, { name: "意大利", value: "17" }, { name: "比利时", value: "18" }, { name: "爱尔兰", value: "19" },
              { name: "西班牙", value: "20" }, { name: "澳大利亚", value: "21" }, { name: "波兰", value: "22" }, { name: "土耳其", value: "23" },
              { name: "越南", value: "24" },
            ],
          },
        ],
      },
    };
  } catch (error) {
    await OmniBox.log("error", `[磁力熊][home] ${error.message}`);
    return { class: CATEGORY_CONFIG.map(({ id, name }) => ({ type_id: id, type_name: name })), list: [] };
  }
}

async function category(params = {}) {
  try {
    const categoryId = String(params.type_id || params.categoryId || params.id || "movie");
    const page = Math.max(1, Number(params.page) || 1);
    const url = buildCategoryUrl(categoryId, page, params.filter || {});
    const cacheKey = `cilixiong:category:${categoryId}:${page}:${JSON.stringify(params.filter || {})}`;
    const html = await getCachedText(cacheKey, LIST_CACHE_TTL, () => requestText(url));
    const $ = cheerio.load(html);
    const typeName = CATEGORY_MAP.get(categoryId)?.name || "磁力";
    const list = $(".col").toArray().map((el) => mapCard($, el, typeName)).filter((item) => item.vod_id && item.vod_name);
    await OmniBox.log("info", `[磁力熊][category] type=${categoryId} page=${page} list=${list.length}`);
    return { list, page, pagecount: list.length ? page + 1 : page, limit: list.length, total: page * list.length + (list.length ? 1 : 0) };
  } catch (error) {
    await OmniBox.log("error", `[磁力熊][category] ${error.message}`);
    return { list: [], page: Number(params.page) || 1, pagecount: Number(params.page) || 1, limit: 0, total: 0 };
  }
}

async function detail(params = {}) {
  try {
    const vodId = absoluteUrl(params.id || params.videoId || params.vod_id || "");
    const cacheKey = `cilixiong:detail:${vodId}`;
    const html = await getCachedText(cacheKey, DETAIL_CACHE_TTL, () => requestText(vodId));
    const meta = parseDetailMeta(html);
    const playSources = parseResourceEpisodes(html);
    await OmniBox.log("info", `[磁力熊][detail] id=${vodId} sources=${playSources.length}`);
    return {
      list: [{
        vod_id: vodId,
        vod_name: meta.title,
        vod_pic: meta.pic,
        type_name: meta.type,
        vod_year: meta.date,
        vod_area: meta.area,
        vod_actor: meta.actors,
        vod_remarks: [meta.score ? `豆瓣${meta.score}` : "", meta.duration].filter(Boolean).join(" / "),
        vod_content: meta.content,
        vod_play_sources: playSources,
      }],
    };
  } catch (error) {
    await OmniBox.log("error", `[磁力熊][detail] ${error.message}`);
    return { list: [] };
  }
}

async function search(params = {}) {
  try {
    const wd = normalizeText(params.wd || params.keyword || params.q || "");
    if (!wd) return { list: [] };
    const cacheKey = `cilixiong:search:${wd}`;
    const html = await getCachedText(cacheKey, SEARCH_CACHE_TTL, async () => {
      const body = new URLSearchParams({ classid: "1,2", show: "title", tempid: "1", keyboard: wd }).toString();
      try {
        return await requestText(`${BASE_URL}/e/search/index.php`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body,
        });
      } catch (postError) {
        await OmniBox.log("warn", `[磁力熊][search] POST failed, fallback GET: ${postError.message}`);
        return await requestText(`${BASE_URL}/e/search/index.php?${body}`);
      }
    });
    const $ = cheerio.load(html);
    let list = $(".col").toArray().map((el) => mapCard($, el)).filter((item) => item.vod_id && item.vod_name);
    if (!list.length) {
      list = $("a[href*='/movie/'], a[href*='/tv/'], a[href*='/drama/']").toArray().map((el) => {
        const node = $(el);
        const href = node.attr("href") || "";
        const title = decodeMaybeGarbled(normalizeText(node.text()));
        return {
          vod_id: absoluteUrl(href),
          vod_name: title,
          vod_pic: "",
          vod_remarks: "",
        };
      }).filter((item, idx, arr) => item.vod_id && item.vod_name && arr.findIndex((x) => x.vod_id === item.vod_id) === idx);
    }
    await OmniBox.log("info", `[磁力熊][search] wd=${wd} list=${list.length}`);
    return { list };
  } catch (error) {
    await OmniBox.log("error", `[磁力熊][search] ${error.message}`);
    return { list: [] };
  }
}

async function play(params = {}) {
  try {
    const raw = String(params.id || params.playId || "").trim();
    const seedType = raw.startsWith("magnet:") ? "magnet" : raw.startsWith("ed2k://") ? "ed2k" : /\.torrent($|\?)/i.test(raw) ? "torrent" : "magnet";
    const urls = buildPlayUrls({ link: raw, url: raw, seedType });
    await OmniBox.log("info", `[磁力熊][play] type=${seedType} urls=${urls.length}`);
    return {
      parse: 0,
      header: {},
      urls: urls
    };
  } catch (error) {
    await OmniBox.log("error", `[磁力熊][play] ${error.message}`);
    return { parse: 0, header: {}, urls: [] };
  }
}
