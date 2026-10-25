# -*- coding: utf-8 -*-
# @name 九色精彩
# @version 2.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/九色精彩.py
# @description 九色/jiuse 站源（OmniBox 适配版 v2）：新站结构，HTML 直出 + mp4 直链

"""
九色精彩 — OmniBox 适配版 v2.0.0

站点已改版（原 /aa + player_aaaa 失效）。
新结构:
  列表: /videos、/videos/categories/{slug}、/videos/categories/{slug}/{page}
  详情: /videos/view/{id}/{slug}/  ->  <video data-src="...mp4">
  搜索: /videos/search?keywords=
主域: https://jiuse.vip （会 302 到子域）
"""

import re
from urllib.parse import quote, urljoin, urlparse

from spider_runner import OmniBox, run

HOST = "https://jiuse.vip"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

CLASSES = [
    {"type_id": "top-rated", "type_name": "热门推荐"},
    {"type_id": "chinese", "type_name": "国产"},
    {"type_id": "japan-korea", "type_name": "日韩"},
    {"type_id": "europe-america", "type_name": "欧美"},
    {"type_id": "unpixelated", "type_name": "无码"},
    {"type_id": "pixelated", "type_name": "有码"},
    {"type_id": "hd", "type_name": "高清AV"},
    {"type_id": "anime", "type_name": "动漫"},
    {"type_id": "fornication", "type_name": "乱伦"},
    {"type_id": "gangbang", "type_name": "群交"},
    {"type_id": "sm", "type_name": "SM专区"},
    {"type_id": "madou", "type_name": "麻豆传媒"},
    {"type_id": "tianmei", "type_name": "天美传媒"},
    {"type_id": "mitao", "type_name": "蜜桃传媒"},
    {"type_id": "guodong", "type_name": "果冻传媒"},
    {"type_id": "xingkong", "type_name": "星空传媒"},
    {"type_id": "jingdong", "type_name": "精东影业"},
    {"type_id": "swag", "type_name": "台湾SWAG"},
    {"type_id": "tuzi", "type_name": "兔子先生"},
    {"type_id": "huangjia", "type_name": "皇家华人"},
    {"type_id": "jijin", "type_name": "片商集锦"},
]

_host = HOST


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


