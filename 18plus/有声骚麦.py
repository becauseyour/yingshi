# -*- coding: utf-8 -*-
# @name 有声骚麦
# @version 1.1.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/%E6%9C%89%E5%A3%B0%E9%AA%9A%E9%BA%A6.py
# @description 有声骚麦 yssm5.xyz（OmniBox）；修复 book-card 属性顺序导致分类为空

"""
有声骚麦 v1.1.0
站点: https://www.yssm5.xyz

修复:
- 列表卡片实际为 href 在前、class 在后，原正则匹配不到 → 分类全空
- 分页文案为「当前第x/y页」
- 播放页音频多为 /upload/audio/*.mp3
"""

import re
from urllib.parse import quote, unquote, urljoin

from spider_runner import OmniBox, run

HOST = "https://www.yssm5.xyz"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Referer": HOST + "/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

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
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def _abs(url):
    if not url:
        return ""
    if url.startswith("http"):
        return url
    if url.startswith("//"):
        return "https:" + url
    return urljoin(HOST + "/", url)


async def _get(path):
    url = path if str(path).startswith("http") else HOST + path
    res = await OmniBox.request(url, {"method": "GET", "headers": HEADERS, "timeout": 15})
    status = int(res.get("statusCode") or 0)
    body = str(res.get("body") or "")
    if status and (status < 200 or status >= 400):
        raise RuntimeError("HTTP %s @ %s" % (status, url))
    return body


def _pagecount(html):
    # 「当前第1/68页」或「共 68 页」
    m = re.search(r"当前第\s*\d+\s*/\s*(\d+)\s*页", html or "")
    if m:
        return max(1, int(m.group(1)))
    m = re.search(r"共\s*(\d+)\s*页", html or "")
    if m:
        return max(1, int(m.group(1)))
    nums = [int(x) for x in re.findall(r"[?&]page=(\d+)", html or "")]
    return max(nums) if nums else 1


def _parse_books(html):
    """解析作品列表。站点卡片为 <a href="..." class="book-card">。"""
    books = []
    seen = set()

    # 1) book-card：href/class 任意顺序
    for m in re.finditer(
        r'<a\b([^>]*\bclass=["\'][^"\']*book-card[^"\']*["\'][^>]*)>(.*?)</a>',
        html or "",
        re.S | re.I,
    ):
        attrs, block = m.group(1), m.group(2)
        href_m = re.search(r'href=["\']([^"\']+)["\']', attrs, re.I)
        if not href_m:
            continue
        href = href_m.group(1)
        vid_m = re.search(r"play\.php\?id=(\d+)", href)
        if not vid_m:
            continue
        vid = vid_m.group(1)
        if vid in seen:
            continue
        title_m = re.search(
            r'class=["\'][^"\']*book-title[^"\']*["\'][^>]*>(.*?)</(?:h\d|div|span|p|a)',
            block,
            re.S | re.I,
        )
        if not title_m:
            title_m = re.search(r"<h3[^>]*>(.*?)</h3>", block, re.S | re.I)
        title = _clean(title_m.group(1) if title_m else "")
        if not title:
            continue
        author = ""
        meta_m = re.search(
            r'class=["\'][^"\']*book-meta[^"\']*["\'][^>]*>(.*?)</(?:div|span|p)',
            block,
            re.S | re.I,
        )
        if meta_m:
            meta = _clean(meta_m.group(1))
            for sep in ("：", ":"):
                if sep in meta:
                    author = meta.split(sep, 1)[-1].strip()
                    break
            if not author:
                author = meta
        remark = ""
        read_m = re.search(
            r'class=["\'][^"\']*read-link[^"\']*["\'][^>]*>(.*?)</',
            block,
            re.S | re.I,
        )
        if read_m:
            remark = _clean(read_m.group(1))
        seen.add(vid)
        books.append(
            {
                "vod_id": vid,
                "vod_name": ("%s - %s" % (title, author)) if author else title,
                "vod_pic": "",
                "vod_remarks": ("播放:%s" % remark) if remark else "",
            }
        )

    if books:
        return books

    # 2) update-item（热播榜 / 最新）
    for m in re.finditer(
        r'class=["\'][^"\']*update-item[^"\']*["\'][^>]*>(.*?)</div>\s*</div>',
        html or "",
        re.S | re.I,
    ):
        block = m.group(1)
        href_m = re.search(r'href=["\']([^"\']*play\.php\?id=\d+[^"\']*)["\']', block)
        if not href_m:
            continue
        vid_m = re.search(r"id=(\d+)", href_m.group(1))
        if not vid_m:
            continue
        vid = vid_m.group(1)
        if vid in seen:
            continue
        title_m = re.search(
            r'class=["\'][^"\']*update-title[^"\']*["\'][^>]*>.*?<a[^>]*>(.*?)</a>',
            block,
            re.S | re.I,
        )
        if not title_m:
            title_m = re.search(r"<h3[^>]*>.*?<a[^>]*>(.*?)</a>", block, re.S | re.I)
        if not title_m:
            title_m = re.search(r"<h3[^>]*>(.*?)</h3>", block, re.S | re.I)
        title = _clean(title_m.group(1) if title_m else "")
        if not title:
            # 退回 a 文本
            am = re.search(r'href=["\'][^"\']*play\.php\?id=' + vid + r'[^"\']*["\'][^>]*>(.*?)</a>', block, re.S)
            title = _clean(am.group(1) if am else "") or ("作品%s" % vid)
        seen.add(vid)
        books.append({"vod_id": vid, "vod_name": title, "vod_pic": "", "vod_remarks": ""})

    if books:
        return books

    # 3) 兜底：任意 play.php?id=
    for href, title in re.findall(
        r'href=["\']([^"\']*play\.php\?id=(\d+)[^"\']*)["\'][^>]*>(.*?)</a>',
        html or "",
        re.S | re.I,
    ):
        # findall groups: full href isn't captured that way - fix
        pass
    for m in re.finditer(
        r'href=["\']([^"\']*play\.php\?id=(\d+)[^"\']*)["\'][^>]*>(.*?)</a>',
        html or "",
        re.S | re.I,
    ):
        vid = m.group(2)
        if vid in seen:
            continue
        title = _clean(m.group(3))
        if not title or len(title) < 2:
            continue
        if any(x in title for x in ("主播", "榜单", "最新", "分类")):
            continue
        seen.add(vid)
        books.append({"vod_id": vid, "vod_name": title, "vod_pic": "", "vod_remarks": ""})

    return books


