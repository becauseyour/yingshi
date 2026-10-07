# -*- coding: utf-8 -*-
# @name 51吃瓜网
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/Silent1566/OmniBox-Spider/main/影视/采集/51吃瓜网.py
# @indexs 1
# @dependencies pycryptodome,pyquery
# @description 51吃瓜/51吸瓜站源（OmniBox 适配版）：动态站点探测、分类/搜索/详情、直链播放

"""
51吃瓜网 — OmniBox 适配版

原 T3 接口已统一为 OmniBox handler 签名 (params, context)。
站点候选: artist/ability/am.vgwtswi.xyz，失败回退 https://51cg1.com
封面 AES 解密在 OmniBox 中尽量直出原始图链；播放返回标准 urls 结构。
"""

import json
import re
import base64
from urllib.parse import urlparse, quote

from spider_runner import OmniBox, run

try:
    from pyquery import PyQuery as pq
except ImportError:
    pq = None

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except ImportError:
    AES = None
    unpad = None

PAGE_SIZE = 90
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
)
FALLBACK_HOST = "https://51cg1.com"
DYNAMIC_HOSTS = [
    "https://artist.vgwtswi.xyz",
    "https://ability.vgwtswi.xyz",
    "https://am.vgwtswi.xyz",
]

# 模块级状态
_host = ""
_headers = {}
_proxies = {}  # 保留 extend 代理配置（若环境支持）


def _safe_label(value):
    return str(value or "").replace("$", "＄").replace("#", "＃").strip()


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _is_video_format(url):
    path = urlparse(str(url or "")).path.lower()
    return any(path.endswith(ext) for ext in [".m3u8", ".mp4", ".ts", ".flv", ".mkv"])


def _getpq(data):
    if pq is None:
        raise RuntimeError("pyquery 未安装")
    try:
        return pq(data)
    except Exception:
        return pq(data.encode("utf-8") if isinstance(data, str) else data)


async def _http_get(url, timeout=12):
    res = await OmniBox.request(
        url,
        {
            "method": "GET",
            "headers": _headers,
            "timeout": timeout,
        },
    )
    status = res.get("statusCode") or 0
    body = res.get("body") or ""
    headers = res.get("headers") or {}
    return status, body, headers


async def _ensure_host():
    global _host, _headers
    if _host:
        return _host

    base_headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

    for url in DYNAMIC_HOSTS:
        try:
            res = await OmniBox.request(
                url,
                {"method": "GET", "headers": base_headers, "timeout": 3},
            )
            if (res.get("statusCode") or 0) == 200:
                text = res.get("body") or ""
                if pq and len(_getpq(text)("#index article a")) > 0:
                    _host = url
                    _headers = dict(base_headers)
                    _headers.update({"Origin": _host, "Referer": f"{_host}/"})
                    await OmniBox.log("info", f"[init] 站点: {_host}")
                    return _host
        except Exception:
            continue

    _host = FALLBACK_HOST
    _headers = dict(base_headers)
    _headers.update({"Origin": _host, "Referer": f"{_host}/"})
    await OmniBox.log("info", f"[init] 回退站点: {_host}")
    return _host


def _getlist(data, tid=""):
    videos = []
    is_folder = "/mrdg" in str(tid)
    for k in data.items():
        a = k.attr("href")
        b = k("h2").text()
        c = (
            k('span[itemprop="datePublished"]').text()
            or k(".post-meta, .entry-meta, time").text()
        )
        if a and b:
            item = {
                "vod_id": f"{a}{'@folder' if is_folder else ''}",
                "vod_name": _safe_label(b.replace("\n", " ")),
                "vod_pic": _getimg(k("script").text()),
                "vod_remarks": _safe_label(c),
            }
            if is_folder:
                item["vod_tag"] = "folder"
            videos.append(item)
    return videos


def _getimg(text):
    match = re.search(r"loadBannerDirect\('([^']+)'", text or "")
    if match:
        return match.group(1)
    return ""