async def _get(path, timeout=15):
    global _host
    url = path if path.startswith("http") else (_host.rstrip("/") + path)
    res = await OmniBox.request(
        url,
        {
            "method": "GET",
            "headers": {
                "User-Agent": UA,
                "Referer": _host.rstrip("/") + "/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            "timeout": timeout,
        },
    )
    body = res.get("body") or ""
    final = (res.get("url") or url).rstrip("/")
    if "jiuse" in final:
        try:
            p = urlparse(final)
            if p.scheme and p.netloc:
                _host = "%s://%s" % (p.scheme, p.netloc)
        except Exception:
            pass
    return body


def _abs(u):
    if not u:
        return ""
    u = u.replace("&amp;", "&").strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http"):
        return u
    return urljoin(_host.rstrip("/") + "/", u.lstrip("/"))


def _parse_list(html):
    videos, seen = [], set()
    blocks = re.findall(
        r'<div[^>]*class="[^"]*colVideoList[^"]*"[^>]*>([\s\S]*?)(?=<div[^>]*class="[^"]*colVideoList|$)',
        html or "",
    )
    if not blocks:
        blocks = re.findall(
            r'(href="/videos/view/\d+/[^"]+"[\s\S]{0,600}?</a>)',
            html or "",
        )

    for block in blocks:
        m = re.search(r'href="(/videos/view/(\d+)/[^"]+)"', block)
        if not m:
            continue
        href, vid = m.group(1), m.group(2)
        if vid in seen:
            continue
        seen.add(vid)

        title = ""
        tm = re.search(
            r'class="[^"]*title[^"]*"[^>]*href="[^"]*"[^>]*>([\s\S]*?)</a>',
            block,
        )
        if tm:
            title = _unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip()
        if not title:
            tm = re.search(r'href="/videos/view/\d+/[^"]+"[^>]*>([\s\S]*?)</a>', block)
            if tm:
                title = _unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip()
        if len(title) < 2:
            continue
        if any(k in title for k in ("注册", "送888", "PG电子", "开元棋牌", "澳门官方")):
            continue

        pic = ""
        pm = re.search(r"background-image:\s*url\(['\"]?([^'\")\s]+)['\"]?\)", block)
        if pm:
            pic = pm.group(1)
        if not pic:
            pm = re.search(r'(https?://[^"\'\s)]+\.(?:jpg|jpeg|png|webp))', block, re.I)
            if pm:
                pic = pm.group(1)

        remarks = ""
        rm = re.search(r'class="layer"[^>]*>([^<]+)', block)
        if rm:
            remarks = rm.group(1).strip()

        videos.append(
            {
                "vod_id": href,
                "vod_name": title,
                "vod_pic": _abs(pic),
                "vod_remarks": remarks,
            }
        )
    return videos


def _pagecount_from(html, current, base_slug):
    pages = [current]
    for m in re.finditer(
        r'href="[^"]*?/(?:categories/%s|%s)/(\d+)"' % (re.escape(base_slug), re.escape(base_slug)),
        html or "",
    ):
        if m.group(1).isdigit():
            pages.append(int(m.group(1)))
    for m in re.finditer(r'class="page-link"[^>]*>(\d+)<', html or ""):
        pages.append(int(m.group(1)))
    return max(pages) if pages else current


async def home(params, context):
    try:
        await OmniBox.log("info", f"[home] from={(context or {}).get('from', 'web')}")
        html = await _get("/videos")
        return {"class": CLASSES, "list": _parse_list(html), "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "top-rated").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        await OmniBox.log("info", f"[category] categoryId={tid}, page={page}")

        if tid == "top-rated":
            path = "/videos" if page <= 1 else f"/videos/top-rated/{page}"
        else:
            path = (
                f"/videos/categories/{tid}"
                if page <= 1
                else f"/videos/categories/{tid}/{page}"
            )

        html = await _get(path)
        videos = _parse_list(html)
        pagecount = _pagecount_from(html, page, tid)
        if pagecount <= page and len(videos) >= 20:
            pagecount = page + 1
        return {
            "list": videos,
            "page": page,
            "pagecount": max(pagecount, page),
            "limit": 24,
            "total": max(pagecount, page) * 24,
        }
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 24}


async def detail(params, context):
    try:
        vod_id = str((params or {}).get("videoId") or "").strip()
        if not vod_id:
            return {"list": []}
        await OmniBox.log("info", f"[detail] videoId={vod_id}")

        if vod_id.startswith("http"):
            path = vod_id
        elif vod_id.startswith("/"):
            path = vod_id
        elif vod_id.isdigit():
            path = f"/videos/view/{vod_id}/"
        else:
            path = "/" + vod_id.lstrip("/")

        html = await _get(path)
        if not html:
            return {"list": []}

        name = ""
        m = re.search(r"<title>([^<]+)</title>", html or "")
        if m:
            name = _unescape(m.group(1))
            for sep in ["-蝌蚪", "-九色", "|", "_"]:
                if sep in name:
                    name = name.split(sep)[0].strip()
        if not name:
            m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html or "")
            if m:
                name = _unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        name = name or vod_id

        pic = ""
        m = re.search(r'data-poster="([^"]+)"', html or "")
        if m:
            pic = m.group(1)
        if not pic:
            m = re.search(
                r"background-image:\s*url\(['\"]?([^'\")\s]+)['\"]?\)",
                html or "",
            )
            if m:
                pic = m.group(1)

        play = ""
        m = re.search(r'data-src="(https?://[^"]+)"', html or "")
        if m:
            play = m.group(1).replace("&amp;", "&")
        if not play:
            m = re.search(
                r'(https?://[^"\'\s<>]+\.(?:mp4|m3u8)[^"\'\s<>]*)',
                html or "",
                re.I,
            )
            if m:
                play = m.group(1).replace("&amp;", "&")

        vod = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": _abs(pic),
            "vod_content": name,
        }
        if play:
            vod["vod_play_sources"] = [
                {"name": "线路1", "episodes": [{"name": "正片", "playId": play}]}
            ]
        else:
            vod["vod_play_sources"] = [
                {"name": "线路1", "episodes": [{"name": "正片", "playId": path}]}
            ]
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
        await OmniBox.log("info", f"[search] keyword={key}, page={page}")
        q = quote(key)
        path = f"/videos/search?keywords={q}"
        if page > 1:
            path = f"/videos/search?keywords={q}&page={page}"
        html = await _get(path)
        videos = _parse_list(html)
        return {
            "list": videos,
            "page": page,
            "pagecount": page + 1 if len(videos) >= 20 else page,
            "limit": 24,
            "total": len(videos),
        }
    except Exception as e:
        await OmniBox.log("error", f"[search] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 24}


async def play(params, context):
    try:
        raw = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not raw:
            raise ValueError("playId 为空")
        await OmniBox.log("info", f"[play] playId={raw[:100]}")

        url = raw.replace("&amp;", "&")
        if any(x in url.lower() for x in (".mp4", ".m3u8", ".flv")):
            pass
        elif url.startswith("http") and "/videos/view/" in url:
            html = await _get(url)
            m = re.search(r'data-src="(https?://[^"]+)"', html or "")
            url = m.group(1).replace("&amp;", "&") if m else ""
        elif url.startswith("/"):
            html = await _get(url)
            m = re.search(r'data-src="(https?://[^"]+)"', html or "")
            url = m.group(1).replace("&amp;", "&") if m else ""
        else:
            html = await _get(f"/videos/view/{url}/")
            m = re.search(r'data-src="(https?://[^"]+)"', html or "")
            url = m.group(1).replace("&amp;", "&") if m else ""

        headers = {
            "User-Agent": UA,
            "Referer": _host.rstrip("/") + "/",
        }
        parse = 0 if url and any(x in url.lower() for x in (".m3u8", ".mp4")) else 1
        return {
            "urls": [{"name": "播放", "url": url}] if url else [],
            "flag": flag,
            "header": headers,
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
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
