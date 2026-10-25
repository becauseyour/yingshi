# -*- coding: utf-8 -*-
# @name 护士AV
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/护士AV.py
# @description 护士AV站源（OmniBox 适配版）：HTML 直出、player_aaaa 解析

import re
import json
from urllib.parse import quote, urljoin

from spider_runner import OmniBox, run

HOST = "https://vip.hushiav9.cc"
PREFIX = "/a"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

CLASSES = [
    {"type_id": "387", "type_name": "国产自拍"},
    {"type_id": "254", "type_name": "国产自拍2"},
    {"type_id": "255", "type_name": "熟女人妻"},
    {"type_id": "388", "type_name": "日本无码"},
    {"type_id": "365", "type_name": "高清无码"},
    {"type_id": "366", "type_name": "中文字幕"},
    {"type_id": "389", "type_name": "主播系列"},
    {"type_id": "363", "type_name": "主播网红"},
    {"type_id": "364", "type_name": "黑料网曝"},
    {"type_id": "258", "type_name": "美乳巨乳"},
    {"type_id": "391", "type_name": "欧美"},
    {"type_id": "264", "type_name": "欧美无码"},
    {"type_id": "369", "type_name": "高清有码"},
    {"type_id": "266", "type_name": "AV解说"},
    {"type_id": "128", "type_name": "国产主播"},
    {"type_id": "304", "type_name": "精品推荐"},
    {"type_id": "307", "type_name": "日本无码2"},
    {"type_id": "310", "type_name": "性感人妻"},
]


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _unescape(s):
    try:
        import html as H
        return H.unescape(s or "")
    except Exception:
        return s or ""


