// @name 黄色仓库
// @version 1.4.0
// @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/🔞黄色仓库.js
/**
 * 黄色仓库 MacCMS 采集源（OmniBox）
 * 镜像池自动切换，优先 m3u8 直链
 */

const OmniBox = require("omnibox_sdk");

const SITE_API_POOL = [
  "https://api.hsckzy.vip/api.php/provide/vod",
  "https://hsckzy.vip/api.php/provide/vod",
  "https://hsckzy888.com/api.php/provide/vod",
  "https://hsckzy001.com/api.php/provide/vod",
  "https://hsckzy.net/api.php/provide/vod",
  "https://cj.hsckzy.vip/api.php/provide/vod",
];
const SITE_API = process.env.SITE_API || SITE_API_POOL[0];
let _activeApi = SITE_API;

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
const PLAY_HEADER = {
  "User-Agent": UA,
  Referer: "https://hsckzy.vip/",
};

function toInt(value) {
  if (typeof value === "number") return Math.floor(value);
  if (typeof value === "string") {
    const n = parseInt(value, 10);
    return isNaN(n) ? 0 : n;
  }
  return 0;
}

async function requestSiteAPI(params) {
  params = params || {};
  const bases = [_activeApi].concat(SITE_API_POOL.filter(function (x) { return x !== _activeApi; }));
  var lastErr = null;
  for (var bi = 0; bi < bases.length; bi++) {
    var base = bases[bi];
    try {
      var url = new URL(base);
      Object.keys(params).forEach(function (key) {
        if (params[key] !== undefined && params[key] !== null && params[key] !== "") {
          url.searchParams.append(key, params[key]);
        }
      });
      OmniBox.log("info", "请求采集站: " + url.toString());
      var response = await OmniBox.request(url.toString(), {
        method: "GET",
        headers: { "User-Agent": UA, Accept: "application/json" },
        timeout: 15,
      });
      if (response.statusCode !== 200) {
        lastErr = new Error("HTTP " + response.statusCode);
        continue;
      }
      var data = JSON.parse(response.body || "{}");
      if (!data || typeof data !== "object" || Array.isArray(data)) {
        lastErr = new Error("响应格式异常");
        continue;
      }
      _activeApi = base;
      return data;
    } catch (e) {
      lastErr = e;
      OmniBox.log("warn", "镜像失败 " + base + ": " + e.message);
    }
  }
  throw lastErr || new Error("全部镜像失败");
}

function formatVideos(list) {
  if (!Array.isArray(list)) return [];
  var out = [];
  for (var i = 0; i < list.length; i++) {
    var item = list[i];
    if (!item || typeof item !== "object") continue;
    var vodId = String(item.vod_id || item.VodID || "");
    if (!vodId) continue;
    out.push({
      vod_id: vodId,
      vod_name: String(item.vod_name || item.VodName || ""),
      vod_pic: String(item.vod_pic || item.VodPic || ""),
      type_id: String(item.type_id || item.TypeID || ""),
      type_name: String(item.type_name || item.TypeName || ""),
      vod_year: String(item.vod_year || item.VodYear || ""),
      vod_remarks: String(item.vod_remarks || item.VodRemarks || ""),
    });
  }
  return out;
}

function formatClasses(classes) {
  if (!Array.isArray(classes)) return [];
  var seen = {};
  var out = [];
  for (var i = 0; i < classes.length; i++) {
    var cls = classes[i];
    if (!cls || typeof cls !== "object") continue;
    var typeId = String(cls.type_id || cls.TypeID || "");
    var typeName = String(cls.type_name || cls.TypeName || "");
    if (!typeId || seen[typeId]) continue;
    seen[typeId] = 1;
    out.push({ type_id: typeId, type_name: typeName || ("分类" + typeId) });
  }
  return out;
}

function isMedia(url) {
  return /\.(m3u8|mp4)(\?|$)/i.test(url || "") || /\/index\.m3u8/i.test(url || "");
}