def _parse_authors(html):
    authors = []
    seen = set()
    for m in re.finditer(
        r'<a\b([^>]*\bclass=["\'][^"\']*host-item[^"\']*["\'][^>]*)>(.*?)</a>',
        html or "",
        re.S | re.I,
    ):
        attrs, block = m.group(1), m.group(2)
        href_m = re.search(r'href=["\']([^"\']+)["\']', attrs, re.I)
        if not href_m:
            continue
        href = href_m.group(1)
        name_m = re.search(r"name=([^&\"']+)", href)
        if name_m:
            name = unquote(name_m.group(1))
        else:
            name = _clean(block)
        if not name or name in seen:
            continue
        seen.add(name)
        authors.append(
            {
                "vod_id": "author:" + name,
                "vod_name": name,
                "vod_pic": "",
                "vod_remarks": "主播",
            }
        )
    if authors:
        return authors
    # 兜底 author_detail 链接
    for m in re.finditer(
        r'href=["\']([^"\']*author_detail\.php\?name=([^"\'&]+)[^"\']*)["\'][^>]*>(.*?)</a>',
        html or "",
        re.S | re.I,
    ):
        name = unquote(m.group(2))
        if not name or name in seen:
            continue
        seen.add(name)
        title = _clean(m.group(3)) or name
        authors.append(
            {"vod_id": "author:" + name, "vod_name": title, "vod_pic": "", "vod_remarks": "主播"}
        )
    return authors


