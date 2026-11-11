# -*- coding: utf-8 -*-
# @name 有声骚麦
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/%E6%9C%89%E5%A3%B0%E9%AA%9A%E9%BA%A6.py
# @description 有声骚麦 yssm5.xyz（OmniBox）

"""
有声骚麦 v1.0.0
站点: https://www.yssm5.xyz
"""

import re
from urllib.parse import quote, unquote, urljoin

from spider_runner import OmniBox, run

HOST = "https://www.yssm5.xyz"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Referer": HOST + "/", "Accept-Language": "zh-CN,zh;q=0.9"}

CLASSES = [
    {"type_id": "经典禁曲", "type_name": "经典禁曲"},
    {"type_id": "单部有声", "type_name": "单部有声"},
    {"type_id": "性爱偷录", "type_name": "性爱偷录"},
    {"type_id": "音乐改编", "type_name": "音乐改编"},
    {"type_id": "有声连载", "type_name": "有声连载"},
    {"type_id": "淫词骚麦", "type_name": "淫词骚麦"},
    {"type_id": "author_list", "type_name": "主播列表"},
    {"type_id": "toplist", "type_name": "热播榜"},
    {"type_id": "latest", "type_name": "最新更新"},
]


def _to_int(v, d=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return d


def _clean(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def _abs(url):
    if not url:
        return ""
    if url.startswith("http"):
        return url
    if url.startswith("//"):
        return "https:" + url
    return urljoin(HOST + "/", url)


async def _get(path):
    url = path if path.startswith("http") else HOST + path
    res = await OmniBox.request(
        url, {"method": "GET", "headers": HEADERS, "timeout": 15}
    )
    body = res.get("body") or ""
    if (res.get("statusCode") or 0) != 200:
        raise RuntimeError("HTTP %s" % res.get("statusCode"))
    return body


def _parse_books(html):
    books = []
    # card blocks
    for m in re.finditer(
        r'<a[^>]*class="[^"]*book-card[^"]*"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        html,
        re.S | re.I,
    ):
        href, block = m.group(1), m.group(2)
        vid_m = re.search(r"play\.php\?id=(\d+)", href)
        if not vid_m:
            continue
        title_m = re.search(r'class="book-title"[^>]*>(.*?)</', block, re.S)
        title = _clean(re.sub(r"<[^>]+>", "", title_m.group(1) if title_m else ""))
        author = ""
        meta_m = re.search(r'class="book-meta"[^>]*>(.*?)</', block, re.S)
        if meta_m:
            meta = _clean(re.sub(r"<[^>]+>", "", meta_m.group(1)))
            if "：" in meta:
                author = meta.split("：", 1)[-1].strip()
            elif ":" in meta:
                author = meta.split(":", 1)[-1].strip()
            else:
                author = meta
        read_m = re.search(r'class="read-link"[^>]*>(.*?)</', block, re.S)
        remark = _clean(re.sub(r"<[^>]+>", "", read_m.group(1) if read_m else ""))
        books.append(
            {
                "vod_id": vid_m.group(1),
                "vod_name": ("%s - %s" % (title, author)) if author else title,
                "vod_pic": "",
                "vod_remarks": ("播放:%s" % remark) if remark else "",
            }
        )
    if books:
        return books
    # update-item
    for m in re.finditer(r'class="update-item"[^>]*>(.*?)</div>\s*</div>', html, re.S | re.I):
        block = m.group(1)
        href_m = re.search(r'href="([^"]*play\.php\?id=\d+[^"]*)"', block)
        if not href_m:
            continue
        vid_m = re.search(r"id=(\d+)", href_m.group(1))
        if not vid_m:
            continue
        title_m = re.search(r'class="update-title"[^>]*>.*?<a[^>]*>(.*?)</a>', block, re.S)
        title = _clean(re.sub(r"<[^>]+>", "", title_m.group(1) if title_m else ""))
        books.append(
            {
                "vod_id": vid_m.group(1),
                "vod_name": title,
                "vod_pic": "",
                "vod_remarks": "",
            }
        )
    return books


def _parse_authors(html):
    authors = []
    for m in re.finditer(r'<a[^>]*class="[^"]*host-item[^"]*"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.S | re.I):
        href, block = m.group(1), m.group(2)
        name_m = re.search(r"name=([^&]+)", href)
        name = unquote(name_m.group(1)) if name_m else _clean(re.sub(r"<[^>]+>", "", block))
        count_m = re.search(r'class="host-books"[^>]*>(.*?)</', block, re.S)
        count = _clean(re.sub(r"<[^>]+>", "", count_m.group(1) if count_m else ""))
        if name:
            authors.append(
                {
                    "vod_id": "author:" + name,
                    "vod_name": name,
                    "vod_pic": "",
                    "vod_remarks": count or "",
                }
            )
    return authors


def _pagecount(html):
    nums = [int(x) for x in re.findall(r"[?&]page=(\d+)", html)]
    m = re.search(r"共\s*(\d+)\s*页", html)
    if m:
        return int(m.group(1))
    return max(nums) if nums else 1


def _extract_audio(html):
    m = re.search(r'class="audio-item"[^>]*data-src="([^"]+)"', html)
    if m:
        return _abs(m.group(1))
    m = re.search(r'<audio[^>]+src="([^"]+)"', html, re.I)
    if m:
        return _abs(m.group(1))
    m = re.search(r'<source[^>]+src="([^"]+)"', html, re.I)
    if m:
        return _abs(m.group(1))
    m = re.search(r'(https?://[^\s"\']+\.(?:mp3|m4a|aac)[^\s"\']*)', html)
    if m:
        return m.group(1)
    m = re.search(r'data-src="(/upload/audio/[^"]+)"', html)
    if m:
        return _abs(m.group(1))
    return ""


async def home(params, context):
    return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("tid") or "toplist")
        page = _to_int(p.get("page"), 1) or 1
        if tid == "author_list":
            html = await _get("/author.php?page=%s" % page)
            items = _parse_authors(html)
            pc = max(_pagecount(html), page)
            return {"list": items, "page": page, "pagecount": pc, "limit": len(items) or 20, "total": pc * 20}
        if tid == "toplist":
            path = "/toplist.php?page=%s" % page
        elif tid == "latest":
            path = "/latest.php?page=%s" % page
        else:
            path = "/cate_detail.php?cate=%s" % quote(tid)
            if page > 1:
                path += "&page=%s" % page
        html = await _get(path)
        books = _parse_books(html)
        pc = max(_pagecount(html), page)
        return {"list": books, "page": page, "pagecount": pc, "limit": len(books) or 20, "total": pc * 20}
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 20, "total": 0}


async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or "").strip()
        if not vid:
            return {"list": []}
        # author folder
        if vid.startswith("author:"):
            name = vid[7:]
            works = []
            for page in range(1, 30):
                html = await _get("/author_detail.php?name=%s&page=%s" % (quote(name), page))
                page_works = _parse_books(html)
                if not page_works:
                    break
                works.extend(page_works)
                if page >= _pagecount(html):
                    break
            eps = [{"name": w["vod_name"], "playId": w["vod_id"]} for w in works]
            return {
                "list": [
                    {
                        "vod_id": vid,
                        "vod_name": "主播 %s 的作品" % name,
                        "vod_pic": "",
                        "vod_play_sources": [{"name": "有声骚麦", "episodes": eps}] if eps else [],
                    }
                ]
            }
        html = await _get("/play.php?id=%s" % quote(vid))
        title_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        title = _clean(re.sub(r"<[^>]+>", "", title_m.group(1) if title_m else "")) or ("音频%s" % vid)
        audio = _extract_audio(html)
        sources = []
        if audio:
            sources = [{"name": "有声骚麦", "episodes": [{"name": "播放", "playId": audio}]}]
        else:
            sources = [{"name": "有声骚麦", "episodes": [{"name": "播放", "playId": vid}]}]
        return {
            "list": [
                {
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": "",
                    "vod_play_sources": sources,
                }
            ]
        }
    except Exception as e:
        await OmniBox.log("error", "[detail] %s" % e)
        return {"list": []}


