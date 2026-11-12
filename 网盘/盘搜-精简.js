// @name 盘搜-精简
// @author becauseyour
// @description 对接本地盘搜API，仅保留115/百度/阿里/夸克，使用OmniBox网盘SDK解析播放
// @version 1.4.3

const OmniBox = require("omnibox_sdk");

const PANSOU_API = process.env.PANSOU_API || "http://192.168.2.1:17080";

// 只保留这些网盘类型
const ALLOWED_TYPES = new Set(["115", "baidu", "aliyun", "quark"]);

function isVideoFile(file) {
  if (!file || !file.file_name) return false;
  const name = String(file.file_name).toLowerCase();
  return /\.(mp4|mkv|avi|mov|wmv|flv|webm|m4v|ts|rmvb|rm|3gp)$/i.test(name);
}

function detectType(url) {
  if (!url) return "";
  const u = String(url).toLowerCase();
  // 115 识别放宽：包含 115 即可（兼容短链/其他域名）
  if (u.includes("115")) return "115";
  if (u.includes("baidu") || u.includes("pan.baidu")) return "baidu";
  if (u.includes("aliyun") || u.includes("alipan") || u.includes("aliyundrive")) return "aliyun";
  if (u.includes("quark")) return "quark";
  return "";
}

function isAllowed(url, typeHint) {
  const t = (typeHint || detectType(url) || "").toLowerCase();
  return ALLOWED_TYPES.has(t);
}

async function searchPansou(keyword) {
  const url = `${PANSOU_API}/api/search`;
  OmniBox.log("info", `[盘搜] POST ${url} kw=${keyword}`);

  const res = await OmniBox.request(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      kw: keyword,
      res: "merge",
      src: "all",
      cloud_types: ["115", "baidu", "aliyun", "quark"],
    }),
  });

  let body = res.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch { body = {}; }
  }
  return body?.data || body || {};
}

async function getAllVideoFiles(shareURL, files) {
  const videoFiles = [];
  for (const file of files || []) {
    if (file.file && isVideoFile(file)) {
      videoFiles.push(file);
    } else if (file.dir) {
      try {
        const sub = await OmniBox.getDriveFileList(shareURL, file.fid);
        if (sub?.files) {
          const subVideos = await getAllVideoFiles(shareURL, sub.files);
          videoFiles.push(...subVideos);
        }
      } catch (e) {
        OmniBox.log("warn", `子目录失败: ${e.message}`);
      }
    }
  }
  return videoFiles;
}

async function home() {
  return { class: [], list: [], filters: {} };
}

async function category() {
  return { list: [], page: 1, pagecount: 0, total: 0 };
}

async function search(params) {
  const keyword = (params.keyword || params.wd || "").trim();
  const page = parseInt(params.page || "1", 10);
  if (!keyword || page > 1) {
    return { list: [], page, pagecount: 1, total: 0 };
  }

  try {
    const data = await searchPansou(keyword);
    const list = [];

    const merged = data.merged_by_type || data.mergedByType || {};
    for (const [type, items] of Object.entries(merged)) {
      const t = String(type).toLowerCase();
      // 兼容 API 返回的类型名
      const normalized = t === "115" || t.includes("115") ? "115" :
                         t.includes("baidu") ? "baidu" :
                         t.includes("ali") ? "aliyun" :
                         t.includes("quark") ? "quark" : t;
      if (!ALLOWED_TYPES.has(normalized)) continue;
      if (!Array.isArray(items)) continue;
      for (const item of items) {
        const url = item.url || item.link;
        if (!url || !isAllowed(url, normalized)) continue;
        list.push({
          vod_id: url,
          vod_name: item.note || item.title || keyword,
          vod_pic: (item.images && item.images[0]) || "",
          vod_remarks: normalized + (item.password ? ` 提取码:${item.password}` : ""),
          vod_tag: normalized,
        });
      }
    }

    if (list.length === 0 && Array.isArray(data.results)) {
      for (const item of data.results) {
        for (const lk of item.links || []) {
          const url = lk.url || lk.link;
          const t = (lk.type || detectType(url) || "").toLowerCase();
          const normalized = t.includes("115") ? "115" :
                             t.includes("baidu") ? "baidu" :
                             t.includes("ali") ? "aliyun" :
                             t.includes("quark") ? "quark" : t;
          if (!url || !ALLOWED_TYPES.has(normalized)) continue;
          list.push({
            vod_id: url,
            vod_name: item.title || keyword,
            vod_pic: (item.images && item.images[0]) || "",
            vod_remarks: normalized + (lk.password ? ` 提取码:${lk.password}` : ""),
            vod_tag: normalized,
          });
        }
      }
    }

    OmniBox.log("info", `[盘搜] 搜索到 ${list.length} 条（仅115/百度/阿里/夸克）`);
    return { list, page: 1, pagecount: 1, total: list.length };
  } catch (e) {
    OmniBox.log("error", `[盘搜] 搜索失败: ${e.message}`);
    return { list: [], page: 1, pagecount: 0, total: 0 };
  }
}