async def _getfod(folder_id):
    host = await _ensure_host()
    url = f"{host}{folder_id}"
    status, body, _ = await _http_get(url, timeout=12)
    if status != 200:
        return []

    data = _getpq(body)
    vdata = data('.post-content[itemprop="articleBody"]')
    for i in [".txt-apps", ".line", "blockquote", ".tags", ".content-tabs"]:
        vdata.remove(i)

    p = vdata("p")
    videos = []
    for i, x in enumerate(vdata("h2").items()):
        c = i * 2
        pic_raw = p.eq(c + 1)("img").attr("data-xkrkllgl") or ""
        videos.append(
            {
                "vod_id": p.eq(c)("a").attr("href") or "",
                "vod_name": _safe_label(p.eq(c).text()),
                "vod_pic": pic_raw,
                "vod_remarks": _safe_label(x.text()),
            }
        )
    return videos


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def home(params, context):
    try:
        from_val = (context or {}).get("from", "web")
        await OmniBox.log("info", f"[home] from={from_val}")
        host = await _ensure_host()

        status, body, _ = await _http_get(host, timeout=10)
        if status != 200:
            return {"class": [], "list": []}

        data = _getpq(body)
        classes = []
        category_selectors = [
            ".category-list ul li",
            ".nav-menu li",
            ".menu li",
            "nav ul li",
        ]
        for selector in category_selectors:
            for k in data(selector).items():
                link = k("a")
                href = (link.attr("href") or "").strip()
                name = (link.text() or "").strip()
                if not href or href == "#" or not name:
                    continue
                classes.append({"type_name": name, "type_id": href})
            if classes:
                break

        if not classes:
            classes = [
                {"type_name": "最新", "type_id": "/latest/"},
                {"type_name": "热门", "type_id": "/hot/"},
            ]

        return {
            "class": classes,
            "list": _getlist(data("#index article a")),
        }
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {"class": [], "list": []}


async def category(params, context):
    try:
        host = await _ensure_host()
        tid = str((params or {}).get("categoryId") or "/")
        page = _to_int((params or {}).get("page"), 1) or 1
        await OmniBox.log("info", f"[category] categoryId={tid}, page={page}")

        if "@folder" in tid:
            folder_id = tid.replace("@folder", "")
            videos = await _getfod(folder_id)
            return {
                "list": videos,
                "page": page,
                "pagecount": 1,
                "limit": len(videos) or PAGE_SIZE,
                "total": len(videos),
            }

        base_url = f"{host}{tid}" if tid.startswith("/") else f"{host}/{tid}"
        base_url = base_url.rstrip("/")
        url = f"{base_url}/{page}/" if page > 1 else f"{base_url}/"

        status, body, _ = await _http_get(url, timeout=12)
        if status != 200:
            return {"list": [], "page": page, "pagecount": 1, "limit": PAGE_SIZE, "total": 0}

        data = _getpq(body)
        videos = _getlist(data("#archive article a, #index article a"), tid)

        pagecount = 1
        try:
            pagination_selectors = [".pagination", ".page-nav", ".pager", ".nav-links", ".pages"]
            for selector in pagination_selectors:
                pagination = data(selector)
                if pagination:
                    page_numbers = [
                        int(link.text().strip())
                        for link in pagination.find("a").items()
                        if link.text().strip().isdigit()
                    ]
                    if page_numbers:
                        pagecount = max(page_numbers)
                        break
            if pagecount == 1 and data('a:contains("下一页"), a:contains("Next")'):
                pagecount = page + 1
        except Exception:
            pagecount = page

        return {
            "list": videos,
            "page": page,
            "pagecount": max(1, pagecount),
            "limit": PAGE_SIZE,
            "total": max(len(videos), page * PAGE_SIZE),
        }
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_SIZE}