async def _get(path):
    url = path if path.startswith("http") else HOST + PREFIX + path
    res = await OmniBox.request(
        url,
        {
            "method": "GET",
            "headers": {
                "User-Agent": UA,
                "Referer": HOST + PREFIX + "/",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            "timeout": 15,
        },
    )
    body = res.get("body") or ""
    if body and "404 Not Found" in body[:200]:
        return ""
    return body


def _parse_list(html):
    videos, seen = [], set()
    for m in re.finditer(
        r'href="%s/index\.php/vod/detail/id/(\d+)[^"]*"[\s\S]{0,500}?data-original="([^"]*)"[\s\S]{0,200}?alt="([^"]*)"'
        % re.escape(PREFIX),
        html or "",
    ):
        vid, pic, name = m.group(1), m.group(2), _unescape(m.group(3)).strip()
        if len(name) < 2 or any(k in name for k in ("萝莉", "幼女")):
            continue
        if vid in seen:
            continue
        seen.add(vid)
        videos.append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": ""})
    if not videos:
        for m in re.finditer(
            r'href="%s/index\.php/vod/detail/id/(\d+)[^"]*"' % re.escape(PREFIX),
            html or "",
        ):
            vid = m.group(1)
            if vid in seen:
                continue
            chunk = (html or "")[m.start(): m.start() + 600]
            pic = ""
            pm = re.search(r'data-original="([^"]+)"', chunk)
            if pm:
                pic = pm.group(1)
            name = ""
            nm = re.search(r'class="vod-name"[^>]*>([\s\S]*?)</div>', chunk)
            if nm:
                name = _unescape(re.sub(r"<[^>]+>", "", nm.group(1))).strip()
            if not name:
                am = re.search(r'alt="([^"]+)"', chunk)
                if am:
                    name = _unescape(am.group(1)).strip()
            if len(name) < 2 or any(k in name for k in ("萝莉", "幼女")):
                continue
            seen.add(vid)
            videos.append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": ""})
    return videos


def _extract_player_url(html):
    m = re.search(r"player_aaaa\s*=\s*(\{.+?\})\s*</script>", html or "", re.S)
    if not m:
        return ""
    try:
        return (json.loads(m.group(1)).get("url") or "").strip()
    except Exception:
        u = re.search(r'"url"\s*:\s*"([^"]+)"', m.group(1))
        if u:
            return u.group(1).replace("\\/", "/")
    return ""


async def _resolve_m3u8(url):
    if not url or ".m3u8" not in url:
        return url
    try:
        res = await OmniBox.request(
            url,
            {"method": "GET", "headers": {"User-Agent": UA, "Referer": HOST + "/"}, "timeout": 15},
        )
        body = res.get("body") or ""
        if not body or ("#EXTINF" in body and "#EXT-X-STREAM-INF" not in body):
            return url
        for line in body.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and ".m3u8" in line:
                return line if line.startswith("http") else urljoin(url, line)
    except Exception:
        pass
    return url


async def home(params, context):
    try:
        await OmniBox.log("info", f"[home] from={(context or {}).get('from', 'web')}")
        html = await _get("/index.php/vod/type/id/387.html")
        return {"class": CLASSES, "list": _parse_list(html), "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "387")
        page = _to_int((params or {}).get("page"), 1) or 1
        await OmniBox.log("info", f"[category] categoryId={tid}, page={page}")
        path = (
            f"/index.php/vod/type/id/{tid}.html"
            if page <= 1
            else f"/index.php/vod/type/id/{tid}/page/{page}.html"
        )
        html = await _get(path)
        videos = _parse_list(html)
        pagecount = page
        pages = re.findall(r"type/id/%s/page/(\d+)" % re.escape(tid), html or "")
        if pages:
            pagecount = max(int(x) for x in pages if x.isdigit())
        elif len(videos) >= 10:
            pagecount = page + 1
        return {"list": videos, "page": page, "pagecount": pagecount, "limit": 24, "total": pagecount * 24}
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 24}


async def detail(params, context):
    try:
        vod_id = str((params or {}).get("videoId") or "")
        if not vod_id:
            return {"list": []}
        await OmniBox.log("info", f"[detail] videoId={vod_id}")
        html = await _get(f"/index.php/vod/detail/id/{vod_id}.html")
        name = ""
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html or "")
        if m:
            name = _unescape(m.group(1)).strip()
        if not name:
            m = re.search(r"<title>([^<]+)</title>", html or "")
            if m:
                name = _unescape(m.group(1)).split("在线")[0].split(" - ")[0].strip()
        pic = ""
        m = re.search(r'data-original="(https?://[^"]+)"', html or "")
        if m:
            pic = m.group(1)
        vod = {
            "vod_id": vod_id,
            "vod_name": name or f"视频{vod_id}",
            "vod_pic": pic,
            "vod_content": name,
            "vod_play_sources": [{"name": "线路1", "episodes": [{"name": "正片", "playId": vod_id}]}],
        }
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] 失败: {e}")
        return {"list": []}


async def search(params, context):
    try:
        key = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 24}
        await OmniBox.log("info", f"[search] keyword={key}")
        q = quote(key)
        path = (
            f"/index.php/vod/search.html?wd={q}"
            if page <= 1
            else f"/index.php/vod/search/page/{page}/wd/{q}.html"
        )
        html = await _get(path)
        videos = _parse_list(html)
        return {"list": videos, "page": page, "pagecount": 1, "limit": 24, "total": len(videos)}
    except Exception as e:
        await OmniBox.log("error", f"[search] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 24}


async def play(params, context):
    try:
        raw = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not raw:
            raise ValueError("playId 为空")
        await OmniBox.log("info", f"[play] playId={raw[:80]}")
        if raw.startswith("http"):
            url = await _resolve_m3u8(raw)
        else:
            html = await _get(f"/index.php/vod/play/id/{raw}/sid/1/nid/1.html")
            url = _extract_player_url(html)
            if url:
                url = await _resolve_m3u8(url)
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        parse = 0 if url and any(x in url.lower() for x in (".m3u8", ".mp4")) else 1
        return {
            "urls": [{"name": "播放", "url": url}] if url else [],
            "flag": flag,
            "header": headers,
            "parse": parse,
        }
    except Exception as e:
        await OmniBox.log("error", f"[play] 失败: {e}")
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