async function detail(params) {
  const videoId = params.videoId || params.id || params.vod_id || "";
  if (!videoId) return { list: [] };

  const shareURL = videoId.split("|")[0];
  if (!shareURL || !isAllowed(shareURL)) return { list: [] };

  OmniBox.log("info", `[detail] shareURL=${shareURL}`);

  try {
    const [driveInfo, fileList] = await Promise.all([
      OmniBox.getDriveInfoByShareURL(shareURL),
      OmniBox.getDriveFileList(shareURL, "0"),
    ]);

    if (!fileList?.files) {
      throw new Error("获取文件列表失败");
    }

    const allVideoFiles = await getAllVideoFiles(shareURL, fileList.files);
    OmniBox.log("info", `[detail] 视频文件数: ${allVideoFiles.length}`);

    if (allVideoFiles.length === 0) {
      throw new Error("未找到视频文件");
    }

    const episodes = allVideoFiles.map((file) => {
      const fileId = file.fid || file.file_id || "";
      const fileName = file.file_name || fileId;
      return {
        name: fileName,
        playId: `${shareURL}|${fileId}`,
        size: file.size || file.file_size || 0,
      };
    });

    const displayName = driveInfo?.displayName || shareURL.split("/").pop() || "分享链接";
    const driveType = detectType(shareURL) || driveInfo?.driveType || "";

    return {
      list: [
        {
          vod_id: shareURL,
          vod_name: displayName,
          vod_pic: "",
          vod_remarks: driveType,
          vod_play_sources: [
            {
              name: driveInfo?.displayName || driveType,
              episodes,
            },
          ],
        },
      ],
    };
  } catch (e) {
    OmniBox.log("error", `[detail] ${e.message}`);
    return { list: [] };
  }
}

async function play(params) {
  const playId = params.playId || "";
  if (!playId) return { urls: [], header: {}, danmaku: [] };

  const parts = playId.split("|");
  if (parts.length < 2) return { urls: [], header: {}, danmaku: [] };

  const shareURL = parts[0];
  const fileId = parts[1];

  if (!isAllowed(shareURL)) {
    OmniBox.log("warn", `[play] 不支持的网盘类型: ${shareURL}`);
    return { urls: [], header: {}, danmaku: [] };
  }

  OmniBox.log("info", `[play] shareURL=${shareURL}, fileId=${fileId}`);

  try {
    const playInfo = await OmniBox.getDriveVideoPlayInfo(shareURL, fileId, "直连");
    if (!playInfo?.url || !Array.isArray(playInfo.url) || playInfo.url.length === 0) {
      throw new Error("无法获取播放地址");
    }

    const urls = playInfo.url.map((item) => ({
      name: item.name || "播放",
      url: item.url,
    }));

    return {
      urls,
      header: playInfo.header || {},
      parse: 0,
      danmaku: playInfo.danmaku || [],
    };
  } catch (e) {
    OmniBox.log("error", `[play] ${e.message}`);
    return { urls: [], header: {}, danmaku: [] };
  }
}

module.exports = { home, category, search, detail, play };

const runner = require("spider_runner");
runner.run(module.exports);
