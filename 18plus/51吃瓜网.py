# -*- coding: utf-8 -*-
# @name 51吃瓜网
# @version 1.1.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/51吃瓜网.py
# @description 51吃瓜站源（OmniBox v1.1）：主站 51cg1.com、正则解析、dplayer 直链

"""
51吃瓜网 — OmniBox 适配版 v1.1.0
- 动态域名多数失效，优先 https://51cg1.com
- 去掉 pyquery 依赖，纯正则
- 详情 data-config 单/双引号均可
"""

import json
import re
from urllib.parse import quote, urlparse

from spider_runner import OmniBox, run

PAGE_SIZE = 40
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
)
FALLBACK_HOST = "https://51cg1.com"
DYNAMIC_HOSTS = [
    "https://51cg1.com",
    "https://artist.vgwtswi.xyz",
    "https://ability.vgwtswi.xyz",
    "https://am.vgwtswi.xyz",
]

_host = ""
_headers = {}


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


def _abs_url(url, host=None):
    host = host or _host or FALLBACK_HOST
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    if url.startswith("/"):
        return host.rstrip("/") + url
    return host.rstrip("/") + "/" + url


async def _http_get(url, timeout=12):
    res = await OmniBox.request(
        url,
        {"method": "GET", "headers": _headers or {"User-Agent": UA}, "timeout": timeout},
    )
    return res.get("statusCode") or 0, res.get("body") or "", res.get("url") or url


async def _ensure_host():
    global _host, _headers
    if _host:
        return _host
    base_headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
    }
    for url in DYNAMIC_HOSTS:
        try:
            res = await OmniBox.request(
                url + "/",
                {"method": "GET", "headers": base_headers, "timeout": 8},
            )
            status = res.get("statusCode") or 0
            body = res.get("body") or ""
            final = (res.get("url") or url).rstrip("/")
            if status == 200 and len(body) > 3000 and (
                "<article" in body or "/archives/" in body or "loadBannerDirect" in body
            ):
                _host = final
                _headers = dict(base_headers)
                _headers.update({"Origin": _host, "Referer": _host + "/"})
                await OmniBox.log("info", "[init] 站点: %s size=%s" % (_host, len(body)))
                return _host
        except Exception as e:
            await OmniBox.log("warn", "[init] 跳过 %s: %s" % (url, e))
    _host = FALLBACK_HOST
    _headers = dict(base_headers)
    _headers.update({"Origin": _host, "Referer": _host + "/"})
    await OmniBox.log("info", "[init] 回退: %s" % _host)
    return _host


def _parse_categories(html):
    classes, seen = [], set()
    for href, name in re.findall(
        r'href="(/category/[^"]+/)"[^>]*>([^<]{2,30})</a>',
        html or "",
    ):
        name = name.strip()
        if not name or href in seen:
            continue
        seen.add(href)
        classes.append({"type_name": name, "type_id": href})
    if not classes:
        classes = [
            {"type_name": "今日吃瓜", "type_id": "/category/wpcz/"},
            {"type_name": "热门大瓜", "type_id": "/category/rdsj/"},
            {"type_name": "成人视频", "type_id": "/category/ysyl/"},
        ]
    return classes


def _parse_list(html, tid=""):
    videos, seen = [], set()
    is_folder = "/mrdg" in str(tid)
    articles = re.findall(r"<article[\s\S]*?</article>", html or "", re.I)
    chunks = articles if articles else [html or ""]
    for art in chunks:
        href_m = re.search(r'href="(/archives/\d+/[^"]*)"', art)
        if not href_m:
            href_m = re.search(r'href="(/archives/\d+/?)"', art)
        if not href_m:
            continue
        href = href_m.group(1)
        if href in seen:
            continue
        seen.add(href)

        title = ""
        for pat in [
            r"<h2[^>]*>([\s\S]*?)</h2>",
            r'class="[^"]*(?:entry-title|post-title)[^"]*"[^>]*>([\s\S]*?)</',
            r'title="([^"]+)"',
        ]:
            tm = re.search(pat, art, re.I)
            if tm:
                title = re.sub(r"<[^>]+>", "", tm.group(1)).strip()
                if title:
                    break
        if not title:
            continue

        pic = ""
        bm = re.search(r"loadBannerDirect\('([^']+)'", art)
        if bm:
            pic = bm.group(1)
        else:
            im = re.search(r'(https?://[^"\'\s)]+\.(?:jpg|jpeg|png|webp))', art, re.I)
            if im:
                pic = im.group(1)

        remarks = ""
        rm = re.search(r"(\d{4}[-年]\d{1,2}[-月]\d{1,2})", art)
        if rm:
            remarks = rm.group(1)

        item = {
            "vod_id": href + ("@folder" if is_folder else ""),
            "vod_name": _safe_label(title.replace("\n", " ")),
            "vod_pic": _abs_url(pic) if pic and not pic.startswith("http") else pic,
            "vod_remarks": _safe_label(remarks),
        }
        if is_folder:
            item["vod_tag"] = "folder"
        videos.append(item)
    return videos


