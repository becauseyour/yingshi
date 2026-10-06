// @name 聚影
// @author
// @description 刮削：支持，弹幕：支持，播放记录：支持
// @dependencies: axios
// @version 1.1.5
// @downloadURL https://raw.githubusercontent.com/Silent1566/OmniBox-Spider/main/影视/网盘/聚影.js

// ==================== 配置区域 ====================
function splitConfigList(value) {
  return String(value || "")
    .split(/[;,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

// 站点地址:可填一个或多个(逗号/分号分隔),运行时按顺序探测,能连上的自动作为当前站点
// 留空则依次尝试 https://www.jying.top -> https://jying.top
const SITE_CANDIDATES = (() => {
  const raw = splitConfigList(process.env.JUYING_WEB_SITE || "");
  const list = (raw.length ? raw : ["https://www.jying.top", "https://jying.top"]).map((item) =>
    String(item || "").trim().replace(/\/+$/, "")
  );
  for (const item of list) {
    if (!/^https?:\/\//i.test(item)) {
      throw new Error(`JUYING_WEB_SITE 配置必须是 http(s) 地址: ${item}`);
    }
  }
  return list;
})();
// 账号密码(默认值即为聚影账号)
let AUTH_USERNAME = String(process.env.JUYING_USERNAME || "").trim();
let AUTH_PASSWORD = String(process.env.JUYING_PASSWORD || "").trim();
const STATIC_TOKEN = String(process.env.JUYING_TOKEN || "").trim();
const STATIC_COOKIE = String(process.env.JUYING_COOKIE || "").trim();
// 请求超时(毫秒)
const REQUEST_TIMEOUT = Math.max(3000, parseInt(process.env.JUYING_TIMEOUT || "20000", 10) || 20000);
// 每页条数
const PAGE_SIZE = Math.max(1, parseInt(process.env.JUYING_LIMIT || "24", 10) || 24);
// 单个影片最多处理的资源数(站点对资源接口有频率限制,不宜过大)
const MAX_RESOURCES = Math.max(1, parseInt(process.env.JUYING_MAX_RESOURCES || "20", 10) || 20);
// 最多拉取的资源页数
const MAX_RESOURCE_PAGES = Math.max(1, parseInt(process.env.JUYING_MAX_RESOURCE_PAGES || "3", 10) || 3);
// 单条线路最多枚举的网盘分享数
const MAX_PAN_SHARES = Math.max(1, parseInt(process.env.JUYING_MAX_PAN_SHARES || "6", 10) || 6);
// 单条线路提前解析真实链接的资源数(每条资源一次 access 请求,受站点频率限制)
const MAX_ACCESS_PER_GROUP = Math.max(1, parseInt(process.env.JUYING_MAX_ACCESS || "6", 10) || 6);
// 单条线路最多返回的选集数
const MAX_EPISODES = Math.max(1, parseInt(process.env.JUYING_MAX_EPISODES || "200", 10) || 200);
const MAX_FAILURE_HINTS = 3;
// 缓存时间(秒)
const CACHE_EX_SECONDS = Math.max(60, parseInt(process.env.JUYING_CACHE_EX_SECONDS || "43200", 10) || 43200);
// 是否开启刮削(弹幕/元数据)
const SCRAPING_ENABLED = String(process.env.JUYING_SCRAPING || "true").toLowerCase() !== "false";
// 网盘类型:命中时详情页拆分为多条线路(115 走直连单线路,不需要本地/服务端代理)
const DRIVE_TYPE_CONFIG = splitConfigList(
  process.env.DRIVE_TYPE_CONFIG || "quark;uc"
).map((item) => item.toLowerCase());
// 线路名称和顺序
const SOURCE_NAMES_CONFIG = splitConfigList(process.env.SOURCE_NAMES_CONFIG || "本地代理;服务端代理;直连");
// 详情页播放线路的网盘排序顺序
const DRIVE_ORDER = splitConfigList(
  process.env.DRIVE_ORDER || "baidu;quark;115;uc;123pan;tianyi;ali;guangya;xunlei"
).map((item) => item.toLowerCase());
// 是否开启外网服务器代理(默认关闭)
const EXTERNAL_SERVER_PROXY_ENABLED = String(process.env.EXTERNAL_SERVER_PROXY_ENABLED || "false").toLowerCase() === "true";
const SITE_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";
// 磁力 115 秒传:配置 115 Cookie 后,详情页把磁力离线到 115 网盘并按文件生成分集
const MAGNET_115_COOKIE = String(
  process.env.JUYING_115_COOKIE || process.env.PAN_115_COOKIE || process.env.GLOBAL_115_COOKIE || ""
).trim();
const MAGNET_115_ENABLED =
  !!MAGNET_115_COOKIE && String(process.env.JUYING_MAGNET_115 || "true").toLowerCase() !== "false";
// 单个详情最多秒传的磁力条数(每条需要一次 access 请求,站点对 access 有限流)
const rawMaxMagnet115 = parseInt(process.env.JUYING_MAX_MAGNET_115 === undefined ? "2" : process.env.JUYING_MAX_MAGNET_115, 10);
const MAX_MAGNET_115 = Number.isFinite(rawMaxMagnet115) ? Math.max(0, rawMaxMagnet115) : 2;
// 115 秒传结果缓存时间(秒)
const MAGNET_115_CACHE_EX = Math.max(600, parseInt(process.env.JUYING_MAGNET_115_CACHE || "86400", 10) || 86400);
// TMDB 密钥:填在引号里(例: "abcd1234efgh"),与全局环境变量 TMDB_API_KEY 效果一致;留空则使用环境变量
const TMDB_API_KEY = "";
// TMDB 代理(可选):直连超时/被墙时填,如 "http://127.0.0.1:7890";留空则自动用 HTTPS_PROXY/HTTP_PROXY 环境变量
const TMDB_PROXY = "";
// 弹幕接口:填在引号里(例: "https://your-danmaku-api"),与全局环境变量 DANMU_API 效果一致;留空则使用环境变量
const DANMU_API = "";
if (TMDB_API_KEY) process.env.TMDB_API_KEY = String(TMDB_API_KEY).trim();
if (TMDB_PROXY) process.env.TMDB_PROXY = String(TMDB_PROXY).trim();
if (DANMU_API) process.env.DANMU_API = String(DANMU_API).trim();
// ==================== 配置区域结束 ====================

// 引入 OmniBox SDK(必须在配置区域之后:保证 TMDB_API_KEY / DANMU_API 已写入环境变量)
// 本地调试时若模块缺失则 fallback，保证 node --check 可通过
let OmniBox;
try {
  OmniBox = require("omnibox_sdk");
} catch (_) {
  OmniBox = {
    log(l, m) {
      console.log(`[${l}] ${m}`);
    },
    async request() {
      return { statusCode: 0, body: "" };
    },
    async getCache() {
      return null;
    },
    async setCache() {},
    async getDriveInfoByShareURL() {
      return {};
    },
    async getDriveFileList() {
      return { files: [] };
    },
    async getDriveVideoPlayInfo() {
      return { url: [] };
    },
    async processScraping() {},
    async getScrapeMetadata() {
      return null;
    },
    async getDanmakuByFileName() {
      return [];
    },
    async addPlayHistory() {
      return false;
    },
  };
}
// 引入 axios(用于 HTTP 请求)
let axios;
try {
  axios = require("axios");
} catch (error) {
  throw new Error("axios 模块未找到,请先安装:npm install axios");
}
const https = require("https");
const http = require("http");
const net = require("net");
const tls = require("tls");
const crypto = require("crypto");

OmniBox.log("info", `聚影 站点候选: ${SITE_CANDIDATES.join(" -> ")}`);

const INSECURE_HTTPS_AGENT = new https.Agent({ rejectUnauthorized: false });

// ==================== 站点选择 ====================
let WEB_SITE = "";
let siteIndex = 0;
let sitePromise = null;

// 网络层失败时丢弃当前站点,下次从下一个候选继续探测
function invalidateWebSite() {
  if (!WEB_SITE) return;
  const idx = SITE_CANDIDATES.indexOf(WEB_SITE);
  siteIndex = idx >= 0 ? (idx + 1) % SITE_CANDIDATES.length : 0;
  WEB_SITE = "";
}

function probeSite(site) {
  return httpRequest(`${site}/api/csrf/`, {
    headers: {
      "User-Agent": SITE_UA,
      Accept: "application/json, text/plain, */*",
      Referer: `${site}/categories`,
    },
    timeout: Math.min(REQUEST_TIMEOUT, 8000),
  });
}

async function resolveWebSite() {
  if (WEB_SITE) return WEB_SITE;
  if (!sitePromise) {
    const start = siteIndex >= 0 && siteIndex < SITE_CANDIDATES.length ? siteIndex : 0;
    sitePromise = (async () => {
      for (let i = 0; i < SITE_CANDIDATES.length; i++) {
        const idx = (start + i) % SITE_CANDIDATES.length;
        const site = SITE_CANDIDATES[idx];
        try {
          const res = await probeSite(site);
          if (res.statusCode > 0 && res.statusCode < 500) {
            WEB_SITE = site;
            siteIndex = idx;
            OmniBox.log("info", `聚影 站点地址: ${WEB_SITE}`);
            return WEB_SITE;
          }
          OmniBox.log("warn", `聚影 站点探测不可用: ${site} (HTTP ${res.statusCode})`);
        } catch (error) {
          OmniBox.log("warn", `聚影 站点探测失败: ${site}, ${error.message}`);
        }
      }
      WEB_SITE = SITE_CANDIDATES[start];
      OmniBox.log("warn", `聚影 站点全部探测失败,暂用: ${WEB_SITE}`);
      return WEB_SITE;
    })().finally(() => {
      sitePromise = null;
    });
  }
  return sitePromise;
}

// ==================== 运行时状态 ====================
let authToken = String(STATIC_TOKEN || "");
let tokenRestored = false;
let loginPromise = null;
let loginFailedAt = 0;
const cookieJar = new Map();
const memCache = new Map();

// ==================== 基础工具 ====================
function parseJson(text) {
  if (typeof text !== "string" || !text.trim()) return null;
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch (error) {
    return null;
  }
}

function toPage(page) {
  const value = parseInt(String(page || "1"), 10);
  return Number.isFinite(value) && value > 0 ? value : 1;
}

function encodeBase64Url(raw) {
  return Buffer.from(String(raw), "utf8")
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function decodeBase64Url(value) {
  let text = String(value || "").replace(/-/g, "+").replace(/_/g, "/");
  text += "=".repeat((4 - (text.length % 4)) % 4);
  return Buffer.from(text, "base64").toString("utf8");
}

function encodeId(typ, data) {
  try {
    return `jy|${typ}|${encodeBase64Url(JSON.stringify(data || {}))}`;
  } catch (error) {
    return "";
  }
}

function decodeId(raw) {
  const parts = String(raw || "").split("|");
  if (parts.length < 3 || parts[0] !== "jy") return ["", {}];
  try {
    const data = JSON.parse(decodeBase64Url(parts.slice(2).join("|")));
    return [parts[1], data && typeof data === "object" ? data : {}];
  } catch (error) {
    return ["", {}];
  }
}

function encodePlayMeta(obj) {
  try {
    return encodeBase64Url(JSON.stringify(obj || {}));
  } catch (error) {
    return "";
  }
}

function decodePlayMeta(str) {
  if (!str) return {};
  try {
    const data = JSON.parse(decodeBase64Url(str));
    return data && typeof data === "object" ? data : {};
  } catch (error) {
    return {};
  }
}

function escapePlayName(value) {
  return String(value || "").replace(/\$/g, "＄").replace(/#/g, "＃").trim();
}

function clean(value) {
  return escapePlayName(String(value || "资源").replace(/\s+/g, " ").trim().slice(0, 120));
}

// 站点演员/导演字段可能是数组或字符串,统一成中文顿号分隔的字符串
function joinNames(value) {
  if (Array.isArray(value)) {
    return value
      .map((item) => (item && (item.name || item)) || "")
      .filter(Boolean)
      .join("、");
  }
  return String(value || "");
}

function basenameOf(url) {
  try {
    const parsed = new URL(String(url || ""));
    const path = parsed.pathname || "";
    const name = path.split("/").filter(Boolean).pop() || "";
    return name ? decodeURIComponent(name) : "";
  } catch (error) {
    return "";
  }
}

function dedupe(list) {
  const out = [];
  const seen = new Set();
  for (const item of Array.isArray(list) ? list : []) {
    const key = String((item && (item.id || item.share_link || item.title)) || item);
    if (key && !seen.has(key)) {
      seen.add(key);
      out.push(item);
    }
  }
  return out;
}

async function mapWithConcurrency(items, limit, handler) {
  const list = Array.isArray(items) ? items : [];
  const results = new Array(list.length);
  let index = 0;
  const workers = Array.from({ length: Math.max(1, Math.min(limit, list.length)) }, async () => {
    while (index < list.length) {
      const current = index++;
      results[current] = await handler(list[current], current);
    }
  });
  await Promise.all(workers);
  return results;
}

async function cacheGet(key) {
  try {
    return await OmniBox.getCache(key);
  } catch (error) {
    OmniBox.log("warn", `聚影 读取缓存失败: ${key}, ${error.message}`);
    return null;
  }
}

async function cacheSet(key, value, exSeconds) {
  try {
    await OmniBox.setCache(key, value, exSeconds || CACHE_EX_SECONDS);
  } catch (error) {
    OmniBox.log("warn", `聚影 写入缓存失败: ${key}, ${error.message}`);
  }
}

// ==================== Cookie / Header ====================
function captureCookies(headers) {
  let raw = headers ? headers["set-cookie"] : null;
  if (!raw) return;
  if (typeof raw === "string") raw = [raw];
  if (!Array.isArray(raw)) return;
  for (const item of raw) {
    const pair = String(item).split(";")[0] || "";
    const idx = pair.indexOf("=");
    if (idx <= 0) continue;
    const name = pair.slice(0, idx).trim();
    const value = pair.slice(idx + 1).trim();
    if (value) cookieJar.set(name, value);
    else cookieJar.delete(name);
  }
}

function cookieHeader() {
  const parts = [];
  for (const [name, value] of cookieJar.entries()) parts.push(`${name}=${value}`);
  return parts.join("; ");
}

function buildHeaders(extra) {
  const headers = {
    "User-Agent": SITE_UA,
    Accept: "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    Referer: `${WEB_SITE}/categories`,
  };
  const ck = cookieHeader() || STATIC_COOKIE;
  if (ck) headers.Cookie = ck;
  if (authToken) headers["X-App-User-Token"] = authToken;
  const csrf = cookieJar.get("csrftoken");
  if (csrf) headers["X-CSRFToken"] = csrf;
  return Object.assign(headers, extra || {});
}

// ==================== HTTP ====================
// 站点对请求频率敏感,统一限制最小请求间隔(设 JUYING_MIN_INTERVAL=0 可关闭)
const rawMinInterval = parseInt(process.env.JUYING_MIN_INTERVAL === undefined ? "150" : process.env.JUYING_MIN_INTERVAL, 10);
const MIN_REQUEST_INTERVAL = Number.isFinite(rawMinInterval) && rawMinInterval >= 0 ? rawMinInterval : 150;
let lastRequestAt = 0;

function waitNextRequest() {
  const now = Date.now();
  const wait = Math.max(0, lastRequestAt + MIN_REQUEST_INTERVAL - now);
  lastRequestAt = now + wait;
  if (wait <= 0) return Promise.resolve();
  return new Promise((resolve) => setTimeout(resolve, wait));
}

async function httpRequest(url, options = {}) {
  await waitNextRequest();
  const method = String(options.method || "GET").toUpperCase();
  const response = await axios({
    url,
    method,
    headers: options.headers || {},
    params: options.params,
    data: options.body,
    timeout: options.timeout || REQUEST_TIMEOUT,
    httpsAgent: INSECURE_HTTPS_AGENT,
    responseType: "text",
    validateStatus: () => true,
  });
  captureCookies(response.headers || {});
  let body = response.data;
  if (typeof body !== "string") {
    body = body === undefined || body === null ? "" : JSON.stringify(body);
  }
  return { statusCode: response.status, body, headers: response.headers || {} };
}

// ==================== 登录 ====================
async function doLogin() {
  if (!AUTH_USERNAME || !AUTH_PASSWORD) {
    OmniBox.log("warn", "聚影 登录跳过: 用户名或密码为空");
    loginFailedAt = Date.now();
    return false;
  }
  try {
    await resolveWebSite();
    await httpRequest(`${WEB_SITE}/api/csrf/`, { timeout: REQUEST_TIMEOUT });
    const headers = buildHeaders({ Origin: WEB_SITE, Referer: `${WEB_SITE}/login` });
    const response = await httpRequest(`${WEB_SITE}/api/app/login/`, {
      method: "POST",
      headers,
      body: { username: AUTH_USERNAME, password: AUTH_PASSWORD },
      timeout: REQUEST_TIMEOUT,
    });
    const data = parseJson(response.body) || {};
    authToken = String(data.token || "");
    if (authToken) {
      OmniBox.log("info", `聚影 登录成功: ${(data.user && data.user.username) || AUTH_USERNAME}`);
      await cacheSet("jy:token", authToken, 86400 * 6);
      return true;
    }
    OmniBox.log("warn", `聚影 登录失败: HTTP ${response.statusCode}`);
    loginFailedAt = Date.now();
    return false;
  } catch (error) {
    OmniBox.log("error", `聚影 登录异常: ${error.message}`);
    invalidateWebSite();
    loginFailedAt = Date.now();
    return false;
  }
}

async function ensureLogin() {
  if (authToken) return true;
  if (!tokenRestored) {
    tokenRestored = true;
    const cached = await cacheGet("jy:token");
    if (cached) authToken = String(cached);
    if (authToken) return true;
  }
  if (STATIC_COOKIE) return true;
  if (Date.now() - loginFailedAt < 8000) return false;
  if (!loginPromise) {
    loginPromise = doLogin().finally(() => {
      loginPromise = null;
    });
  }
  return loginPromise;
}

async function login(params = {}) {
  const username = String(params.username || AUTH_USERNAME || "").trim();
  const password = String(params.password || AUTH_PASSWORD || "").trim();
  if (!username || !password) {
    return { code: -1, msg: "用户名或密码未配置" };
  }
  AUTH_USERNAME = username;
  AUTH_PASSWORD = password;
  authToken = "";
  tokenRestored = true;
  loginFailedAt = 0;
  memCache.clear();
  const ok = await doLogin();
  return ok ? { code: 1, msg: "登录成功" } : { code: -1, msg: "登录失败" };
}

async function logout() {
  authToken = "";
  tokenRestored = true;
  cookieJar.clear();
  memCache.clear();
  await cacheSet("jy:token", "", 1);
  OmniBox.log("info", "聚影 已退出登录");
  return { code: 1, msg: "已退出" };
}

async function getLoginStatus() {
  const ok = await ensureLogin();
  if (!ok) return { loggedIn: false, username: "" };
  const data = await apiCall("/api/app/profile/");
  const user = data && data.user;
  if (user && user.username) return { loggedIn: true, username: user.username };
  if (data && data.status === "success") return { loggedIn: true, username: AUTH_USERNAME };
  return { loggedIn: false, username: "" };
}

// ==================== API 请求 ====================
const rateLimits = new Map();

function scopeForPath(path) {
  const p = String(path || "");
  if (/\/access\//.test(p)) return "resource_access";
  if (/\/resources\//.test(p)) return "resource_read";
  if (/\/movies\/|\/home-initial-data\//.test(p)) return "list_read";
  if (/\/detail\//.test(p)) return "detail_read";
  return "default";
}

function rateLimitRemaining(path) {
  const until = rateLimits.get(scopeForPath(path)) || 0;
  return Math.max(0, until - Date.now());
}

function noteRateLimit(parsed, path) {
  const retryAfter = parseInt((parsed && (parsed.retry_after || parsed.retryAfter)) || "", 10) || 300;
  const seconds = Math.min(Math.max(retryAfter, 30), 1800);
  const until = Date.now() + seconds * 1000;
  rateLimits.set(scopeForPath(path), until);
  const reported = String((parsed && parsed.limit_scope) || "").replace(/_cooldown$/, "");
  if (reported) rateLimits.set(reported, until);
  OmniBox.log(
    "warn",
    `聚影 站点触发限流(${reported || "未知范围"}),${seconds}秒后自动恢复: ${path}`
  );
}

async function apiCall(path, options = {}) {
  const params = options.params || null;
  const post = options.post;
  const cacheKey = `${post ? "p:" : "g:"}${path}|${JSON.stringify(params || {})}|${JSON.stringify(post || {})}`;
  if (memCache.has(cacheKey)) return memCache.get(cacheKey);
  const remaining = rateLimitRemaining(path);
  if (remaining > 0) {
    OmniBox.log("warn", `聚影 站点限流冷却中(${Math.ceil(remaining / 1000)}秒),跳过请求: ${path}`);
    return {};
  }

  let result = {};
  let cacheable = false;
  for (let attempt = 0; attempt < 2; attempt++) {
    await resolveWebSite();
    const ok = await ensureLogin();
    if (!ok) break;
    try {
      const response = await httpRequest(WEB_SITE + path, {
        method: post ? "POST" : "GET",
        headers: buildHeaders({ Referer: `${WEB_SITE}/categories` }),
        params: params || undefined,
        body: post,
        timeout: REQUEST_TIMEOUT,
      });
      const parsed = parseJson(response.body);
      if (response.statusCode === 429 || (parsed && parsed.code === "rate_limited")) {
        noteRateLimit(parsed, path);
        return {};
      }
      if (response.statusCode === 401 || response.statusCode === 403) {
        OmniBox.log("warn", `聚影 接口鉴权失败(${response.statusCode}),重新登录: ${path}`);
        authToken = "";
        await cacheSet("jy:token", "", 1);
        continue;
      }
      result = parsed || {};
      cacheable = Boolean(result) && Object.keys(result).length > 0 && result.status !== "error";
      break;
    } catch (error) {
      OmniBox.log("warn", `聚影 请求失败: ${path}, ${error.message}`);
      result = {};
      invalidateWebSite();
    }
  }

  if (cacheable) memCache.set(cacheKey, result);
  return result;
}

function overviewApi() {
  return apiCall("/api/app/categories/");
}

function homeInitialApi() {
  return apiCall("/api/app/home-initial-data/", { params: { page_size: 12 } });
}

function movieDetailApi(mid) {
  const cacheKey = `jy:detail:${mid}`;
  return (async () => {
    try {
      const cached = await cacheGet(cacheKey);
      if (cached && typeof cached === "object" && Object.keys(cached).length) return cached;
    } catch (error) {
      /* 忽略缓存读取失败 */
    }
    const result = await apiCall(`/api/app/movie/${encodeURIComponent(mid)}/detail/`);
    if (result && Object.keys(result).length) {
      try {
        await cacheSet(cacheKey, result, 1800);
      } catch (error) {
        /* 忽略缓存写入失败 */
      }
    }
    return result;
  })();
}

function capResources(list, max) {
  if (list.length <= max) return list;
  const groups = groupByResourceType(list);
  const buckets = orderedGroupKeys(groups).map((key) => groups[key] || []);
  const picked = [];
  let offset = 0;
  while (picked.length < max) {
    let took = false;
    for (const bucket of buckets) {
      if (picked.length >= max) break;
      const item = bucket[offset];
      if (item !== undefined) {
        picked.push(item);
        took = true;
      }
    }
    if (!took) break;
    offset += 1;
  }
  return picked;
}

async function resourceListApi(mid) {
  const key = `res|${mid}`;
  if (memCache.has(key)) return memCache.get(key);
  // 播放器历史记录二次进入时站点常在限流冷却:先读持久缓存,进程重启也能出资源
  const storeKey = `jy:res:${mid}`;
  try {
    const stored = await cacheGet(storeKey);
    if (Array.isArray(stored) && stored.length) {
      memCache.set(key, stored);
      return stored;
    }
  } catch (error) {
    /* 忽略缓存读取失败 */
  }
  const list = [];
  let page = 1;
  while (page <= MAX_RESOURCE_PAGES && list.length < MAX_RESOURCES) {
    const data = await apiCall(`/api/app/movie/${encodeURIComponent(mid)}/resources/`, {
      params: { page, page_size: 120 },
    });
    const items = Array.isArray(data.resources) ? data.resources : [];
    if (!items.length) break;
    list.push(...items);
    if (!data.has_more) break;
    page += 1;
  }
  const result = capResources(dedupe(list), MAX_RESOURCES);
  if (result.length) {
    memCache.set(key, result);
    try {
      await cacheSet(storeKey, result, 600);
    } catch (error) {
      /* 忽略缓存写入失败 */
    }
  }
  return result;
}

// ==================== 资源真实链接 ====================
function attachSharePassword(url, code) {
  const shareURL = String(url || "");
  const pwd = String(code || "").trim();
  if (!shareURL || !pwd || !isPanShareUrl(shareURL)) return shareURL;
  if (/[?&](password|pass|pwd|code)=/i.test(shareURL)) return shareURL;
  return `${shareURL}${shareURL.includes("?") ? "&" : "?"}password=${encodeURIComponent(pwd)}`;
}

async function accessResource(x) {
  if (!x || typeof x !== "object") return "";
  const cacheKey = `access|${x.id || ""}|${x.access_ticket || ""}`;
  if (memCache.has(cacheKey)) return memCache.get(cacheKey);
  // 持久缓存:历史记录二次进入/限流冷却时直接复用上次拿到的分享链接
  const storeKey = `jy:${cacheKey}`;
  try {
    const stored = await cacheGet(storeKey);
    if (stored && typeof stored === "string") {
      memCache.set(cacheKey, stored);
      return stored;
    }
  } catch (error) {
    /* 忽略缓存读取失败 */
  }

  let target = "";
  if (x.target) {
    target = String(x.target);
  } else {
    const shared = x.share_link || x.raw_share_link || x.share_link_with_code || "";
    if (shared) target = String(shared);
    else {
      const rid = x.id;
      const ticket = x.access_ticket || x.ticket || "";
      if (rid && ticket) {
        const data = await apiCall(`/api/app/resource/${encodeURIComponent(rid)}/access/`, {
          post: { access_ticket: String(ticket) },
        });
        const raw = data.target || data.share_link || data.url || "";
        if (raw) {
          target = normalizePlayUrl(String(raw));
          target = attachSharePassword(target, data.access_code || data.extraction_code || "");
        }
      }
    }
  }

  target = normalizePlayUrl(target);
  if (target) {
    memCache.set(cacheKey, target);
    try {
      await cacheSet(storeKey, target, 7200);
    } catch (error) {
      /* 忽略缓存写入失败 */
    }
  }
  return target;
}

// 123云盘同一批分享有多个域名(123684/123685/123865/123912),OmniBox SDK 只认含 123pan 的域名,
// 其它域名会报"无法识别的分享链接格式"或被当成迅雷报"此分享不存在";
// 统一改写成 www.123pan.cn(与这些域名同一套 API,已验证 /api/share/info 与 /s/ 分享页都可用)并补 password 参数
const PAN123_HOST_MAP = {
  "123684.com": "www.123pan.cn",
  "123685.com": "www.123pan.cn",
  "123865.com": "www.123pan.cn",
  "123912.com": "www.123pan.cn",
};

function normalizePanShareURL(raw) {
  const value = String(raw || "");
  if (!value || !/^https?:\/\//i.test(value)) return value;
  const parts = value.match(/^(https?:\/\/)([^/?#]+)(.*)$/i);
  if (!parts) return value;
  const host = parts[2].toLowerCase().replace(/^www\./, "");
  const target = PAN123_HOST_MAP[host];
  let next = target ? `${parts[1]}${target}${parts[3]}` : value;
  if (target) {
    const pwd = next.match(/[?&]pwd=([^&#]+)/i);
    if (pwd && !/[?&]password=/i.test(next)) next += `${next.includes("?") ? "&" : "?"}password=${pwd[1]}`;
    OmniBox.log("info", `聚影 123分享域名改写: ${value.split("?")[0]} -> ${next.split("?")[0]}`);
  }
  return next;
}

const PAN123_FALLBACK_HOSTS = ["www.123pan.cn", "www.123pan.com", "www.123684.com", "www.123865.com"];

function isPan123URL(url) {
  const parts = String(url || "").match(/^https?:\/\/([^/?#]+)/i);
  if (!parts) return false;
  const host = parts[1].toLowerCase().replace(/^www\./, "");
  if (PAN123_HOST_MAP[host]) return true;
  return /(^|\.)123pan\.(cn|com)$/.test(host);
}

// 123 分享被 OmniBox SDK 识别失败时(无法识别的分享链接格式/被当成迅雷),按域名候选依次重试;
// 这些域名是同一套 123 云盘后端,先试 123pan.cn(已验证 API 与 /s/ 页面都可用),再试其它等价域名
async function pan123Candidates(raw) {
  const normalized = normalizePanShareURL(raw);
  if (!isPan123URL(normalized)) return [normalized];
  const parts = normalized.match(/^(https?:\/\/)([^/?#]+)(.*)$/i);
  if (!parts) return [normalized];
  const list = [];
  const preferred = await cacheGet(`jy:pan123:${normalized}`);
  if (preferred) list.push(String(preferred));
  if (/123pan/i.test(parts[2])) list.push(normalized);
  for (const host of PAN123_FALLBACK_HOSTS.concat([parts[2]])) {
    const candidate = `${parts[1]}${host}${parts[3]}`;
    if (!list.includes(candidate)) list.push(candidate);
  }
  return list;
}

function normalizePlayUrl(raw) {
  let value = String(raw || "").replace(/&amp;/g, "&").trim();
  while (value.length > 0 && (value.charAt(0) === '"' || value.charAt(0) === "'")) {
    value = value.slice(1).trim();
  }
  while (value.length > 0) {
    const last = value.charAt(value.length - 1);
    if (last !== '"' && last !== "'") break;
    value = value.slice(0, -1).trim();
  }
  if (!value) return "";
  const hasScheme = /^(https?|magnet|ed2k):/i.test(value);
  if (!hasScheme && /%3a%2f%2f/i.test(value)) {
    try {
      const decoded = decodeURIComponent(value).trim();
      if (/^(https?|magnet|ed2k):/i.test(decoded)) value = decoded;
    } catch (error) {
      // 保持原样
    }
  }
  return normalizePanShareURL(value.trim());
}

function isRawPlayable(url) {
  const value = String(url || "");
  const lower = value.toLowerCase();
  if (lower.startsWith("magnet:") || lower.startsWith("ed2k://")) return true;
  // 与 isVideoFile 同步:含 .iso/.vob 等,直链交给播放器(OK影视可播 .iso)
  return /\.(m3u8|mp4|flv|mkv|ts|webm|m4v|avi|mov|wmv|mpg|mpeg|vob|mts|m2ts|rm|rmvb|iso|3gp|ogv|ogm|asf|f4v|dat|tp|trp|ifo)(\?|#|$)/i.test(
    value
  );
}

function isPanShareUrl(url) {
  return /115|quark|aliyun|alipan|baidu|uc\.cn|123pan|123684|123685|123865|123912|189\.cn|139\.cn|xunlei|anxia|guangyapan|tianyi|pikpak/i.test(
    String(url || "")
  );
}

// 站点已标明网盘类型的资源一律按网盘枚举(分享域名会新增,如 123684.com,不能只靠 URL 特征判断)
const PAN_TYPE_KEYS = new Set([
  "115",
  "123",
  "baidu",
  "xunlei",
  "quark",
  "aliyun",
  "uc",
  "guangya",
  "tianyi",
  "pikpak",
  "mobile",
  "139",
  "189",
]);

function isPanResourceKey(key) {
  return PAN_TYPE_KEYS.has(String(key || "").toLowerCase());
}

// 直链/网盘分流:网盘类型的资源只要不是直链文件就走网盘枚举,这样 123684.com 之类的新域名也能出分集
function classifyPlayUrl(url, item) {
  const direct = isRawPlayable(url);
  if (isPanResourceKey(resourceType(item))) return direct ? "direct" : "pan";
  return isPanShareUrl(url) ? "pan" : "direct";
}

// 磁力/电驴只需在播放时取一次真实链接,详情页直接延迟解析,避免批量请求触发站点限流
function isLazyResourceType(item) {
  const key = resourceType(item);
  return key === "magnet" || key === "ed2k";
}

function compactResource(item) {
  const src = item && typeof item === "object" ? item : {};
  const out = {};
  for (const key of [
    "id",
    "access_ticket",
    "ticket",
    "share_link",
    "raw_share_link",
    "share_link_with_code",
    "target",
    "access_code",
    "extraction_code",
    "resource_type",
    "title",
    "resource_description",
  ]) {
    if (src[key] !== undefined && src[key] !== null && src[key] !== "") out[key] = src[key];
  }
  return out;
}

// ==================== 网盘文件枚举 ====================
function isVideoFile(file) {
  if (!file || !file.file_name) return false;
  const name = String(file.file_name).toLowerCase();
  // 与蜗牛4K.js 一致:含 .iso/.vob/.ifo 等光盘镜像,OK影视可直接播放
  const extensions = [
    ".mp4", ".mkv", ".avi", ".flv", ".mov", ".wmv", ".m3u8", ".ts", ".webm", ".m4v",
    ".mpg", ".mpeg", ".vob", ".mts", ".m2ts", ".rm", ".rmvb", ".iso", ".3gp", ".ogv",
    ".ogm", ".asf", ".f4v", ".dat", ".tp", ".trp", ".ifo",
  ];
  for (const ext of extensions) {
    if (name.endsWith(ext)) return true;
  }
  if (file.format_type) {
    const formatType = String(file.format_type).toLowerCase();
    if (
      formatType.includes("video") ||
      formatType.includes("mpeg") ||
      formatType.includes("h264") ||
      formatType.includes("iso")
    ) {
      return true;
    }
  }
  return false;
}

async function driveInfoCached(shareURL) {
  shareURL = normalizePanShareURL(shareURL);
  const key = `jy:drive:${shareURL}`;
  const cached = await cacheGet(key);
  if (cached && typeof cached === "object") return cached;
  const info = await OmniBox.getDriveInfoByShareURL(shareURL);
  const result = info && typeof info === "object" ? info : {};
  if (result.driveType) await cacheSet(key, result);
  return result;
}

async function rootFileListCached(shareURL) {
  shareURL = normalizePanShareURL(shareURL);
  const key = `jy:root:${shareURL}`;
  const cached = await cacheGet(key);
  if (cached && Array.isArray(cached.files)) return cached.files;
  const list = await OmniBox.getDriveFileList(shareURL, "0");
  const files = list && Array.isArray(list.files) ? list.files : [];
  if (files.length) await cacheSet(key, { files });
  return files;
}

async function collectVideoFiles(shareURL, files, depth) {
  if (!Array.isArray(files) || depth > 4) return [];
  const videos = [];
  const dirs = [];
  for (const file of files) {
    if (!file) continue;
    if (file.dir) {
      dirs.push(file);
      continue;
    }
    if (isVideoFile(file)) videos.push(file);
  }
  if (dirs.length) {
    const subLists = await mapWithConcurrency(dirs, 4, async (dir) => {
      try {
        const list = await OmniBox.getDriveFileList(shareURL, dir.fid);
        const children = list && Array.isArray(list.files) ? list.files : [];
        return await collectVideoFiles(shareURL, children, depth + 1);
      } catch (error) {
        OmniBox.log("warn", `聚影 获取子目录失败 [${dir.name || dir.fid}]: ${error.message}`);
        return [];
      }
    });
    for (const sub of subLists) {
      if (Array.isArray(sub)) videos.push(...sub);
    }
  }
  return videos;
}

async function videoFilesCached(shareURL) {
  const normalized = normalizePanShareURL(shareURL);
  const key = `jy:files:${normalized}`;
  const cached = await cacheGet(key);
  if (Array.isArray(cached) && cached.length) return cached;
  const candidates = await pan123Candidates(normalized);
  const errors = [];
  for (const candidate of candidates) {
    try {
      const roots = await rootFileListCached(candidate);
      const files = await collectVideoFiles(candidate, roots, 0);
      if (files.length) {
        if (candidate !== normalized) await cacheSet(`jy:pan123:${normalized}`, candidate, CACHE_EX_SECONDS);
        await cacheSet(key, files);
        return files;
      }
    } catch (error) {
      errors.push(error);
      if (candidates.length > 1) {
        OmniBox.log("warn", `聚影 枚举网盘文件失败(${candidate.split("?")[0]}): ${error.message}`);
      }
    }
  }
  if (errors.length) {
    if (candidates.length > 1) {
      const uniq = [...new Set(errors.map((error) => error.message))];
      throw new Error(`123分享候选域名均失败(${candidates.length}): ${uniq.join(" / ")}`);
    }
    throw errors[0];
  }
  return [];
}

function formatFileSize(size) {
  if (!size || size <= 0) return "";
  const units = ["B", "K", "M", "G", "T", "P"];
  let value = size;
  let exp = 0;
  while (value >= 1024 && exp < units.length - 1) {
    value /= 1024;
    exp += 1;
  }
  if (value === Math.floor(value)) return `${Math.floor(value)}${units[exp]}`;
  return `${value.toFixed(2)}${units[exp]}`;
}

// ==================== 站点字段工具 ====================
function resourceType(x) {
  const type = String((x && x.resource_type) || "other").toLowerCase();
  if (type === "magnetlink") return "magnet";
  if (type.includes("123")) return "123";
  if (type.includes("baidu")) return "baidu";
  if (type.includes("xunlei")) return "xunlei";
  if (type.includes("quark")) return "quark";
  if (type.includes("aliyun") || type.includes("alipan")) return "aliyun";
  if (type.includes("115")) return "115";
  if (type === "uc") return "uc";
  if (type.includes("ed2k")) return "ed2k";
  return type || "other";
}

const RESOURCE_NAME_MAP = {
  "123": "123云盘",
  baidu: "百度网盘",
  xunlei: "迅雷云盘",
  quark: "夸克网盘",
  aliyun: "阿里云盘",
  "115": "115网盘",
  uc: "UC网盘",
  magnet: "磁力",
  ed2k: "电驴",
  guangya: "光鸭云盘",
  tianyi: "天翼云盘",
  other: "其他",
};

function resourceName(key, x) {
  if (x && x.resource_type_display) return String(x.resource_type_display);
  return RESOURCE_NAME_MAP[key] || String(key || "其他");
}

// 网盘图标(与盘搜分组.js一致,无图标的分组走应用默认字母图标)
const PAN_PICS = {
  aliyun: "https://gh-proxy.org/https://github.com//power721/alist-tvbox/raw/refs/heads/master/web-ui/public/ali.jpg",
  quark: "https://gh-proxy.org/https://github.com//power721/alist-tvbox/raw/refs/heads/master/web-ui/public/quark.png",
  uc: "https://gh-proxy.org/https://github.com//power721/alist-tvbox/raw/refs/heads/master/web-ui/public/uc.png",
  pikpak: "https://gh-proxy.org/https://github.com//power721/alist-tvbox/raw/refs/heads/master/web-ui/public/pikpak.jpg",
  xunlei: "https://gh-proxy.org/https://github.com//power721/alist-tvbox/raw/refs/heads/master/web-ui/public/thunder.png",
  "123": "https://gh-proxy.org/https://github.com//power721/alist-tvbox/raw/refs/heads/master/web-ui/public/123.png",
  tianyi: "https://gh-proxy.org/https://github.com//power721/alist-tvbox/raw/refs/heads/master/web-ui/public/189.png",
  mobile: "https://gh-proxy.org/https://github.com//power721/alist-tvbox/raw/refs/heads/master/web-ui/public/139.jpg",
  "115": "https://gh-proxy.org/https://github.com//power721/alist-tvbox/raw/refs/heads/master/web-ui/public/115.jpg",
  baidu: "https://gh-proxy.org/https://github.com//power721/alist-tvbox/raw/refs/heads/master/web-ui/public/baidu.jpg",
};

const RESOURCE_ORDER = ["baidu", "115", "123", "xunlei", "quark", "aliyun", "uc", "guangya", "tianyi", "magnet", "ed2k", "other"];

function groupByResourceType(list) {
  const groups = {};
  for (const item of Array.isArray(list) ? list : []) {
    const key = resourceType(item);
    if (!groups[key]) groups[key] = [];
    groups[key].push(item);
  }
  return groups;
}

function orderedGroupKeys(groups) {
  const keys = Object.keys(groups || {});
  const preferred = RESOURCE_ORDER.filter((key) => keys.includes(key));
  return preferred.concat(keys.filter((key) => !RESOURCE_ORDER.includes(key)));
}

// 分组卡片按 DRIVE_ORDER 排序(与盘搜分组.js sortGroupResultsByDriveOrder 一致)
function sortGroupKeysByDriveOrder(keys, groups) {
  if (!Array.isArray(keys) || keys.length <= 1 || DRIVE_ORDER.length === 0) return keys;
  const orderMap = new Map(DRIVE_ORDER.map((name, index) => [name, index]));
  return [...keys].sort((a, b) => {
    const aType = inferDriveTypeFromSourceName(resourceName(a, (groups[a] || [{}])[0]));
    const bType = inferDriveTypeFromSourceName(resourceName(b, (groups[b] || [{}])[0]));
    const aOrder = orderMap.has(aType) ? orderMap.get(aType) : Number.MAX_SAFE_INTEGER;
    const bOrder = orderMap.has(bType) ? orderMap.get(bType) : Number.MAX_SAFE_INTEGER;
    if (aOrder !== bOrder) return aOrder - bOrder;
    return 0;
  });
}

// 网盘分组卡片(每个网盘一组,字段与盘搜分组.js formatDriveSearchResultsGrouped 一致)
function buildDriveGroupCards(groups, videoId, vodPic) {
  const keys = sortGroupKeysByDriveOrder(orderedGroupKeys(groups), groups);
  const cards = [];
  for (const key of keys) {
    const items = groups[key] || [];
    if (!items.length) continue;
    cards.push({
      vod_id: encodeId("group", { id: String(videoId || ""), group: key, pic: vodPic || "" }),
      vod_name: resourceName(key, items[0]),
      vod_pic: PAN_PICS[key] || "",
      type_id: "pan_category",
      type_name: "网盘分类",
      vod_remarks: `${items.length}条结果`,
      vod_tag: "folder",
      panType: key,
    });
  }
  return cards;
}

function remarks(x) {
  const out = [];
  for (const key of ["movie_type_display", "release_year", "year", "category_name", "region"]) {
    if (!x || x[key] === undefined || x[key] === null || String(x[key]) === "") continue;
    const value = String(x[key]);
    if (!out.includes(value)) out.push(value);
  }
  if (x && x.resource_count !== undefined && x.resource_count !== null) out.push(`${x.resource_count}源`);
  return out.slice(0, 4).join(" / ");
}

function toVod(x) {
  if (!x || typeof x !== "object") return null;
  const pic = x.cover || x.cover_url || "";
  const vod = {
    vod_id: encodeId("movie", { id: x.id, pic }),
    vod_name: x.title || "资源",
    vod_pic: pic,
    vod_remarks: remarks(x),
    vod_content: x.description || "",
  };
  // 多源影片标记为目录:点击走 category 返回网盘分组/链接列表(OK影视对 detail 多条目不渲染)
  if (Number(x.resource_count) > 1) {
    vod.type_id = vod.vod_id;
    vod.vod_tag = "folder";
  }
  return vod;
}

function filterValues(list, nameKey, valueKey) {
  const out = [];
  const seen = new Set();
  for (const item of Array.isArray(list) ? list : []) {
    if (!item || typeof item !== "object") continue;
    const name = String(
      item[nameKey] || item.display_name || item.label || item.resource_type_display || item[valueKey] || ""
    ).trim();
    const value = String(item[valueKey] || item.slug || item.key || item.resource_type || name).trim();
    if (name && value && !seen.has(value)) {
      seen.add(value);
      out.push({ name, value });
    }
  }
  return out;
}

function buildFilters(data) {
  const source = data && typeof data === "object" ? data : {};
  const years = [{ name: "全部", value: "" }];
  const currentYear = new Date().getFullYear();
  for (let year = currentYear + 2; year >= 1990; year -= 1) years.push({ name: String(year), value: String(year) });

  const types = [
    { name: "全部", value: "" },
    { name: "电影", value: "movie" },
    { name: "电视剧", value: "tv" },
    { name: "动漫", value: "anime" },
    { name: "纪录片", value: "documentary" },
    { name: "其他", value: "other" },
  ];
  const regions = [{ name: "全部", value: "" }].concat(filterValues(source.region_stats, "name", "key")).slice(0, 81);
  const tags = [{ name: "全部", value: "" }].concat(filterValues(source.tags, "name", "slug")).slice(0, 121);
  const categories = [{ name: "全部", value: "" }].concat(filterValues(source.categories, "name", "slug")).slice(0, 121);
  let disks = filterValues(source.resource_type_stats, "name", "key");
  if (!disks.length) {
    disks = [
      { name: "百度网盘", value: "baidu" },
      { name: "115网盘", value: "115" },
      { name: "123云盘", value: "123" },
      { name: "迅雷云盘", value: "xunlei" },
      { name: "阿里云盘", value: "aliyun" },
      { name: "磁力", value: "MagnetLink" },
    ];
  }
  const diskValues = [{ name: "全部", value: "" }].concat(disks).slice(0, 81);
  const sort = [
    { name: "最新", value: "-created_at" },
    { name: "最多资源", value: "-resource_count" },
    { name: "年份新", value: "-release_year" },
    { name: "热度", value: "-views" },
  ];

  const groups = [
    { key: "type", name: "类型", init: "", value: types },
    { key: "region", name: "国家", init: "", value: regions },
    { key: "year", name: "年份", init: "", value: years },
    { key: "tag", name: "标签", init: "", value: tags },
    { key: "category", name: "分类", init: "", value: categories },
    { key: "resource_type", name: "网盘", init: "", value: diskValues },
    { key: "ordering", name: "排序", init: "", value: sort },
  ];

  const filters = {};
  for (const typeId of ["all", "movie", "tv", "anime", "documentary", "other"]) {
    filters[typeId] = groups;
  }
  return filters;
}

// ==================== 线路选择(与参考脚本一致) ====================
function inferDriveTypeFromSourceName(name = "") {
  const raw = String(name || "").toLowerCase();
  if (raw.includes("百度")) return "baidu";
  if (raw.includes("天翼")) return "tianyi";
  if (raw.includes("夸克")) return "quark";
  if (raw === "uc" || raw.includes("uc")) return "uc";
  if (raw.includes("115")) return "115";
  if (raw.includes("迅雷")) return "xunlei";
  if (raw.includes("阿里")) return "ali";
  if (raw.includes("123")) return "123pan";
  if (raw.includes("光鸭") || raw.includes("光雅")) return "guangya";
  return raw;
}

function sortPlaySourcesByDriveOrder(playSources = []) {
  if (!Array.isArray(playSources) || playSources.length <= 1 || DRIVE_ORDER.length === 0) return playSources;
  const orderMap = new Map(DRIVE_ORDER.map((name, index) => [name, index]));
  return [...playSources].sort((a, b) => {
    const aType = inferDriveTypeFromSourceName((a && a.name) || "");
    const bType = inferDriveTypeFromSourceName((b && b.name) || "");
    const aOrder = orderMap.has(aType) ? orderMap.get(aType) : Number.MAX_SAFE_INTEGER;
    const bOrder = orderMap.has(bType) ? orderMap.get(bType) : Number.MAX_SAFE_INTEGER;
    if (aOrder !== bOrder) return aOrder - bOrder;
    return 0;
  });
}

function resolveCallerSource(params = {}, context = {}) {
  return String((context && context.from) || (params && params.source) || "").toLowerCase();
}

function getBaseURLHost(context = {}) {
  const baseURL = String((context && context.baseURL) || "").trim();
  if (!baseURL) return "";
  try {
    return new URL(baseURL).hostname.toLowerCase();
  } catch (error) {
    return baseURL.toLowerCase();
  }
}

function isPrivateHost(hostname = "") {
  const host = String(hostname || "").toLowerCase();
  if (!host) return false;
  if (host === "localhost" || host === "127.0.0.1" || host === "::1" || host === "0.0.0.0") return true;
  if (/^(10\.|192\.168\.|169\.254\.)/.test(host)) return true;
  if (/^172\.(1[6-9]|2\d|3[0-1])\./.test(host)) return true;
  if (host.endsWith(".local") || host.endsWith(".lan") || host.endsWith(".internal") || host.endsWith(".intra")) return true;
  if (host.includes(":")) return host.startsWith("fc") || host.startsWith("fd");
  return false;
}

function canUseServerProxy(context = {}) {
  if (EXTERNAL_SERVER_PROXY_ENABLED) return true;
  return isPrivateHost(getBaseURLHost(context));
}

function filterSourceNamesForCaller(sourceNames = [], callerSource = "", context = {}) {
  let filtered = Array.isArray(sourceNames) ? [...sourceNames] : [];
  const allowServerProxy = canUseServerProxy(context);

  if (callerSource === "web") {
    filtered = filtered.filter((name) => name !== "本地代理");
  } else if (callerSource === "emby") {
    filtered = allowServerProxy
      ? filtered.filter((name) => name === "服务端代理")
      : filtered.filter((name) => name !== "服务端代理");
  } else if (callerSource === "uz") {
    filtered = filtered.filter((name) => name !== "本地代理");
  }

  if (!allowServerProxy) {
    filtered = filtered.filter((name) => name !== "服务端代理");
  }

  return filtered.length > 0 ? filtered : ["直连"];
}

function resolveRouteType(flag = "", callerSource = "", context = {}) {
  const allowServerProxy = canUseServerProxy(context);
  const validRouteTypes = new Set(["本地代理", "服务端代理", "直连"]);
  let routeType = "直连";

  if (callerSource === "web" || callerSource === "emby") {
    routeType = allowServerProxy ? "服务端代理" : "直连";
  }

  if (flag) {
    if (flag.includes("-")) {
      const parts = flag.split("-");
      routeType = parts[parts.length - 1];
    } else {
      routeType = flag;
    }
  }

  if (!validRouteTypes.has(routeType)) routeType = "直连";
  if (!allowServerProxy && routeType === "服务端代理") routeType = "直连";
  if (callerSource === "uz" && routeType === "本地代理") routeType = "直连";
  return routeType;
}

// ==================== 刮削元数据 ====================
function logScrapeResult(videoId, payload) {
  const data = payload && payload.scrapeData;
  const mappings = payload && Array.isArray(payload.videoMappings) ? payload.videoMappings.length : 0;
  const cast = data && data.credits && Array.isArray(data.credits.cast) ? data.credits.cast.length : 0;
  OmniBox.log(
    "info",
    `聚影 刮削结果: ${videoId} 标题=${data ? data.title || "-" : "无"} 映射=${mappings} 主演=${cast}人 类型=${(payload && payload.scrapeType) || "-"}`
  );
}

async function scrapeMetadataCached(videoId, vodName, mergedFiles) {
  const cacheKey = `jy:meta:${videoId}`;
  const canScrape = SCRAPING_ENABLED && Array.isArray(mergedFiles) && mergedFiles.length > 0;
  const cached = await cacheGet(cacheKey);
  const cachedPayload = cached && typeof cached === "object" ? cached : null;
  if (cachedPayload && cachedPayload.scrapeData) return cachedPayload;
  if (!canScrape) return cachedPayload || { scrapeData: null, videoMappings: [], scrapeType: "" };

  // 缓存里是空结果(上次刮削失败/超时)时,5分钟内只再同步试一次,避免每次都白跑
  if (cachedPayload) {
    const retryLock = await cacheGet(`jy:metaRetry:${videoId}`);
    if (retryLock) return cachedPayload;
    await cacheSet(`jy:metaRetry:${videoId}`, { t: Date.now() }, 300);
  }

  try {
    OmniBox.log("info", `聚影 开始刮削: ${videoId}, 文件数=${mergedFiles.length}`);
    await OmniBox.processScraping(videoId, vodName, vodName, mergedFiles);
    const metadata = await OmniBox.getScrapeMetadata(videoId);
    const payload = {
      scrapeData: (metadata && metadata.scrapeData) || null,
      videoMappings: (metadata && metadata.videoMappings) || [],
      scrapeType: (metadata && metadata.scrapeType) || "",
    };
    await cacheSet(cacheKey, payload);
    logScrapeResult(videoId, payload);
    if (!payload.scrapeData) {
      OmniBox.log("warn", `聚影 刮削未返回元数据: ${videoId}(稍后自动重试)`);
    }
    return payload;
  } catch (error) {
    OmniBox.log("warn", `聚影 刮削失败: ${error.message}`);
    if (cachedPayload) return cachedPayload;
    return { scrapeData: null, videoMappings: [], scrapeType: "" };
  }
}

function scrapedEpisodeName(scrapeData, mapping, fallback) {
  if (!scrapeData || !Array.isArray(scrapeData.episodes) || !mapping) return fallback;
  if (mapping.confidence !== undefined && mapping.confidence !== null && mapping.confidence < 0.5) return fallback;
  if (!mapping.episodeNumber) return fallback;
  for (const episode of scrapeData.episodes) {
    if (
      episode &&
      episode.episodeNumber === mapping.episodeNumber &&
      episode.seasonNumber === mapping.seasonNumber &&
      episode.name
    ) {
      return `${mapping.episodeNumber}.${episode.name}`;
    }
  }
  return fallback;
}

// 站点元数据是否为电影:电影不套用剧集集数映射(避免出现 1.xxx 集数与 S01E01 弹幕名)
function looksLikeMovieMeta(meta) {
  if (!meta || typeof meta !== "object") return false;
  const text = `${meta.movie_type_display || ""} ${meta.category_name || ""} ${meta.movie_type || ""} ${meta.type_name || ""}`.trim();
  if (!text) return false;
  if (!/电影|影片|movie|film/i.test(text)) return false;
  if (/电视剧|剧集|动漫|动画|综艺|纪录片|少儿|系列|连载/i.test(text)) return false;
  return true;
}

function applyScrapeToSources(sources, metadata, hints) {
  const scrapeType = String((metadata && metadata.scrapeType) || "").toLowerCase();
  if ((hints && hints.isMovie) || scrapeType === "movie") return;
  const scrapeData = metadata && metadata.scrapeData;
  const mappings = metadata && Array.isArray(metadata.videoMappings) ? metadata.videoMappings : [];
  if (!scrapeData || !mappings.length) return;
  const mappingMap = new Map();
  for (const mapping of mappings) {
    if (mapping && mapping.fileId) mappingMap.set(String(mapping.fileId), mapping);
  }

  for (const source of sources) {
    const episodes = (source && source.episodes) || [];
    let changed = false;
    for (const episode of episodes) {
      if (!episode._shareURL || !episode._fileId || !episode._videoId) continue;
      const mapping = mappingMap.get(`${episode._shareURL}|${episode._fileId}|${episode._videoId}`);
      if (!mapping) continue;
      const nextName = scrapedEpisodeName(scrapeData, mapping, episode.name);
      if (nextName && nextName !== episode.name) {
        episode.name = escapePlayName(nextName);
        changed = true;
      }
      if (mapping.seasonNumber !== undefined && mapping.seasonNumber !== null) {
        episode._seasonNumber = mapping.seasonNumber;
      }
      if (mapping.episodeNumber !== undefined && mapping.episodeNumber !== null) {
        episode._episodeNumber = mapping.episodeNumber;
        changed = true;
      }
    }
    const hasNumber = episodes.some((episode) => episode._episodeNumber !== undefined);
    if (hasNumber) {
      episodes.sort((a, b) => {
        const seasonA = a._seasonNumber || 0;
        const seasonB = b._seasonNumber || 0;
        if (seasonA !== seasonB) return seasonA - seasonB;
        const epA = a._episodeNumber || 0;
        const epB = b._episodeNumber || 0;
        if (epA !== epB) return epA - epB;
        return String(a.name || "").localeCompare(String(b.name || ""), "zh-CN");
      });
      changed = true;
    }
    if (changed) source.episodes = episodes;
  }
}

// 刮削结果补全影片信息(主演/导演/简介/年份),只在站点数据缺失时补齐,与盘搜分组.js applyScrapeInfoToVod 一致
function applyScrapeInfoToVod(vod, scrapeData) {
  if (!vod || !scrapeData || typeof scrapeData !== "object") return vod;
  const credits = scrapeData.credits || {};
  const missing = (value) => !String(value || "").trim();
  const uniq = (list) => list.filter((name, index) => name && list.indexOf(name) === index);
  if (missing(vod.vod_actor) && Array.isArray(credits.cast) && credits.cast.length) {
    vod.vod_actor = uniq(
      credits.cast.slice(0, 12).map((cast) => (cast && (cast.name || cast.character)) || "")
    )
      .slice(0, 8)
      .join("、");
  }
  if (missing(vod.vod_director) && Array.isArray(credits.crew) && credits.crew.length) {
    const directors = credits.crew.filter(
      (crew) => crew && (crew.job === "Director" || crew.department === "Directing" || crew.known_for_department === "Directing")
    );
    vod.vod_director = uniq(directors.slice(0, 6).map((crew) => crew.name || ""))
      .slice(0, 3)
      .join("、");
  }
  if (missing(vod.vod_content) && scrapeData.overview) vod.vod_content = String(scrapeData.overview);
  if (missing(vod.vod_year) && scrapeData.releaseDate) vod.vod_year = String(scrapeData.releaseDate).slice(0, 4);
  if (missing(vod.vod_pic) && scrapeData.posterPath) {
    vod.vod_pic = `https://image.tmdb.org/t/p/w500${scrapeData.posterPath}`;
  }
  if (missing(vod.vod_area) && Array.isArray(scrapeData.originCountry) && scrapeData.originCountry.length) {
    vod.vod_area = String(scrapeData.originCountry[0]);
  }
  return vod;
}

// 站点/刮削都没给出主演导演时,用 TMDB 接口补全(需在配置区填 TMDB_API_KEY)
const TMDB_HOST = "api.themoviedb.org";

function tmdbProxyUrl() {
  return String(
    process.env.TMDB_PROXY ||
      process.env.HTTPS_PROXY ||
      process.env.https_proxy ||
      process.env.HTTP_PROXY ||
      process.env.http_proxy ||
      ""
  ).trim();
}

// 按 chunked 编码解析响应体
function tmdbParseChunks(buf) {
  let out = Buffer.alloc(0);
  let i = 0;
  while (i < buf.length) {
    const lineEnd = buf.indexOf("\r\n", i);
    if (lineEnd < 0) break;
    const size = parseInt(buf.slice(i, lineEnd).toString("ascii").split(";")[0], 16);
    if (!Number.isFinite(size) || size <= 0) break;
    out = Buffer.concat([out, buf.slice(lineEnd + 2, lineEnd + 2 + size)]);
    i = lineEnd + 2 + size + 2;
  }
  return out;
}

// TMDB 走原生 socket:配置/环境里有代理时先 CONNECT 隧道,避免 axios 走不了代理导致超时
function tmdbConnect(proxy) {
  return new Promise((resolve, reject) => {
    if (proxy) {
      const parsed = new URL(proxy);
      const req = http.request({
        host: parsed.hostname,
        port: Number(parsed.port) || 80,
        method: "CONNECT",
        path: `${TMDB_HOST}:443`,
        timeout: 8000,
      });
      req.on("connect", (res, socket) => {
        if (res.statusCode === 200) resolve(socket);
        else reject(new Error(`代理CONNECT失败(${res.statusCode})`));
      });
      req.on("timeout", () => {
        req.destroy();
        reject(new Error("代理连接超时"));
      });
      req.on("error", reject);
      req.end();
    } else {
      const socket = net.connect({ host: TMDB_HOST, port: 443, timeout: 8000 });
      socket.once("connect", () => resolve(socket));
      socket.on("timeout", () => {
        socket.destroy();
        reject(new Error("TMDB 直连超时"));
      });
      socket.on("error", reject);
    }
  });
}

function tmdbRequest(path) {
  const proxy = tmdbProxyUrl();
  return new Promise(async (resolve, reject) => {
    let settled = false;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error);
      else resolve(value);
    };
    const timer = setTimeout(() => finish(new Error("TMDB 请求超时")), 12000);
    try {
      const tunnel = await tmdbConnect(proxy);
      const socket = tls.connect({ socket: tunnel, servername: TMDB_HOST });
      socket.on("error", (error) => finish(error));
      socket.on("secureConnect", () => {
        socket.write(
          `GET ${path} HTTP/1.1\r\nHost: ${TMDB_HOST}\r\nAccept: application/json\r\nConnection: close\r\n\r\n`
        );
      });
      const chunks = [];
      socket.on("data", (data) => chunks.push(data));
      socket.on("end", () => {
        const raw = Buffer.concat(chunks);
        const split = raw.indexOf("\r\n\r\n");
        if (split < 0) return finish(new Error("TMDB 响应格式异常"));
        const head = raw.slice(0, split).toString("utf8");
        const status = Number((head.split("\r\n")[0] || "").split(" ")[1]) || 0;
        const headers = head
          .split("\r\n")
          .slice(1)
          .reduce((acc, line) => {
            const index = line.indexOf(":");
            if (index > 0) acc[line.slice(0, index).trim().toLowerCase()] = line.slice(index + 1).trim();
            return acc;
          }, {});
        let body = raw.slice(split + 4);
        if (String(headers["transfer-encoding"] || "").toLowerCase().includes("chunked")) {
          body = tmdbParseChunks(body);
        }
        finish(null, { status, body: body.toString("utf8") });
      });
    } catch (error) {
      finish(error);
    }
  });
}

async function tmdbJson(path, params, language) {
  const key = String(process.env.TMDB_API_KEY || "").trim();
  if (!key) return null;
  const query = new URLSearchParams({ api_key: key, language: language || "zh-CN" });
  for (const [name, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== "") query.set(name, String(value));
  }
  const response = await tmdbRequest(`/3${path}${path.includes("?") ? "&" : "?"}${query.toString()}`);
  if (!response || response.status !== 200) {
    throw new Error(`TMDB HTTP ${response ? response.status : "?"}`);
  }
  try {
    const data = JSON.parse(response.body);
    return data && typeof data === "object" ? data : null;
  } catch (error) {
    throw new Error("TMDB 响应解析失败");
  }
}

// 标题相似度:完全一致 > 包含关系 > 公共前缀,避免搜到"XX之番外"这类同名衍生作
function titleMatchScore(query, candidate) {
  const norm = (value) => String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "");
  const q = norm(query);
  const t = norm(candidate);
  if (!q || !t) return 0;
  if (t === q) return 100;
  if (t.startsWith(q) || q.startsWith(t)) return 80;
  if (t.includes(q) || q.includes(t)) return 60;
  let i = 0;
  while (i < q.length && i < t.length && q[i] === t[i]) i++;
  return i >= 4 && i / Math.max(q.length, t.length) >= 0.5 ? 45 : 0;
}

// 先按站点类型搜,搜不到再换另一类;带年份搜不到时去掉年份重试(站点年份常与 TMDB 不一致),
// 各次结果统一按"标题相似度 + 类型偏好 + 年份命中"打分取最高,避免误匹配
async function searchTmdb(name, isTv, year, deadline) {
  const preferred = isTv ? "tv" : "movie";
  const other = isTv ? "movie" : "tv";
  const plan = [
    { type: preferred, withYear: true },
    { type: preferred, withYear: false },
    { type: other, withYear: true },
    { type: other, withYear: false },
  ];
  let best = null;
  let bestScore = 0;
  for (const step of plan) {
    if (Date.now() > deadline) break;
    const params = { query: name };
    if (step.withYear && year) {
      if (step.type === "movie") params.year = year;
      else params.first_air_date_year = year;
    }
    let results = [];
    try {
      const hit = await tmdbJson(`/search/${step.type}`, params);
      results = hit && Array.isArray(hit.results) ? hit.results : [];
    } catch (error) {
      if (bestScore >= 45) break;
      throw error;
    }
    for (const item of results.slice(0, 5)) {
      const title = (item && (item.title || item.name)) || "";
      let score = titleMatchScore(name, title);
      if (!score) continue;
      if (step.type === preferred) score += 10;
      if (step.withYear && year) score += 3;
      if (score > bestScore) {
        bestScore = score;
        best = { type: step.type, id: item.id, title };
      }
    }
    if (bestScore >= 110) break;
  }
  if (!best || bestScore < 45) return null;
  return { ...best, score: bestScore };
}

async function fillMissingMetaFromTmdb(vod) {
  if (!vod || !String(process.env.TMDB_API_KEY || "").trim()) return;
  const missing = (value) => !String(value || "").trim();
  if (!missing(vod.vod_actor) && !missing(vod.vod_director) && !missing(vod.vod_content)) return;
  const name = String(vod.vod_name || "").trim();
  if (!name) return;
  const typeName = `${vod.type_name || ""} ${vod.vod_remarks || ""}`;
  const isTv = /电视剧|剧集|动漫|综艺|纪录片|动画|TV|Series/i.test(typeName);
  const cacheKey = `jy:tmdb:${name}:${vod.vod_year || ""}`;
  const deadline = Date.now() + 12000;
  try {
    const cached = await cacheGet(cacheKey);
    if (cached && typeof cached === "object" && cached.credits) {
      applyTmdbToVod(vod, cached, true);
      return;
    }
    const hit = await searchTmdb(name, isTv, vod.vod_year, deadline);
    if (!hit) {
      OmniBox.log("info", `聚影 TMDB 未匹配: ${name}`);
      return;
    }
    let detail = await tmdbJson(`/${hit.type}/${hit.id}`, { append_to_response: "credits" });
    if (!detail) return;
    if (!String(detail.overview || "").trim() && Date.now() <= deadline) {
      const en = await tmdbJson(`/${hit.type}/${hit.id}`, { append_to_response: "credits" }, "en-US");
      if (en) detail = en;
    }
    const payload = {
      overview: detail.overview || "",
      releaseDate: detail.release_date || detail.first_air_date || "",
      posterPath: detail.poster_path || "",
      originCountry: Array.isArray(detail.origin_country) ? detail.origin_country : detail.production_countries,
      credits: detail.credits || {},
    };
    applyTmdbToVod(vod, payload, false);
    if (hit.score >= 90) await cacheSet(cacheKey, payload, 86400);
    const castCount = Array.isArray(payload.credits.cast) ? payload.credits.cast.length : 0;
    OmniBox.log(
      "info",
      `聚影 TMDB 补全: ${name} -> ${hit.title}[${hit.type}] (匹配分${hit.score}, 主演${castCount}人, 导演${vod.vod_director || "-"})`
    );
  } catch (error) {
    OmniBox.log("warn", `聚影 TMDB 补全失败: ${error.message}${tmdbProxyUrl() ? "" : "(可配 TMDB_PROXY 走代理)"}`);
  }
}

function applyTmdbToVod(vod, payload, silent) {
  try {
    applyScrapeInfoToVod(vod, payload);
  } catch (error) {
    if (!silent) OmniBox.log("warn", `聚影 TMDB 字段补全失败: ${error.message}`);
  }
  return vod;
}

// ==================== 详情:构建播放线路 ====================
function failureHintText(message) {
  const msg = String(message || "").trim();
  if (!msg) return "链接不可用";
  if (/已被取消|已取消|invalid share/i.test(msg)) return "分享已被取消";
  if (/不存在|已删除|404|not found|此分享/i.test(msg)) return "分享不存在或已删除";
  if (/密码|password|提取码|无权|权限|private/i.test(msg)) return "需要提取码或无权限";
  if (/无法识别|不支持/i.test(msg)) return "分享链接无法识别";
  if (/401|403|鉴权|unauthorized|forbidden/i.test(msg)) return "登录鉴权失效,稍后重试";
  if (/限流|429|冷却|稍后/i.test(msg)) return "站点限流,稍后再试";
  if (/超时|timeout|network|fetch failed/i.test(msg)) return "网络异常,稍后再试";
  return msg.length > 60 ? `${msg.slice(0, 60)}…` : msg;
}

function withFallbackSource(playSources) {
  if (Array.isArray(playSources) && playSources.length > 0) return playSources;
  // 资源列表/链接解析任一环节处于限流冷却都会导致无线路,提示要如实区分限流与真没资源
  const limited = [
    "/api/app/movie/0/resources/",
    "/api/app/resource/0/access/",
    "/api/app/movies/",
    "/api/app/movie/0/detail/",
  ].some((path) => rateLimitRemaining(path) > 0);
  const hint = limited ? "站点限流,请稍后再试" : "暂无资源";
  return [{ name: "提示", episodes: [{ name: hint, playId: encodePlayMeta({ k: "empty" }) }] }];
}

// 分组内资源全部解析失败(常见:持久缓存里的 access_ticket 过期导致 403)时的提示
function resolveFailHintText() {
  const limited = ["/api/app/resource/0/access/", "/api/app/movie/0/resources/"].some(
    (path) => rateLimitRemaining(path) > 0
  );
  return limited ? "站点限流,请稍后再试" : "链接解析失败,稍后重试";
}

// 清掉某影片的持久资源缓存,让下次 resourceListApi 拉取带新票据的列表
async function invalidateResourceCache(mid) {
  if (!mid) return;
  memCache.delete(`res|${mid}`);
  try {
    await cacheSet(`jy:res:${mid}`, "", 1);
  } catch (error) {
    /* 忽略缓存清理失败 */
  }
}

async function buildPlaySources(groups, callerSource, context, videoId, vodName, out, hints) {
  const sources = [];
  const mergedFiles = [];
  const isMovie = !!(hints && hints.isMovie);

  for (const key of orderedGroupKeys(groups)) {
    const items = groups[key] || [];
    if (!items.length) continue;
    const driveName = resourceName(key, items[0]);

    // 1. 分流:磁力/电驴延迟到播放时解析,其余需要提前拿到真实链接
    const lazyItems = [];
    const eagerItems = [];
    for (const item of items) {
      if (isLazyResourceType(item)) lazyItems.push(item);
      else if (eagerItems.length < MAX_ACCESS_PER_GROUP) eagerItems.push(item);
    }

    // 2. 解析其余资源的真实链接
    const resolved = await mapWithConcurrency(eagerItems, 4, async (item) => {
      try {
        const url = normalizePlayUrl(await accessResource(item));
        return { item, url };
      } catch (error) {
        OmniBox.log("warn", `聚影 解析资源链接失败: ${error.message}`);
        return { item, url: "" };
      }
    });
    const valid = resolved.filter((entry) => entry.url);

    // 2.1 分组内可急解资源全部失败(票据过期/鉴权403):先给一条可见提示并标记,由 detail 刷新资源列表自愈一次
    if (eagerItems.length && !valid.length && !lazyItems.length) {
      if (out) out.resolveFailed = true;
      OmniBox.log("warn", `聚影 资源链接解析失败(${eagerItems.length}条): ${driveName}`);
      sources.push({
        name: driveName,
        episodes: [{ name: escapePlayName(resolveFailHintText()), playId: encodePlayMeta({ k: "empty" }) }],
      });
    }

    // 3. 拆分直链与网盘
    const directItems = [];
    const panItems = [];
    for (const entry of valid) {
      if (classifyPlayUrl(entry.url, entry.item) === "pan") panItems.push(entry);
      else directItems.push(entry);
    }

    // 4. 直链(含磁力/电驴/在线视频)
    if (directItems.length || lazyItems.length) {
      const episodes = directItems.slice(0, MAX_EPISODES).map((entry) => ({
        name: escapePlayName(entry.item.title || entry.item.resource_description || basenameOf(entry.url) || driveName),
        playId: encodePlayMeta({ k: "direct", u: entry.url, v: videoId || "" }),
      }));
      const remain = Math.max(0, MAX_EPISODES - episodes.length);
      for (const item of lazyItems.slice(0, remain)) {
        episodes.push({
          name: escapePlayName(item.title || item.resource_description || resourceName(key, item)),
          playId: encodePlayMeta({ k: "lazy", r: compactResource(item), v: videoId || "" }),
        });
      }
      if (episodes.length) sources.push({ name: driveName, episodes });
    }

    // 4.1 磁力 115 秒传:离线到 115 网盘后按文件生成分集,放在磁力线路前面;失败时保持磁力线路
    const magnet115Source = await build115MagnetSource(lazyItems, videoId);
    if (magnet115Source) {
      const index = sources.findIndex((item) => item && item.name === driveName);
      if (index >= 0) sources.splice(index, 0, magnet115Source);
      else sources.push(magnet115Source);
    }

    // 5. 网盘分享:枚举文件后按文件生成选集
    if (panItems.length) {
      const limited = panItems.slice(0, MAX_PAN_SHARES);
      const results = await mapWithConcurrency(limited, 3, async (entry) => {
        let driveInfo = {};
        let files = [];
        let failure = "";
        try {
          driveInfo = (await driveInfoCached(entry.url)) || {};
        } catch (error) {
          failure = error.message;
          OmniBox.log("warn", `聚影 获取网盘信息失败: ${entry.url}, ${error.message}`);
        }
        try {
          files = (await videoFilesCached(entry.url)) || [];
        } catch (error) {
          if (!failure) failure = error.message;
          OmniBox.log("warn", `聚影 枚举网盘文件失败: ${entry.url}, ${error.message}`);
        }
        return { ...entry, driveInfo, files, failure };
      });

      const firstInfo = results.map((entry) => entry.driveInfo).find((info) => info && info.driveType) || {};
      const driveType = String(firstInfo.driveType || key || "").toLowerCase();
      const multiRoute = DRIVE_TYPE_CONFIG.includes(driveType);

      const episodes = [];
      let failureCount = 0;
      for (const entry of results) {
        if (entry.files.length) {
          for (const file of entry.files) {
            const fileId = String(file.fid || file.file_id || "");
            const fileName = String(file.file_name || file.name || "");
            if (!fileId || !fileName) continue;
            const size = Number(file.size || file.file_size || 0);
            const label = size > 0 ? `[${formatFileSize(size)}] ${fileName}` : fileName;
            episodes.push({
              name: escapePlayName(label),
              playId: encodePlayMeta({
                k: "pan",
                u: entry.url,
                f: fileId,
                v: videoId || "",
                e: fileName,
                m: isMovie ? 1 : 0,
              }),
              size: size > 0 ? size : undefined,
              rawName: fileName,
              episodeName: fileName,
              _shareURL: entry.url,
              _fileId: fileId,
              _videoId: videoId || "",
            });
            if (videoId && SCRAPING_ENABLED) {
              const mergedId = `${entry.url}|${fileId}|${videoId}`;
              mergedFiles.push({ ...file, fid: mergedId, file_id: mergedId });
            }
          }
        } else if (entry.failure) {
          failureCount += 1;
          if (failureCount <= MAX_FAILURE_HINTS) {
            episodes.push({
              name: escapePlayName(`链接已失效: ${failureHintText(entry.failure)}`),
              playId: encodePlayMeta({ k: "empty" }),
            });
          }
        } else {
          episodes.push({
            name: escapePlayName(entry.item.title || entry.item.resource_description || `${driveName}(未找到视频文件)`),
            playId: encodePlayMeta({ k: "pan", u: entry.url, v: videoId || "" }),
          });
        }
      }
      if (failureCount > MAX_FAILURE_HINTS) {
        episodes.push({
          name: escapePlayName(`另有${failureCount - MAX_FAILURE_HINTS}条链接已失效`),
          playId: encodePlayMeta({ k: "empty" }),
        });
      }

      if (episodes.length) {
        const capped = episodes.slice(0, MAX_EPISODES);
        const routeNames = multiRoute ? filterSourceNamesForCaller(SOURCE_NAMES_CONFIG, callerSource, context) : [""];
        for (const route of routeNames) {
          sources.push({ name: route ? `${driveName}-${route}` : driveName, episodes: capped });
        }
      }
    }
  }

  // 6. 刮削(用于剧集命名与弹幕)
  if (SCRAPING_ENABLED && videoId && mergedFiles.length) {
    try {
      const metadata = await scrapeMetadataCached(videoId, vodName, mergedFiles.slice(0, 400));
      applyScrapeToSources(sources, metadata, hints);
      if (out) out.metadata = metadata;
    } catch (error) {
      OmniBox.log("warn", `聚影 刮削处理失败: ${error.message}`);
      if (out) out.metadata = null;
    }
  } else if (out) {
    out.metadata = null;
  }

  // 7. 清理内部字段(刮削匹配已完成)
  for (const source of sources) {
    const episodes = (source && source.episodes) || [];
    for (const episode of episodes) {
      if (!episode || typeof episode !== "object") continue;
      delete episode._shareURL;
      delete episode._fileId;
      delete episode._videoId;
    }
  }

  return sortPlaySourcesByDriveOrder(sources);
}

// ==================== 对外接口 ====================
async function home(params, context) {
  try {
    const from = (context && context.from) || "web";
    await OmniBox.log("info", `[home] from=${from}`);
    const [overviewData, initialData] = await Promise.all([overviewApi(), homeInitialApi()]);
    const classes = [
      { type_id: "all", type_name: "影视库" },
      { type_id: "movie", type_name: "电影" },
      { type_id: "tv", type_name: "电视剧" },
      { type_id: "anime", type_name: "动漫" },
      { type_id: "documentary", type_name: "纪录片" },
      { type_id: "other", type_name: "其他" },
    ];

    const rawList = [];
    if (initialData && typeof initialData === "object") {
      for (const key of ["default_movies", "hero_candidates"]) {
        if (Array.isArray(initialData[key])) rawList.push(...initialData[key]);
      }
      const sections = initialData.featured_sections;
      if (sections && typeof sections === "object") {
        for (const key of Object.keys(sections)) {
          if (Array.isArray(sections[key])) rawList.push(...sections[key]);
        }
      }
    }
    const list = dedupe(rawList)
      .slice(0, 24)
      .map(toVod)
      .filter(Boolean);

    return { class: classes, list, filters: buildFilters(overviewData) };
  } catch (error) {
    OmniBox.log("error", `聚影 获取首页失败: ${error.message}`);
    return {
      class: [{ type_id: "all", type_name: "影视库" }],
      list: [],
      filters: {},
    };
  }
}

// 分组二级目录条目:每个链接(资源)一条(与盘搜分组.js formatDriveSearchResultsSpecific 一致)
function toResourceVod(item, groupKey, pic, movieId) {
  const key = resourceType(item);
  return {
    vod_id: encodeId("res", { ...item, _mid: String(movieId || "") }),
    vod_name: clean(item.title || item.resource_description || resourceName(key, item)),
    vod_pic: PAN_PICS[key] || pic || "",
    type_id: String(groupKey || ""),
    type_name: resourceName(key, item),
    vod_remarks: resourceName(key, item),
    vod_content: item.description || item.resource_description || "",
  };
}

async function groupCategoryPage(data, page) {
  const all = (await resourceListApi(data.id)).filter((item) => resourceType(item) === data.group);
  const total = all.length;
  const pagecount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const current = Math.max(1, Math.min(page, pagecount));
  const start = (current - 1) * PAGE_SIZE;
  const slice = all.slice(start, start + PAGE_SIZE);

  const list = slice.map((item) => toResourceVod(item, data.group, data.pic || "", data.id)).filter((item) => item.vod_id);

  return { list, page: current, pagecount, limit: PAGE_SIZE, total };
}

async function movieResourceCategoryPage(data, page) {
  const resources = await resourceListApi(data.id);
  const groups = groupByResourceType(resources);
  const keys = orderedGroupKeys(groups).filter((key) => (groups[key] || []).length > 0);

  // 多网盘:返回一级分组卡片
  if (keys.length > 1) {
    const cards = buildDriveGroupCards(groups, data.id, data.pic || "");
    return { list: cards, page: 1, pagecount: 1, limit: Math.max(1, cards.length), total: cards.length };
  }

  // 单网盘:直接返回二级目录(该网盘下的每个链接)
  const groupKey = keys[0] || "";
  const items = groupKey ? groups[groupKey] : [];
  const total = items.length;
  const pagecount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const current = Math.max(1, Math.min(page, pagecount));
  const start = (current - 1) * PAGE_SIZE;
  const list = items
    .slice(start, start + PAGE_SIZE)
    .map((item) => toResourceVod(item, groupKey, data.pic || "", data.id))
    .filter((item) => item.vod_id);
  return { list, page: current, pagecount, limit: PAGE_SIZE, total };
}

async function category(params, context) {
  const page = toPage(params && params.page);
  try {
    await OmniBox.log(
      "info",
      `[category] categoryId=${(params && (params.categoryId || params.type_id)) || "all"}, page=${page}, from=${(context && context.from) || "web"}`
    );
    let typeId = String((params && (params.categoryId || params.type_id)) || "all");
    const filters =
      params && params.filters && typeof params.filters === "object" && !Array.isArray(params.filters)
        ? params.filters
        : {};

    let [typ, data] = decodeId(typeId);
    // 兜底:调用方可能把影片/分组ID放在 type_id 而不是 categoryId
    if (typ !== "group" && typ !== "movie") {
      const alt = String((params && params.type_id) || "");
      const [altTyp, altData] = decodeId(alt);
      if (altTyp === "group" || altTyp === "movie") {
        typeId = alt;
        typ = altTyp;
        data = altData;
      }
    }
    if (typ === "group") return await groupCategoryPage(data, page);
    if (typ === "movie") return await movieResourceCategoryPage(data, page);

    const query = {
      page,
      page_size: PAGE_SIZE,
      count: 1,
      ordering: String(filters.ordering || filters.sort || "-created_at"),
    };
    const typeValue = filters.type ? String(filters.type) : "";
    const effectiveType = typeId && typeId !== "all" ? typeId : typeValue;
    if (effectiveType && effectiveType !== "all") query.type = effectiveType;
    for (const key of ["category", "region", "tag", "year", "resource_type"]) {
      if (filters[key]) query[key] = filters[key];
    }

    const data2 = await apiCall("/api/app/movies/", { params: query });
    const results = Array.isArray(data2.results) ? data2.results : [];
    const totalPages = parseInt(data2.total_pages, 10);
    const pagecount =
      Number.isFinite(totalPages) && totalPages > 0 ? totalPages : page + (results.length ? 1 : 0);
    const total = parseInt(data2.total_count, 10) || parseInt(data2.count, 10) || results.length;

    return {
      list: results.map(toVod).filter(Boolean),
      page,
      pagecount,
      limit: PAGE_SIZE,
      total,
    };
  } catch (error) {
    OmniBox.log("error", `聚影 获取分类失败: ${error.message}`);
    return { list: [], page, pagecount: 0, limit: PAGE_SIZE, total: 0 };
  }
}

async function search(params, context) {
  const page = toPage(params && params.page);
  try {
    const keyword = String((params && (params.keyword || params.q || params.wd)) || "").trim();
    if (!keyword) return { list: [], page, pagecount: 0, limit: PAGE_SIZE, total: 0 };
    await OmniBox.log("info", `[search] keyword=${keyword}, page=${page}, from=${(context && context.from) || "web"}`);

    const data = await apiCall("/api/app/movies/", {
      params: { q: keyword, page, page_size: PAGE_SIZE, count: 1, exact: 1 },
    });
    const results = Array.isArray(data.results) ? data.results : [];
    const totalPages = parseInt(data.total_pages, 10);
    const pagecount = Number.isFinite(totalPages) && totalPages > 0 ? totalPages : 1;
    const total = parseInt(data.total_count, 10) || parseInt(data.count, 10) || results.length;

    return {
      list: results.map(toVod).filter(Boolean),
      page,
      pagecount,
      limit: PAGE_SIZE,
      total,
    };
  } catch (error) {
    OmniBox.log("error", `聚影 搜索失败: ${error.message}`);
    return { list: [], page, pagecount: 0, limit: PAGE_SIZE, total: 0 };
  }
}

async function detail(params, context) {
  try {
    const rawId = String((params && (params.videoId || params.id || params.vod_id || params.vodId)) || "");
    if (!rawId) throw new Error("视频ID不能为空");

    const [typ, data] = decodeId(rawId);
    const callerSource = resolveCallerSource(params || {}, context || {});

    if (typ === "res") {
      const item = data || {};
      const key = resourceType(item);
      const vodName = clean(item.title || item.resource_description || resourceName(key, item));

      // 链接列表里的资源条目带 _mid:取影片元数据补导演/演员/简介,并按影片ID做刮削
      const resMid = String(item._mid || "");
      let meta = {};
      if (resMid) {
        try {
          const detailData = await movieDetailApi(resMid);
          meta = (detailData && (detailData.data || detailData.movie)) || detailData || {};
        } catch (error) {
          OmniBox.log("warn", `聚影 资源详情取影片信息失败: ${error.message}`);
        }
      }
      const resName = meta.title ? clean(meta.title) : vodName;
      const scrapeOut = {};
      const buildHints = { isMovie: looksLikeMovieMeta(meta) };
      let groups = {};
      groups[key] = [item];
      let playSources = await buildPlaySources(groups, callerSource, context, resMid, resName, scrapeOut, buildHints);
      // 票据过期导致解析全失败:刷新资源列表拿新票据再建一次(每条详情最多一次)
      if (scrapeOut.resolveFailed && resMid) {
        OmniBox.log("info", `聚影 资源链接解析失败,刷新资源列表重试: mid=${resMid}`);
        await invalidateResourceCache(resMid);
        try {
          const fresh = await resourceListApi(resMid);
          const freshItem =
            fresh.find((entry) => entry && String(entry.id) === String(item.id)) ||
            fresh.find((entry) => entry && resourceType(entry) === key);
          if (freshItem) {
            groups = {};
            groups[key] = [freshItem];
            scrapeOut.resolveFailed = false;
            playSources = await buildPlaySources(groups, callerSource, context, resMid, resName, scrapeOut, buildHints);
          }
        } catch (error) {
          OmniBox.log("warn", `聚影 刷新资源列表失败: ${error.message}`);
        }
      }
      const vod = {
        vod_id: rawId,
        vod_name: resName,
        vod_pic: meta.cover || meta.cover_url || PAN_PICS[key] || item.pic || "",
        vod_year: String(meta.release_year || meta.year || ""),
        vod_area: meta.region || "",
        vod_actor: joinNames(meta.actors),
        vod_director: joinNames(meta.director),
        vod_content: meta.description || item.description || item.resource_description || "",
        vod_remarks: resourceName(key, item),
        type_name: resourceName(key, item),
        vod_play_sources: withFallbackSource(playSources),
      };
      applyScrapeInfoToVod(vod, scrapeOut.metadata && scrapeOut.metadata.scrapeData);
      await fillMissingMetaFromTmdb(vod);
      return { list: [vod] };
    }

    const isGroup = typ === "group" && !!data.group;
    const mid = typ === "movie" || isGroup ? String(data.id || rawId) : rawId;

    const detailData = await movieDetailApi(mid);
    const meta = (detailData && (detailData.data || detailData.movie)) || detailData || {};
    const vodName = meta.title || "资源";
    const vodPic = meta.cover || meta.cover_url || "";

    let groups = groupByResourceType(await resourceListApi(mid));

    // detail 始终只返回一条可播放影片(OK影视对多条目 detail 不渲染,分组/链接列表走 category)
    const pickTarget = (map) =>
      isGroup && Array.isArray(map[data.group]) && map[data.group].length ? { [data.group]: map[data.group] } : map;
    const scrapeOut = {};
    const buildHints = { isMovie: looksLikeMovieMeta(meta) };
    let targetGroups = pickTarget(groups);
    let playSources = await buildPlaySources(targetGroups, callerSource, context, mid, vodName, scrapeOut, buildHints);
    // 票据过期导致解析全失败(常见403):清掉持久资源缓存拿新票据,重建一次
    if (scrapeOut.resolveFailed) {
      OmniBox.log("info", `聚影 资源链接解析失败,刷新资源列表重试: mid=${mid}`);
      await invalidateResourceCache(mid);
      groups = groupByResourceType(await resourceListApi(mid));
      targetGroups = pickTarget(groups);
      scrapeOut.resolveFailed = false;
      playSources = await buildPlaySources(targetGroups, callerSource, context, mid, vodName, scrapeOut, buildHints);
    }
    const sourceSummary = playSources.map((item) => `${item.name}:${(item.episodes || []).length}`).join(",") || "无线路";
    if (isGroup) {
      OmniBox.log("info", `聚影 分组详情: ${resourceName(data.group, null)} -> ${sourceSummary}`);
    } else {
      OmniBox.log("info", `聚影 线路: ${sourceSummary}`);
    }

    const vod = {
      vod_id: isGroup ? rawId : String(mid),
      vod_name: vodName,
      vod_pic: vodPic,
      vod_year: String(meta.release_year || meta.year || ""),
      vod_area: meta.region || "",
      vod_actor: joinNames(meta.actors),
      vod_director: joinNames(meta.director),
      vod_content: meta.description || "",
      vod_remarks: remarks(meta),
      type_name: isGroup
        ? resourceName(data.group, null)
        : String(meta.movie_type_display || meta.category_name || ""),
      vod_play_sources: withFallbackSource(playSources),
    };
    applyScrapeInfoToVod(vod, scrapeOut.metadata && scrapeOut.metadata.scrapeData);
    await fillMissingMetaFromTmdb(vod);
    if (!String(vod.vod_actor || "").trim() || !String(vod.vod_director || "").trim()) {
      OmniBox.log(
        "info",
        `聚影 影片信息待补: actor=${vod.vod_actor ? "有" : "空"} director=${vod.vod_director ? "有" : "空"} (TMDB_API_KEY=${process.env.TMDB_API_KEY ? "已配置" : "未配置"})`
      );
    }
    return { list: [vod] };
  } catch (error) {
    OmniBox.log("error", `聚影 获取详情失败: ${error.message}`);
    return { list: [] };
  }
}

// ==================== 磁力 115 秒传 ====================
// OK影视 无法直接播放 magnet:// 直链,配置 115 Cookie 后把磁力离线到 115 网盘,按文件生成分集
function isMagnetUrl(value) {
  return /^magnet:\?xt=urn:btih:/i.test(String(value || "").trim());
}

function build115MagnetCacheKey(magnet) {
  const hash = crypto.createHash("sha1").update(String(magnet || "").trim().toLowerCase()).digest("hex");
  return `jy:115magnet:${hash}`;
}

function build115FileCacheKey(fileName) {
  const hash = crypto.createHash("sha1").update(String(fileName || "").trim()).digest("hex");
  return `jy:115file:${hash}`;
}

function normalize115OfflineFiles(files) {
  return (Array.isArray(files) ? files : [])
    .map((file, index) => ({
      id: String((file && (file.id || file.fid || file.file_id || file.pickcode || file.pick_code)) || index).trim(),
      name: String((file && (file.name || file.file_name || file.server_filename)) || `115文件${index + 1}`).trim(),
      size: Number((file && (file.size || file.file_size)) || 0) || 0,
      pickcode: String((file && (file.pickcode || file.pick_code)) || "").trim(),
    }))
    .filter((file) => file.id && file.name);
}

function bodyJson(body) {
  if (body && typeof body === "object") return body;
  return parseJson(String(body || ""));
}

function build115Headers(extra) {
  return Object.assign(
    {
      "User-Agent": SITE_UA,
      Accept: "application/json, text/plain, */*",
      Cookie: MAGNET_115_COOKIE,
      Origin: "https://115.com",
      Referer: "https://115.com/web/lixian/",
      "X-Requested-With": "XMLHttpRequest",
    },
    extra || {}
  );
}

// 115 请求独立于站点请求:不共享 jying 的 Cookie,也不触发站点最小间隔
async function request115(url, options = {}) {
  const response = await axios({
    url,
    method: String(options.method || "GET").toUpperCase(),
    headers: options.headers || build115Headers(),
    params: options.params,
    data: options.body,
    timeout: options.timeout || 15000,
    httpsAgent: INSECURE_HTTPS_AGENT,
    maxRedirects: options.maxRedirects === undefined ? 5 : options.maxRedirects,
    responseType: "text",
    validateStatus: options.validateStatus || ((status) => status >= 200 && status < 400),
  });
  return { statusCode: response.status, body: response.data, headers: response.headers || {} };
}

async function pushMagnetTo115(magnet) {
  const normalizedMagnet = String(magnet || "").trim();
  const result = { ok: false, state: "unknown", files: [], magnet: normalizedMagnet };
  if (!MAGNET_115_COOKIE) return { ...result, state: "no_cookie" };
  if (!isMagnetUrl(normalizedMagnet)) return { ...result, state: "invalid_magnet" };

  const cacheKey = build115MagnetCacheKey(normalizedMagnet);
  const cached = await cacheGet(cacheKey);
  if (cached && Array.isArray(cached.files) && cached.files.length) {
    OmniBox.log("info", `聚影 115秒传缓存命中: files=${cached.files.length}`);
    return { ...cached, ok: true, state: cached.state || "cached", magnet: normalizedMagnet, cached: true };
  }
  const mem = memCache.get(cacheKey);
  if (mem && typeof mem === "object" && mem.__exp > Date.now()) {
    return { ...mem, ok: !!mem.ok, magnet: normalizedMagnet, cached: true };
  }

  try {
    const uidMatch = MAGNET_115_COOKIE.match(/UID=(\d+)/);
    const uid = uidMatch ? uidMatch[1] : "";
    if (!uid) return { ...result, state: "missing_uid" };

    const spaceRes = await request115("https://115.com/?ct=offline&ac=space");
    const spaceJson = bodyJson(spaceRes.body) || {};
    if (!spaceJson.state || !spaceJson.sign || !spaceJson.time) {
      OmniBox.log("warn", `聚影 115秒传签名获取失败: status=${spaceRes.statusCode}`);
      return { ...result, state: "space_invalid" };
    }

    const addTask = async () => {
      const res = await request115("https://115.com/web/lixian/?ct=lixian&ac=add_task_url", {
        method: "POST",
        headers: build115Headers({ "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8" }),
        body: `url=${encodeURIComponent(normalizedMagnet)}&uid=${encodeURIComponent(uid)}&sign=${encodeURIComponent(
          spaceJson.sign
        )}&time=${encodeURIComponent(spaceJson.time)}`,
        timeout: 20000,
      });
      return bodyJson(res.body) || {};
    };

    let files = [];
    let finalJson = {};
    let attempts = 0;
    for (let attempt = 0; attempt < 4; attempt++) {
      attempts = attempt + 1;
      finalJson = await addTask();
      files = normalize115OfflineFiles(finalJson.files || []);
      if (files.length) break;
      const submitted = finalJson.state || finalJson.errcode === 0 || finalJson.errcode === 10008;
      if (!submitted || attempt === 3) break;
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }

    const ok = Boolean(finalJson.state || finalJson.errcode === 0 || finalJson.errcode === 10008);
    const payload = {
      ...result,
      ok: ok && files.length > 0,
      state: finalJson.errcode === 10008 ? "exists" : files.length ? "submitted" : ok ? "submitted_waiting" : "add_failed",
      infoHash: String(finalJson.info_hash || "").trim(),
      files,
      attempts,
    };
    if (payload.ok) {
      OmniBox.log("info", `聚影 115秒传成功: files=${files.length}, attempts=${attempts}, 预览=${files
        .slice(0, 3)
        .map((file) => file.name)
        .join(" | ")}`);
      await cacheSet(cacheKey, payload, MAGNET_115_CACHE_EX);
      memCache.set(cacheKey, { ...payload, __exp: Date.now() + MAGNET_115_CACHE_EX * 1000 });
    } else {
      OmniBox.log(
        "warn",
        `聚影 115秒传未完成: state=${payload.state}, errcode=${finalJson.errcode || ""}, msg=${finalJson.error_msg || finalJson.msg || ""}`
      );
      memCache.set(cacheKey, { ...payload, __exp: Date.now() + 120 * 1000 });
    }
    return payload;
  } catch (error) {
    OmniBox.log("warn", `聚影 115秒传异常: ${error.message}`);
    memCache.set(cacheKey, { ...result, state: "exception", error: error.message, __exp: Date.now() + 120 * 1000 });
    return { ...result, state: "exception", error: error.message };
  }
}

function extractEpisodeNumber(name) {
  const text = String(name || "");
  const baseName = text.split(/[\\/]/).pop() || text;
  const basenamePatterns = [
    /^(\d{1,3})(?=\.(?!\d{3,4}p\b)|[._\-\s\[【])/i,
    /(?:^|[\s._\-【\[])(\d{1,3})(?=\.\d{3,4}p\b)/i,
  ];
  for (const pattern of basenamePatterns) {
    const match = baseName.match(pattern);
    if (!match) continue;
    const episode = Number(match[1]);
    if (Number.isFinite(episode) && episode > 0 && episode <= 300) return episode;
  }
  const patterns = [
    /S\d{1,2}E(\d{1,3})/i,
    /第\s*(\d{1,3})\s*[集话]/,
    /\[(\d{1,3})\s*[集话]\]/,
    /(?:^|[^A-Z0-9])E[P]?(\d{1,3})(?:[^A-Z0-9]|$)/i,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (!match) continue;
    const episode = Number(match[1]);
    if (Number.isFinite(episode) && episode > 0 && episode <= 300) return episode;
  }
  return null;
}

function sort115Episodes(episodes) {
  return episodes
    .map((episode, index) => ({ episode, index }))
    .sort((a, b) => {
      const aNo = a.episode._episodeNumber;
      const bNo = b.episode._episodeNumber;
      const aValid = Number.isFinite(aNo);
      const bValid = Number.isFinite(bNo);
      if (aValid && bValid && aNo !== bNo) return aNo - bNo;
      if (aValid !== bValid) return aValid ? -1 : 1;
      if (a.index !== b.index) return a.index - b.index;
      return String(a.episode.rawName || "").localeCompare(String(b.episode.rawName || ""), "zh-Hans-CN", {
        numeric: true,
      });
    })
    .map((entry) => entry.episode);
}

// 详情页把前 N 条磁力离线到 115 并按文件生成分集;失败时静默回退到磁力线路
async function build115MagnetSource(items, videoId) {
  if (!MAGNET_115_ENABLED || MAX_MAGNET_115 <= 0) return null;

  const magnets = [];
  for (const item of Array.isArray(items) ? items : []) {
    if (magnets.length >= MAX_MAGNET_115) break;
    if (resourceType(item) !== "magnet") continue;
    if (rateLimitRemaining("/api/app/resource/0/access/") > 0) {
      OmniBox.log("warn", "聚影 115秒传跳过: 站点 access 限流冷却中");
      break;
    }
    try {
      const url = normalizePlayUrl(await accessResource(item));
      if (isMagnetUrl(url) && !magnets.includes(url)) magnets.push(url);
    } catch (error) {
      OmniBox.log("warn", `聚影 115秒传获取磁力失败: ${error.message}`);
    }
  }
  if (!magnets.length) return null;

  const episodes = [];
  for (const magnet of magnets) {
    try {
      const pushed = await pushMagnetTo115(magnet);
      if (!pushed.ok || !pushed.files.length) continue;
      for (const file of pushed.files) {
        const rawName = String(file.name || "").trim();
        if (!rawName) continue;
        const label = file.size > 0 ? `[${formatFileSize(file.size)}] ${rawName}` : rawName;
        episodes.push({
          name: escapePlayName(label),
          playId: encodePlayMeta({
            k: "m115",
            m: magnet,
            fi: file.id,
            pn: file.pickcode,
            fn: rawName,
            v: videoId || "",
            e: rawName,
          }),
          size: file.size > 0 ? file.size : undefined,
          rawName,
          episodeName: rawName,
          _episodeNumber: extractEpisodeNumber(rawName),
        });
        if (episodes.length >= MAX_EPISODES) break;
      }
      if (episodes.length >= MAX_EPISODES) break;
    } catch (error) {
      OmniBox.log("warn", `聚影 115秒传生成分集失败: ${error.message}`);
    }
  }
  if (!episodes.length) return null;

  const sorted = sort115Episodes(episodes);
  OmniBox.log(
    "info",
    `聚影 115秒传分集生成完成: ${sorted.length} 个, 预览=${sorted
      .slice(0, 3)
      .map((item) => item.episodeName)
      .join(" | ")}`
  );
  return { name: "115秒传", episodes: sorted };
}

async function find115FileByName(fileName) {
  const targetName = String(fileName || "").trim();
  if (!targetName || !MAGNET_115_COOKIE) return null;
  const cacheKey = build115FileCacheKey(targetName);
  const cached = await cacheGet(cacheKey);
  if (cached && (cached.fid || cached.pickcode)) return cached;
  const mem = memCache.get(cacheKey);
  if (mem && typeof mem === "object" && (mem.fid || mem.pickcode)) return mem;

  const keyword = targetName.split(/[\\/]/).pop().replace(/\.[a-z0-9]{2,5}$/i, "").slice(0, 80);
  const res = await request115(`https://webapi.115.com/files/search?search_value=${encodeURIComponent(keyword)}&format=json&type=4&limit=50`);
  const json = bodyJson(res.body) || {};
  const list = Array.isArray(json && json.data)
    ? json.data
    : Array.isArray(json && json.data && json.data.list)
      ? json.data.list
      : Array.isArray(json && json.files)
        ? json.files
        : [];
  const normalized = list
    .map((item) => ({
      fid: String((item && (item.fid || item.file_id || item.id || item.cid)) || "").trim(),
      name: String((item && (item.n || item.name || item.file_name || item.server_filename)) || "").trim(),
      pickcode: String((item && (item.pc || item.pickcode || item.pick_code)) || "").trim(),
      size: Number((item && (item.s || item.size || item.file_size)) || 0) || 0,
    }))
    .filter((item) => item.name && (item.fid || item.pickcode));
  const baseNameOf = (value) => String(value || "").split(/[\\/]/).pop().trim();
  const matched = normalized.find((item) => baseNameOf(item.name) === baseNameOf(targetName)) || normalized[0] || null;
  OmniBox.log("info", `聚影 115文件搜索: keyword=${keyword}, 命中=${matched ? matched.name : "无"}`);
  if (matched) {
    await cacheSet(cacheKey, matched, MAGNET_115_CACHE_EX);
    memCache.set(cacheKey, matched);
  }
  return matched;
}

async function get115VideoPlayUrl(file) {
  const pickcode = String((file && (file.pickcode || file.pc)) || "").trim();
  if (!pickcode) throw new Error("115 文件缺少 pickcode");
  const candidates = [
    `https://115.com/api/video/m3u8/${encodeURIComponent(pickcode)}.m3u8`,
    `https://webapi.115.com/files/video?pickcode=${encodeURIComponent(pickcode)}`,
  ];
  let lastError = null;
  for (const url of candidates) {
    try {
      const res = await request115(url, { maxRedirects: 0, validateStatus: (status) => status >= 200 && status < 400 });
      const location = String((res.headers && res.headers.location) || "");
      if (location) return location;
      const text = String(res.body || "");
      if (text.includes("#EXTM3U")) return url;
      const data = bodyJson(res.body) || {};
      const candidate =
        (data.data && (data.data.video_url || data.data.url || data.data.m3u8)) ||
        data.video_url ||
        data.url ||
        data.m3u8 ||
        "";
      if (candidate) return String(candidate);
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error("115未返回可播放地址");
}

async function resolve115MagnetPlay(meta) {
  const magnet = String((meta && meta.m) || "").trim();
  if (!magnet) throw new Error("缺少磁力链接");
  const pushed = await pushMagnetTo115(magnet);
  if (!pushed.ok || !pushed.files.length) throw new Error(`115秒传未完成: ${pushed.state || "unknown"}`);

  const fileId = String((meta && meta.fi) || "");
  const target = pushed.files.find((file) => String(file.id) === fileId) || pushed.files[0];
  if (!target) throw new Error("115秒传未返回目标文件");

  const realFile = (await find115FileByName(String(meta.fn || "").trim())) || (await find115FileByName(target.name));
  if (!realFile) throw new Error("115网盘内未找到该文件");

  const url = await get115VideoPlayUrl(realFile);
  if (!url) throw new Error("115未返回可播放地址");
  return {
    url,
    name: String((meta && meta.e) || realFile.name || target.name || "115播放"),
    header: { "User-Agent": SITE_UA, Referer: "https://115.com/", Cookie: MAGNET_115_COOKIE },
  };
}

function recordHistory(params, vodId, playId, context) {
  try {
    const sourceId = context && context.sourceId;
    if (!sourceId || typeof OmniBox.addPlayHistory !== "function") return;
    OmniBox.addPlayHistory({
      vodId: String(vodId || ""),
      title: (params && params.title) || "",
      pic: (params && params.pic) || "",
      episode: playId,
      sourceId,
      episodeNumber: null,
      episodeName: (params && params.episodeName) || "",
    })
      .then((added) => {
        if (added) OmniBox.log("info", "聚影 已添加观看记录");
      })
      .catch((error) => {
        OmniBox.log("warn", `聚影 添加观看记录失败: ${error.message}`);
      });
  } catch (error) {
    OmniBox.log("warn", `聚影 添加观看记录失败: ${error.message}`);
  }
}

function directHeader(url) {
  const value = String(url || "").toLowerCase();
  if (value.startsWith("magnet:") || value.startsWith("ed2k://")) return {};
  return { "User-Agent": SITE_UA };
}

async function resolveDanmaku(playInfo, meta) {
  const fallback = playInfo && Array.isArray(playInfo.danmaku) ? playInfo.danmaku : [];
  try {
    if (!SCRAPING_ENABLED || !meta.v || !meta.f) return fallback;
    const cached = await cacheGet(`jy:meta:${meta.v}`);
    if (!cached || !cached.scrapeData || !Array.isArray(cached.videoMappings)) return fallback;
    const mapping = cached.videoMappings.find(
      (item) => item && String(item.fileId) === `${meta.u}|${meta.f}|${meta.v}`
    );
    if (!mapping) return fallback;

    const scrapeData = cached.scrapeData;
    const title = String(scrapeData.title || "");
    const season = String(mapping.seasonNumber || 1).padStart(2, "0");
    const episode = String(mapping.episodeNumber || 1).padStart(2, "0");
    const seriesName = title ? `${title}.${scrapeData.seasonAirYear || ""}.S${season}E${episode}` : "";
    const preferMovie = Number(meta.m || 0) === 1 || String(cached.scrapeType || "").toLowerCase() === "movie";
    // 电影优先按片名匹配(避免 "标题..S01E01" 这种剧集式文件名),匹配不上再退回剧集式,保证不劣化
    const candidates = preferMovie ? [title, seriesName] : [seriesName];
    for (const fileName of candidates) {
      if (!fileName) continue;
      const list = await OmniBox.getDanmakuByFileName(fileName);
      if (Array.isArray(list) && list.length) {
        OmniBox.log("info", `聚影 弹幕匹配成功: ${fileName}, 条数=${list.length}`);
        return list;
      }
    }
    return fallback;
  } catch (error) {
    OmniBox.log("warn", `聚影 弹幕匹配失败: ${error.message}`);
    return fallback;
  }
}

async function play(params, context) {
  const flag = String((params && params.flag) || "");
  try {
    let playId = String((params && params.playId) || "");
    if (playId.indexOf("push://") === 0) playId = playId.slice(7).trim();
    const callerSource = resolveCallerSource(params || {}, context || {});
    const routeType = resolveRouteType(flag, callerSource, context || {});
    OmniBox.log("info", `聚影 播放: flag=${flag}, 线路=${routeType}`);

    if (!playId) throw new Error("播放参数不能为空");
    let meta = decodePlayMeta(playId);
    if (!meta.k) {
      // 兜底: 兼容调用方直接把 vod_id 或原始链接当作播放参数
      const [idType, idData] = decodeId(playId);
      if (idType === "res") {
        const url = normalizePlayUrl(await accessResource(idData));
        if (!url) throw new Error("资源链接为空");
        meta = classifyPlayUrl(url, idData) === "pan" ? { k: "pan", u: url, v: "" } : { k: "direct", u: url, v: "" };
      } else if (/^(https?|magnet|ed2k):/i.test(playId)) {
        meta = { k: "direct", u: playId, v: "" };
      }
    }
    const kind0 = String(meta.k || "");
    if (kind0 === "lazy") {
      const item = meta.r || {};
      const url = normalizePlayUrl(await accessResource(item));
      if (!url) throw new Error("资源链接为空");
      meta =
        classifyPlayUrl(url, item) === "pan"
          ? { k: "pan", u: url, v: meta.v || "", e: meta.e || "" }
          : { k: "direct", u: url, v: meta.v || "" };
    }
    const kind = String(meta.k || "");

    if (kind === "empty") {
      return { urls: [], flag, header: {}, parse: 0, danmaku: [] };
    }

    if (kind === "m115") {
      const info = await resolve115MagnetPlay(meta);
      recordHistory(params, meta.v, playId, context);
      OmniBox.log("info", `聚影 115秒传播放地址已获取: ${info.name}`);
      return { urls: [{ name: "播放", url: info.url }], flag, header: info.header, parse: 0, danmaku: [] };
    }

    if (kind === "direct") {
      const url = String(meta.u || "");
      if (!url) throw new Error("播放地址为空");
      recordHistory(params, meta.v, playId, context);
      const danmaku = await resolveDanmaku(null, meta);
      return { urls: [{ name: "播放", url }], flag, header: directHeader(url), parse: 0, danmaku };
    }

    if (kind === "pan") {
      const rawShareURL = String(meta.u || "");
      let fileId = String(meta.f || "");
      if (!rawShareURL) throw new Error("分享链接为空");
      const candidates = await pan123Candidates(rawShareURL);
      if (!fileId) {
        const files = await videoFilesCached(rawShareURL);
        const first = Array.isArray(files) ? files[0] : null;
        fileId = first ? String(first.fid || first.file_id || "") : "";
        if (!fileId) throw new Error("网盘分享中未找到视频文件");
      }

      let playInfo = null;
      let shareURL = candidates[0];
      const errors = [];
      for (const candidate of candidates) {
        try {
          const info = await OmniBox.getDriveVideoPlayInfo(candidate, fileId, routeType);
          const list = info && Array.isArray(info.url) ? info.url : [];
          if (list.length) {
            playInfo = info;
            shareURL = candidate;
            break;
          }
          errors.push(new Error("无法获取播放地址"));
        } catch (error) {
          errors.push(error);
          if (candidates.length > 1) {
            OmniBox.log("warn", `聚影 获取播放地址失败(${candidate.split("?")[0]}): ${error.message}`);
          }
        }
      }
      if (!playInfo) {
        if (candidates.length > 1 && errors.length) {
          const uniq = [...new Set(errors.map((error) => error.message))];
          throw new Error(`123分享候选域名均失败(${candidates.length}): ${uniq.join(" / ")}`);
        }
        throw errors[0] || new Error("无法获取播放地址");
      }
      const urlList = playInfo.url;
      if (!urlList.length) throw new Error("无法获取播放地址");

      const urls = urlList
        .map((item) => ({ name: (item && item.name) || "播放", url: (item && item.url) || "" }))
        .filter((item) => item.url);
      if (!urls.length) throw new Error("无法获取播放地址");

      let header = (playInfo && playInfo.header) || {};
      const lower = shareURL.toLowerCase();
      if (
        (lower.includes("drive.uc.cn") || lower.includes("pc-api.uc.cn") || lower.includes("uc.cn/s/")) &&
        routeType === "直连"
      ) {
        header = {};
      }

      recordHistory(params, meta.v, playId, context);
      const danmaku = await resolveDanmaku(playInfo, meta);
      OmniBox.log("info", `聚影 播放地址已获取: ${urls.length} 条`);
      return { urls, flag, header, parse: 0, danmaku };
    }

    throw new Error("未知的播放参数");
  } catch (error) {
    OmniBox.log("error", `聚影 播放失败: ${error.message}`);
    return { urls: [], flag, header: {}, parse: 0, danmaku: [] };
  }
}

module.exports = {
  home,
  category,
  search,
  detail,
  play,
  login,
  logout,
  getLoginStatus,
};

let runner;
try {
  runner = require("spider_runner");
} catch (_) {
  runner = { run() {} };
}
runner.run(module.exports);