async def detail(params, context):
    try:
        host = await _ensure_host()
        req_id = str((params or {}).get("videoId") or "")
        if not req_id:
            return {"list": []}

        await OmniBox.log("info", f"[detail] videoId={req_id}")
        url = req_id if req_id.startswith("http") else f"{host}{req_id}"

        status, body, _ = await _http_get(url, timeout=12)
        if status != 200:
            return {"list": []}

        data = _getpq(body)
        vod = {
            "vod_id": req_id,
            "vod_name": _safe_label(data(".post-title").text() or "51吃瓜视频"),
            "vod_pic": "",
            "vod_content": "",
        }

        try:
            tags = []
            if data(".tags .keywords a"):
                for k in data(".tags .keywords a").items():
                    title = k.text().strip()
                    if title:
                        tags.append(title)
            vod["vod_content"] = " ".join(tags) if tags else (data(".post-title").text() or "")
        except Exception:
            vod["vod_content"] = data(".post-title").text() or ""

        episodes = []
        used_names = set()
        if data(".dplayer"):
            for c, k in enumerate(data(".dplayer").items(), start=1):
                config_attr = k.attr("data-config")
                if not config_attr:
                    continue
                try:
                    config = json.loads(config_attr)
                    video_url = (config.get("video") or {}).get("url", "")
                    if not video_url:
                        continue

                    ep_name = ""
                    try:
                        parent = k.parents().eq(0)
                        for _ in range(3):
                            if not parent:
                                break
                            heading = parent.find("h2, h3, h4").eq(0).text() or ""
                            heading = heading.strip()
                            if heading:
                                ep_name = heading
                                break
                            parent = parent.parents().eq(0)
                    except Exception:
                        ep_name = ""

                    base_name = ep_name if ep_name else f"视频{c}"
                    name = base_name
                    count = 2
                    while name in used_names:
                        name = f"{base_name} {count}"
                        count += 1
                    used_names.add(name)
                    episodes.append({"name": _safe_label(name), "playId": video_url})
                except Exception:
                    continue

        if not episodes:
            await OmniBox.log("warn", "[detail] 未找到有效视频源")
            return {"list": []}

        vod["vod_play_sources"] = [{"name": "51吃瓜", "episodes": episodes}]
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] 失败: {e}")
        return {"list": []}


async def search(params, context):
    try:
        host = await _ensure_host()
        keyword = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not keyword:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_SIZE}

        await OmniBox.log("info", f"[search] keyword={keyword}, page={page}")
        url = (
            f"{host}/search/{quote(keyword)}/{page}/"
            if page > 1
            else f"{host}/search/{quote(keyword)}/"
        )

        status, body, _ = await _http_get(url, timeout=12)
        if status != 200:
            return {"list": [], "page": page, "pagecount": 1, "limit": PAGE_SIZE, "total": 0}

        data = _getpq(body)
        videos = _getlist(data("#archive article a, #index article a"))

        pagecount = 1
        try:
            pagination_selectors = [".pagination", ".page-nav", ".pager", ".nav-links", ".pages"]
            for selector in pagination_selectors:
                pagination = data(selector)
                if pagination:
                    page_numbers = [
                        int(link.text().strip())
                        for link in pagination.find("a").items()
                        if link.text().strip().isdigit()
                    ]
                    if page_numbers:
                        pagecount = max(page_numbers)
                        break
        except Exception:
            pagecount = page

        return {
            "list": videos,
            "page": page,
            "pagecount": max(1, pagecount),
            "limit": PAGE_SIZE,
            "total": max(len(videos), page * PAGE_SIZE),
        }
    except Exception as e:
        await OmniBox.log("error", f"[search] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_SIZE}


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            raise ValueError("playId 不能为空")

        parse = 0 if _is_video_format(play_id) else 1
        await OmniBox.log("info", f"[play] playId={play_id[:100]}, parse={parse}")

        return {
            "urls": [{"name": "播放", "url": play_id}],
            "flag": flag,
            "header": dict(_headers) if _headers else {"User-Agent": UA},
            "parse": parse,
        }
    except Exception as e:
        await OmniBox.log("error", f"[play] 失败: {e}")
        return {
            "urls": [],
            "flag": (params or {}).get("flag", "play"),
            "header": {},
            "parse": 0,
        }


if __name__ == "__main__":
    run(
        {
            "home": home,
            "category": category,
            "detail": detail,
            "search": search,
            "play": play,
        }
    )