def _extract_dplayer(html):
    episodes, used = [], set()
    configs = []
    configs.extend(re.findall(r"data-config\s*=\s*'([^']*)'", html or ""))
    configs.extend(re.findall(r'data-config\s*=\s*"([^"]*)"', html or ""))
    for i, raw in enumerate(configs, 1):
        try:
            cfg = json.loads(raw)
            video_url = ((cfg.get("video") or {}).get("url") or "").replace("\\/", "/")
            if not video_url:
                continue
            name = "视频%s" % i
            mt = re.search(r'data-video_title="([^"]+)"', html or "")
            if mt and mt.group(1).strip():
                name = mt.group(1).strip()
            base = name
            n = 2
            while name in used:
                name = "%s %s" % (base, n)
                n += 1
            used.add(name)
            episodes.append({"name": _safe_label(name), "playId": video_url})
        except Exception:
            continue
    if not episodes:
        for m in re.finditer(r'https?://[^"\'\s<>\\]+\.m3u8[^"\'\s<>\\]*', (html or "").replace("\\/", "/")):
            episodes.append({"name": "正片", "playId": m.group(0)})
            break
    return episodes


async def home(params, context):
    try:
        await OmniBox.log("info", "[home] from=%s" % (context or {}).get("from", "web"))
        host = await _ensure_host()
        status, body, _ = await _http_get(host + "/", timeout=12)
        if status != 200:
            return {"class": [], "list": []}
        return {
            "class": _parse_categories(body),
            "list": _parse_list(body),
            "filters": {},
        }
    except Exception as e:
        await OmniBox.log("error", "[home] 失败: %s" % e)
        return {"class": [], "list": []}


async def category(params, context):
    try:
        host = await _ensure_host()
        tid = str((params or {}).get("categoryId") or "/")
        page = _to_int((params or {}).get("page"), 1) or 1
        await OmniBox.log("info", "[category] %s page=%s" % (tid, page))

        if "@folder" in tid:
            return {"list": [], "page": 1, "pagecount": 1, "limit": PAGE_SIZE, "total": 0}

        path = tid if tid.startswith("/") else "/" + tid
        base = host.rstrip("/") + path.rstrip("/")
        url = base + "/" if page <= 1 else "%s/%s/" % (base, page)

        status, body, _ = await _http_get(url, timeout=12)
        if status != 200:
            return {"list": [], "page": page, "pagecount": 1, "limit": PAGE_SIZE, "total": 0}

        videos = _parse_list(body, tid)
        pagecount = page + 1 if len(videos) >= 10 else page
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": PAGE_SIZE,
            "total": page * PAGE_SIZE,
        }
    except Exception as e:
        await OmniBox.log("error", "[category] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_SIZE}


async def detail(params, context):
    try:
        host = await _ensure_host()
        req_id = str((params or {}).get("videoId") or "")
        if not req_id:
            return {"list": []}
        await OmniBox.log("info", "[detail] %s" % req_id)
        url = req_id if req_id.startswith("http") else _abs_url(req_id.replace("@folder", ""), host)

        status, body, _ = await _http_get(url, timeout=15)
        if status != 200 or not body:
            return {"list": []}

        title = ""
        for pat in [r'class="[^"]*post-title[^"]*"[^>]*>([\s\S]*?)</', r"<h1[^>]*>([\s\S]*?)</h1>", r"<title>([^<]+)</title>"]:
            m = re.search(pat, body, re.I)
            if m:
                title = re.sub(r"<[^>]+>", "", m.group(1)).split("-")[0].strip()
                if title:
                    break
        title = title or "51吃瓜"

        episodes = _extract_dplayer(body)
        vod = {
            "vod_id": req_id,
            "vod_name": _safe_label(title),
            "vod_pic": "",
            "vod_content": title,
        }
        if episodes:
            vod["vod_play_sources"] = [{"name": "51吃瓜", "episodes": episodes}]
        else:
            await OmniBox.log("warn", "[detail] 未找到视频源")
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] 失败: %s" % e)
        return {"list": []}


async def search(params, context):
    try:
        host = await _ensure_host()
        keyword = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not keyword:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_SIZE}
        await OmniBox.log("info", "[search] %s" % keyword)
        url = (
            "%s/search/%s/" % (host, quote(keyword))
            if page <= 1
            else "%s/search/%s/%s/" % (host, quote(keyword), page)
        )
        status, body, _ = await _http_get(url, timeout=12)
        if status != 200:
            return {"list": [], "page": page, "pagecount": 1, "limit": PAGE_SIZE, "total": 0}
        videos = _parse_list(body)
        return {
            "list": videos,
            "page": page,
            "pagecount": page + 1 if len(videos) >= 10 else page,
            "limit": PAGE_SIZE,
            "total": len(videos),
        }
    except Exception as e:
        await OmniBox.log("error", "[search] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_SIZE}


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            raise ValueError("playId 为空")
        parse = 0 if _is_video_format(play_id) else 1
        await OmniBox.log("info", "[play] parse=%s %s" % (parse, play_id[:100]))
        headers = dict(_headers) if _headers else {"User-Agent": UA}
        headers["Referer"] = (_host or FALLBACK_HOST) + "/"
        return {
            "urls": [{"name": "播放", "url": play_id}],
            "flag": flag,
            "header": headers,
            "parse": parse,
        }
    except Exception as e:
        await OmniBox.log("error", "[play] 失败: %s" % e)
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