def _extract_audio(html):
    patterns = [
        r'class=["\'][^"\']*audio-item[^"\']*["\'][^>]*data-src=["\']([^"\']+)',
        r'data-src=["\'](/upload/audio/[^"\']+)',
        r'<audio[^>]+src=["\']([^"\']+)',
        r'<source[^>]+src=["\']([^"\']+)',
        r'src=["\']([^"\']+\.(?:mp3|m4a|aac)[^"\']*)',
        r'(https?://[^\s"\']+\.(?:mp3|m4a|aac)[^\s"\']*)',
        r'["\'](/upload/audio/[^"\']+\.(?:mp3|m4a|aac)[^"\']*)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html or "", re.I)
        if m:
            return _abs(m.group(1))
    return ""


async def home(params, context):
    try:
        html = await _get("/latest.php")
        items = _parse_books(html)[:24]
        if not items:
            html = await _get("/")
            items = _parse_books(html)[:24]
        await OmniBox.log("info", "[有声骚麦][home] list=%s" % len(items))
        return {"class": CLASSES, "list": items, "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[有声骚麦][home] %s" % e)
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("tid") or p.get("type_id") or "latest")
        page = _to_int(p.get("page") or p.get("pg"), 1) or 1

        if tid == "author_list":
            path = "/author.php"
            if page > 1:
                path += "?page=%s" % page
            html = await _get(path)
            items = _parse_authors(html)
            pc = max(_pagecount(html), page)
            if len(items) >= 20:
                pc = max(pc, page + 1)
            await OmniBox.log("info", "[有声骚麦][category] authors=%s" % len(items))
            return {
                "list": items,
                "page": page,
                "pagecount": pc,
                "limit": len(items) or 20,
                "total": pc * max(1, len(items)),
            }

        if tid == "toplist":
            path = "/toplist.php"
            if page > 1:
                path += "?page=%s" % page
        elif tid == "latest":
            path = "/latest.php"
            if page > 1:
                path += "?page=%s" % page
        else:
            path = "/cate_detail.php?cate=%s" % quote(tid)
            if page > 1:
                path += "&page=%s" % page

        html = await _get(path)
        books = _parse_books(html)
        pc = max(_pagecount(html), page)
        if len(books) >= 18:
            pc = max(pc, page + 1)
        await OmniBox.log(
            "info", "[有声骚麦][category] tid=%s page=%s list=%s" % (tid, page, len(books))
        )
        return {
            "list": books,
            "page": page,
            "pagecount": pc,
            "limit": len(books) or 20,
            "total": pc * max(1, len(books)),
        }
    except Exception as e:
        await OmniBox.log("error", "[有声骚麦][category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 20, "total": 0}


async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or p.get("vod_id") or "").strip()
        if not vid:
            return {"list": []}

        # 主播合集
        if vid.startswith("author:"):
            name = vid[7:]
            works = []
            for page in range(1, 40):
                html = await _get(
                    "/author_detail.php?name=%s&page=%s" % (quote(name), page)
                )
                page_works = _parse_books(html)
                if not page_works:
                    break
                works.extend(page_works)
                if page >= _pagecount(html):
                    break
            # 去重
            seen, uniq = set(), []
            for w in works:
                if w["vod_id"] in seen:
                    continue
                seen.add(w["vod_id"])
                uniq.append(w)
            eps = [{"name": w["vod_name"], "playId": w["vod_id"]} for w in uniq]
            return {
                "list": [
                    {
                        "vod_id": vid,
                        "vod_name": "主播 %s 的作品" % name,
                        "vod_pic": "",
                        "vod_play_sources": (
                            [{"name": "有声骚麦", "episodes": eps}] if eps else []
                        ),
                    }
                ]
            }

        html = await _get("/play.php?id=%s" % quote(vid))
        title_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        title = _clean(title_m.group(1) if title_m else "") or ("音频%s" % vid)
        audio = _extract_audio(html)
        if audio:
            sources = [
                {
                    "name": "有声骚麦",
                    "episodes": [{"name": "播放", "playId": audio}],
                }
            ]
        else:
            sources = [
                {
                    "name": "有声骚麦",
                    "episodes": [{"name": "播放", "playId": vid}],
                }
            ]
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
        await OmniBox.log("error", "[有声骚麦][detail] %s" % e)
        return {"list": []}


async def search(params, context):
    try:
        p = params or {}
        key = str(p.get("keyword") or p.get("wd") or "").strip()
        page = _to_int(p.get("page") or p.get("pg"), 1) or 1
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        path = "/search.php?wd=%s" % quote(key)
        if page > 1:
            path += "&page=%s" % page
        html = await _get(path)
        books = _parse_books(html)
        pc = max(_pagecount(html), page)
        if len(books) >= 18:
            pc = max(pc, page + 1)
        await OmniBox.log("info", "[有声骚麦][search] kw=%s list=%s" % (key, len(books)))
        return {"list": books, "page": page, "pagecount": pc, "total": len(books)}
    except Exception as e:
        await OmniBox.log("error", "[有声骚麦][search] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}


async def play(params, context):
    try:
        p = params or {}
        play_id = str(p.get("playId") or p.get("url") or p.get("id") or "").strip()
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        if not play_id:
            return {"urls": [], "parse": 0, "header": headers}
        # 已是直链
        if re.search(r"\.(mp3|m4a|aac)(\?|$)", play_id, re.I) or (
            play_id.startswith("http") and "/upload/audio/" in play_id
        ):
            return {
                "urls": [{"name": "播放", "url": _abs(play_id)}],
                "parse": 0,
                "header": headers,
            }
        if play_id.startswith("http") and re.search(r"\.(mp3|m4a|aac)", play_id, re.I):
            return {
                "urls": [{"name": "播放", "url": play_id}],
                "parse": 0,
                "header": headers,
            }
        # 数字 id → 拉播放页
        if play_id.isdigit():
            html = await _get("/play.php?id=%s" % play_id)
            audio = _extract_audio(html)
            if audio:
                return {
                    "urls": [{"name": "播放", "url": audio}],
                    "parse": 0,
                    "header": headers,
                }
        return {"urls": [], "parse": 0, "header": headers}
    except Exception as e:
        await OmniBox.log("error", "[有声骚麦][play] %s" % e)
        return {"urls": [], "parse": 0, "header": {}}


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
