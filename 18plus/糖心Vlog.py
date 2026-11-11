# -*- coding: utf-8 -*-
# @name 糖心Vlog
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/%E7%B3%96%E5%BF%83Vlog.py
# @description 糖心Vlog tangxinvlog.app（OmniBox）

"""
糖心Vlog v1.0.0
站点: https://tangxinvlog.app
CDN: https://t.5gcdn.xyz/videos/{id}/index.m3u8
"""

import re
from urllib.parse import quote, unquote

from spider_runner import OmniBox, run

HOST = "https://tangxinvlog.app"
LANG = "/zh-tw"
CDN = "https://t.5gcdn.xyz/videos"
UA = (
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/139.0 Mobile Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": HOST + LANG + "/",
}


def _to_int(v, d=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return d


def _clean(s):
    s = re.sub(r"<!\[CDATA\[|\]\]>", "", s or "")
    return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", s)).replace("&amp;", "&").strip()


def _m(s, p):
    m = re.search(p, s or "", re.S | re.I)
    return m.group(1) if m else ""


async def _get(url):
    res = await OmniBox.request(
        url, {"method": "GET", "headers": HEADERS, "timeout": 12}
    )
    body = res.get("body") or ""
    if (res.get("statusCode") or 0) != 200:
        raise RuntimeError("HTTP %s" % res.get("statusCode"))
    return body


def _dedup(arr):
    out, seen = [], set()
    for x in arr:
        k = x.get("vod_id")
        if k and k not in seen:
            seen.add(k)
            out.append(x)
    return out


async def _classes():
    try:
        h = await _get(HOST + LANG + "/tag/")
    except Exception:
        h = ""
    arr = [
        {"type_id": "latest", "type_name": "最新"},
        {"type_id": "recommend", "type_name": "推荐"},
    ]
    for href, name in re.findall(
        r'<a href="/zh-tw/tag/([^"]+)"[^>]*>\s*<span class="name"[^>]*>(.*?)</span>',
        h,
        re.S | re.I,
    ):
        slug = unquote(href).strip("/")
        title = _clean(name)
        if slug and title and title not in [x["type_name"] for x in arr]:
            arr.append({"type_id": "tag/" + slug, "type_name": title})
    return arr


def _parse_list(html):
    arr = []
    for c in re.split(r'<article class="card"', html, flags=re.I)[1:]:
        href = _m(c, r'<a class="cover-link" href="([^"]+)"') or _m(
            c, r'href="([^"]*/v/\d+/[^"]*)"'
        )
        m = re.search(r"/v/(\d+)/", href or "")
        if not m:
            continue
        vid = m.group(1)
        name = _clean(
            _m(c, r'aria-label="([^"]+)"')
            or _m(c, r'<img[^>]+alt="([^"]+)"')
            or _m(c, r"<h3[^>]*>.*?<a[^>]*>(.*?)</a>")
        )
        pic = _m(c, r'<img[^>]+src="([^"]+)"') or ("%s/%s/cover.jpg" % (CDN, vid))
        mark = _clean(_m(c, r'<span class="duration"[^>]*>(.*?)</span>'))
        arr.append(
            {
                "vod_id": vid,
                "vod_name": name or vid,
                "vod_pic": pic,
                "vod_remarks": mark,
            }
        )
        if len(arr) >= 30:
            break
    return _dedup(arr)


async def _actors():
    h = await _get(HOST + LANG + "/a/")
    arr = []
    for href, name, num in re.findall(
        r'<a href="/zh-tw/a/([^"]+)"[^>]*>\s*<span class="name"[^>]*>(.*?)</span>\s*<span class="num"[^>]*>(.*?)</span>',
        h,
        re.S | re.I,
    ):
        slug = unquote(href).strip("/")
        title = _clean(name)
        if slug and title:
            arr.append(
                {
                    "vod_id": "actor/" + slug,
                    "vod_name": title,
                    "vod_pic": "",
                    "vod_remarks": _clean(num),
                }
            )
    return _dedup(arr)


async def _tags():
    h = await _get(HOST + LANG + "/tag/")
    arr = []
    for href, name, num in re.findall(
        r'<a href="/zh-tw/tag/([^"]+)"[^>]*>\s*<span class="name"[^>]*>(.*?)</span>\s*<span class="num"[^>]*>(.*?)</span>',
        h,
        re.S | re.I,
    ):
        slug = unquote(href).strip("/")
        title = _clean(name)
        if slug and title:
            arr.append(
                {
                    "vod_id": "tag/" + slug,
                    "vod_name": title,
                    "vod_pic": "",
                    "vod_remarks": _clean(num),
                }
            )
    return _dedup(arr)


async def home(params, context):
    try:
        classes = await _classes()
        return {"class": classes, "list": [], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[home] %s" % e)
        return {
            "class": [
                {"type_id": "latest", "type_name": "最新"},
                {"type_id": "recommend", "type_name": "推荐"},
            ],
            "list": [],
            "filters": {},
        }


async def category(params, context):
    try:
        p = params or {}
        tid = unquote(str(p.get("categoryId") or p.get("tid") or "latest")).strip()
        page = _to_int(p.get("page"), 1) or 1
        if tid in ("latest", "最新"):
            data = await _actors()
            return {"list": data, "page": 1, "pagecount": 1, "limit": len(data), "total": len(data)}
        if tid in ("recommend", "推荐"):
            data = await _tags()
            return {"list": data, "page": 1, "pagecount": 1, "limit": len(data), "total": len(data)}
        if tid.startswith("actor/"):
            slug = tid[6:]
            url = HOST + LANG + "/a/" + quote(slug, safe="") + ("/" if page <= 1 else "/%s" % page)
            data = _parse_list(await _get(url))
            return {"list": data, "page": page, "pagecount": 999 if data else page, "limit": 30, "total": 999999}
        if tid.startswith("tag/"):
            slug = tid[4:]
            url = HOST + LANG + "/tag/" + quote(slug, safe="") + ("/" if page <= 1 else "/%s" % page)
            data = _parse_list(await _get(url))
            return {"list": data, "page": page, "pagecount": 999 if data else page, "limit": 30, "total": 999999}
        url = HOST + LANG + "/tag/" + quote(tid, safe="") + ("/" if page <= 1 else "/%s" % page)
        data = _parse_list(await _get(url))
        return {"list": data, "page": page, "pagecount": 999 if data else page, "limit": 30, "total": 999999}
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 30, "total": 0}


async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or "").strip()
        if vid.startswith("actor/") or vid.startswith("tag/"):
            # treat as folder — return category redirect style single item list empty play
            return {
                "list": [
                    {
                        "vod_id": vid,
                        "vod_name": vid,
                        "vod_pic": "",
                        "vod_play_sources": [],
                    }
                ]
            }
        m = re.search(r"(\d+)", vid)
        vid = m.group(1) if m else vid
        h = await _get(HOST + LANG + "/v/%s/" % vid)
        name = _clean(_m(h, r"<h1[^>]*>(.*?)</h1>")) or vid
        pic = _m(h, r'<video[^>]+poster="([^"]+)"') or ("%s/%s/cover.jpg" % (CDN, vid))
        actor = _clean(_m(h, r'<a class="nickname"[^>]*>(.*?)</a>'))
        duration = _clean(_m(h, r'data-pagefind-meta="duration"[^>]*>(.*?)</span>'))
        return {
            "list": [
                {
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_actor": actor,
                    "vod_remarks": duration or "m3u8",
                    "vod_play_sources": [
                        {
                            "name": "直连",
                            "episodes": [{"name": "播放", "playId": vid}],
                        }
                    ],
                }
            ]
        }
    except Exception as e:
        await OmniBox.log("error", "[detail] %s" % e)
        return {"list": []}