function toM3u8(url) {
  var u = String(url || "").trim();
  if (!u) return "";
  var m = u.match(/\/share\/([^?&#]+)/i);
  if (m && !/\.m3u8/i.test(u)) {
    return "https://hsm3.hwzcfz.com/" + m[1].replace(/\/+$/, "") + "/index.m3u8";
  }
  return u;
}

function convertToPlaySources(vodPlayFrom, vodPlayUrl) {
  var names = String(vodPlayFrom || "").split("$$$").map(function (s) { return s.trim(); }).filter(Boolean);
  var blocks = String(vodPlayUrl || "").split("$$$").map(function (s) { return s.trim(); }).filter(Boolean);
  var sources = [];
  var n = Math.max(names.length, blocks.length);
  for (var i = 0; i < n; i++) {
    var sourceName = names[i] || ("线路" + (i + 1));
    var block = blocks[i] || "";
    var episodes = [];
    var segs = block.split("#");
    for (var j = 0; j < segs.length; j++) {
      var seg = segs[j].trim();
      if (!seg) continue;
      var epName, playId;
      var dollar = seg.indexOf("$");
      if (dollar >= 0) {
        epName = seg.slice(0, dollar).trim() || "正片";
        playId = toM3u8(seg.slice(dollar + 1).trim());
      } else {
        epName = "正片";
        playId = toM3u8(seg);
      }
      if (playId) episodes.push({ name: epName, playId: playId });
    }
    if (episodes.length > 0) {
      sources.push({ name: sourceName, episodes: episodes });
    }
  }
  sources.sort(function (a, b) {
    var au = (a.episodes[0] && a.episodes[0].playId) || "";
    var bu = (b.episodes[0] && b.episodes[0].playId) || "";
    return (isMedia(au) ? 0 : 1) - (isMedia(bu) ? 0 : 1);
  });
  var media = sources.filter(function (s) {
    return isMedia((s.episodes[0] && s.episodes[0].playId) || "");
  });
  return media.length ? media : sources;
}

async function home(params) {
  try {
    OmniBox.log("info", "获取首页数据");
    var page = (params && params.page) || "1";
    var response = await requestSiteAPI({ ac: "list", pg: String(page) });

    if (!response.class || !response.class.length) {
      try {
        var classResponse = await requestSiteAPI({ ac: "class" });
        if (classResponse.class && classResponse.class.length) {
          response.class = classResponse.class;
        }
      } catch (e) {}
    }
    if (!response.class || !response.class.length) {
      var seen = {};
      var synth = [];
      var list = response.list || [];
      for (var i = 0; i < list.length; i++) {
        var item = list[i];
        var tid = String(item.type_id || "");
        var tname = String(item.type_name || tid || "分类");
        if (!tid || seen[tid]) continue;
        seen[tid] = 1;
        synth.push({ type_id: tid, type_name: tname });
      }
      response.class = synth;
    }

    var classes = formatClasses(response.class || []);
    var videos = formatVideos(response.list || []);

    return {
      class: classes,
      list: videos,
    };
  } catch (error) {
    OmniBox.log("error", "获取首页数据失败: " + error.message);
    return {
      class: [],
      list: [],
    };
  }
}

async function category(params) {
  try {
    var categoryId = (params && params.categoryId) || "";
    var page = (params && params.page) || 1;
    OmniBox.log("info", "获取分类: categoryId=" + categoryId + ", page=" + page);

    var response = await requestSiteAPI({
      ac: "videolist",
      t: String(categoryId),
      pg: String(page),
    });

    var videos = formatVideos(response.list || []);
    return {
      page: toInt(response.page) || toInt(page) || 1,
      pagecount: toInt(response.pagecount) || 1,
      total: toInt(response.total) || 0,
      list: videos,
    };
  } catch (error) {
    OmniBox.log("error", "获取分类失败: " + error.message);
    return {
      page: 1,
      pagecount: 0,
      total: 0,
      list: [],
    };
  }
}

async function detail(params) {
  try {
    var videoId = (params && params.videoId) || "";
    if (!videoId) {
      throw new Error("视频ID不能为空");
    }
    OmniBox.log("info", "获取视频详情: videoId=" + videoId);

    var response = await requestSiteAPI({
      ac: "detail",
      ids: String(videoId),
    });

    var item = (response.list || [])[0];
    if (!item) {
      return { list: [] };
    }

    var sources = convertToPlaySources(item.vod_play_from, item.vod_play_url);
    var content = String(item.vod_content || "").replace(/<[^>]+>/g, "").trim();

    return {
      list: [
        {
          vod_id: String(item.vod_id || videoId),
          vod_name: String(item.vod_name || ""),
          vod_pic: String(item.vod_pic || ""),
          type_name: String(item.type_name || ""),
          vod_year: String(item.vod_year || ""),
          vod_area: String(item.vod_area || ""),
          vod_remarks: String(item.vod_remarks || ""),
          vod_actor: String(item.vod_actor || ""),
          vod_director: String(item.vod_director || ""),
          vod_content: content,
          vod_play_sources: sources,
        },
      ],
    };
  } catch (error) {
    OmniBox.log("error", "获取视频详情失败: " + error.message);
    return { list: [] };
  }
}

async function search(params) {
  try {
    var keyword = (params && (params.keyword || params.wd)) || "";
    var page = (params && params.page) || 1;
    if (!keyword) {
      return { page: 1, pagecount: 0, total: 0, list: [] };
    }
    OmniBox.log("info", "搜索视频: keyword=" + keyword + ", page=" + page);

    var response = await requestSiteAPI({
      ac: "list",
      wd: String(keyword),
      pg: String(page),
    });

    return {
      page: toInt(response.page) || toInt(page) || 1,
      pagecount: toInt(response.pagecount) || 1,
      total: toInt(response.total) || 0,
      list: formatVideos(response.list || []),
    };
  } catch (error) {
    OmniBox.log("error", "搜索视频失败: " + error.message);
    return { page: 1, pagecount: 0, total: 0, list: [] };
  }
}

async function play(params) {
  try {
    var playId = (params && params.playId) || "";
    var flag = (params && params.flag) || "";
    if (!playId) {
      throw new Error("播放地址ID不能为空");
    }
    OmniBox.log("info", "获取播放地址: playId=" + playId);

    playId = toM3u8(playId);
    var media = isMedia(playId);

    return {
      urls: [{ name: "播放", url: playId }],
      flag: flag,
      header: PLAY_HEADER,
      parse: media ? 0 : 1,
    };
  } catch (error) {
    OmniBox.log("error", "获取播放地址失败: " + error.message);
    return {
      urls: [],
      flag: (params && params.flag) || "",
      header: PLAY_HEADER,
      parse: 0,
    };
  }
}

module.exports = {
  home: home,
  category: category,
  search: search,
  detail: detail,
  play: play,
};

try {
  var runner = require("spider_runner");
  runner.run(module.exports);
} catch (e) {
  // 非 runner 环境忽略
}