async def search(params, context):
    try:
        p = params or {}
        key = str(p.get("keyword") or p.get("wd") or "").strip()
        page = _to_int(p.get("page"), 1) or 1
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        path = "/search.php?wd=%s" % quote(key)
        if page > 1:
            path += "&page=%s" % page
        html = await _get(path)
        books = _parse_books(html)
        pc = max(_pagecount(html), page)
        return {"list": books, "page": page, "pagecount": pc, "total": len(books)}
    except Exception as e:
        await OmniBox.log("error", "[search] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}


async def play(params, context):
    try:
        p = params or {}
        play_id = str(p.get("playId") or p.get("url") or "").strip()
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        if not play_id:
            return {"urls": [], "parse": 0, "header": headers}
        if re.search(r"\.(mp3|m4a|aac)(\?|$)", play_id, re.I) or play_id.startswith("http"):
            return {"urls": [{"name": "播放", "url": _abs(play_id)}], "parse": 0, "header": headers}
        if play_id.isdigit():
            html = await _get("/play.php?id=%s" % play_id)
            audio = _extract_audio(html)
            if audio:
                return {"urls": [{"name": "播放", "url": audio}], "parse": 0, "header": headers}
        return {"urls": [], "parse": 0, "header": headers}
    except Exception as e:
        await OmniBox.log("error", "[play] %s" % e)
        return {"urls": [], "parse": 0, "header": {}}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