async def search(params, context):
    try:
        p = params or {}
        key = str(p.get("keyword") or p.get("wd") or "").strip().lower()
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        h = await _get(HOST + LANG + "/rss.xml")
        arr = []
        for it in re.findall(r"<item>(.*?)</item>", h, re.S | re.I):
            title = _clean(_m(it, r"<title>(.*?)</title>"))
            link = _m(it, r"<link>(.*?)</link>")
            m = re.search(r"/v/(\d+)/", link or "")
            if not m:
                continue
            if key not in title.lower():
                continue
            vid = m.group(1)
            arr.append(
                {
                    "vod_id": vid,
                    "vod_name": title or vid,
                    "vod_pic": "%s/%s/cover.jpg" % (CDN, vid),
                    "vod_remarks": "m3u8",
                }
            )
            if len(arr) >= 50:
                break
        return {"list": _dedup(arr), "page": 1, "pagecount": 1, "total": len(arr)}
    except Exception as e:
        await OmniBox.log("error", "[search] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}


async def play(params, context):
    try:
        p = params or {}
        play_id = str(p.get("playId") or p.get("url") or "").strip()
        m = re.search(r"(\d+)", play_id)
        vid = m.group(1) if m else play_id
        url = "%s/%s/index.m3u8" % (CDN, vid)
        headers = {
            "User-Agent": UA,
            "Referer": HOST + LANG + "/v/%s/" % vid,
            "Origin": HOST,
        }
        return {"urls": [{"name": "播放", "url": url}], "parse": 0, "header": headers}
    except Exception as e:
        await OmniBox.log("error", "[play] %s" % e)
        return {"urls": [], "parse": 0, "header": {}}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
