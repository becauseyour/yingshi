# -*- coding: utf-8 -*-
# @name 欲语心镜
# @version 1.1.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/欲语心镜.py
# @description 欲女心经站源（OmniBox v1.1）：分类/搜索/详情/rawUrl 直链

"""
站点: https://rzj.ynxj9.work
修复: 列表正则配对封面、详情 rawUrl、弱化过度过滤
"""

import re
from urllib.parse import quote

from spider_runner import OmniBox, run

DEFAULT_HOST = "https://rzj.ynxj9.work"
PAGE_SIZE = 20
UA = (
    "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

# 仅过滤明确未成年关键词，不再做文言替换导致误杀
_MINOR_KEYWORDS = ("幼女", "萝莉", "loli", "child", "underage", "小学生", "初中生")

_host = DEFAULT_HOST
_categories = []


def _is_minor(text):
    if not text:
        return False
    lower = str(text).lower()
    return any(kw.lower() in lower for kw in _MINOR_KEYWORDS)


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


async def _fetch(url, referer=None, timeout=15):
    res = await OmniBox.request(
        url,
        {
            "method": "GET",
            "headers": {
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": referer or (_host + "/"),
            },
            "timeout": timeout,
        },
    )
    if (res.get("statusCode") or 0) >= 400:
        return ""
    return res.get("body") or ""


def _parse_categories(html_text):
    classes, seen = [], set()
    for m in re.finditer(
        r'href="/vodtype/(\d+)\.html"[^>]*>\s*<span>([^<]+)</span>',
        html_text or "",
    ):
        tid, tname = m.group(1), m.group(2).strip()
        if tid in seen or not tname or _is_minor(tname):
            continue
        seen.add(tid)
        classes.append({"type_id": tid, "type_name": tname})
    if not classes:
        # 兜底静态分类
        for tid, name in [
            ("29", "国产视频"), ("30", "无码视频"), ("31", "有码视频"),
            ("32", "中文字幕"), ("33", "日韩精品"), ("34", "欧美精品"),
            ("21", "女神学生"), ("22", "美女直播"), ("23", "人妻系列"),
            ("25", "自拍偷拍"), ("35", "动漫精品"), ("36", "三级伦理"),
        ]:
            classes.append({"type_id": tid, "type_name": name})
    return classes


def _parse_list(html_text):
    items, seen = [], set()
    text = html_text or ""
    # 按出现顺序取唯一 id
    ids = []
    for m in re.finditer(r'href="/(\d+)\.html"', text):
        vid = m.group(1)
        if vid not in seen:
            seen.add(vid)
            ids.append(vid)

    # 封面：background-image
    bg_imgs = re.findall(
        r'background(?:-image)?:\s*url\(["\']?([^"\'\)]+)["\']?\)',
        text,
    )

    # 标题：带文字的 a 标签
    titles = []
    for m in re.finditer(r'<a[^>]*href="/\d+\.html"[^>]*>([^<]{4,})</a>', text):
        t = m.group(1).strip()
        if t and t not in ("详情", "播放", "更多"):
            titles.append(t)

    for i, vid in enumerate(ids):
        name = titles[i] if i < len(titles) else ""
        if not name or _is_minor(name):
            continue
        pic = bg_imgs[i] if i < len(bg_imgs) else ""
        items.append({
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": "",
        })
    return items


def _parse_pagecount(html_text, current, tid):
    pages = [current]
    pattern = r"/vodtype/" + re.escape(str(tid)) + r"-(\d+)\.html"
    for m in re.finditer(pattern, html_text or ""):
        pages.append(_to_int(m.group(1), current) or current)
    return max(pages)


async def _ensure_host():
    global _host, _categories
    if _categories:
        return
    try:
        html = await _fetch(_host + "/ynxj/", referer=DEFAULT_HOST + "/")
        _categories = _parse_categories(html)
    except Exception:
        _categories = _parse_categories("")


async def home(params, context):
    try:
        await OmniBox.log("info", "[home] from=%s" % (context or {}).get("from", "web"))
        await _ensure_host()
        html = await _fetch(_host + "/ynxj/", referer=DEFAULT_HOST + "/")
        lst = _parse_list(html)
        return {
            "class": _categories or [{"type_id": "29", "type_name": "国产视频"}],
            "list": lst,
            "filters": {},
        }
    except Exception as e:
        await OmniBox.log("error", "[home] 失败: %s" % e)
        return {"class": [], "list": [], "filters": {}}


async def category(params, context):
    try:
        await _ensure_host()
        tid = str((params or {}).get("categoryId") or "29").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        await OmniBox.log("info", "[category] id=%s page=%s" % (tid, page))
        url = (
            "%s/vodtype/%s.html" % (_host, tid)
            if page == 1
            else "%s/vodtype/%s-%s.html" % (_host, tid, page)
        )
        html = await _fetch(url, referer=DEFAULT_HOST + "/")
        items = _parse_list(html)
        pagecount = _parse_pagecount(html, page, tid)
        if pagecount <= page and len(items) >= 10:
            pagecount = page + 1
        return {
            "page": page,
            "pagecount": pagecount,
            "limit": PAGE_SIZE,
            "total": pagecount * PAGE_SIZE,
            "list": items,
        }
    except Exception as e:
        await OmniBox.log("error", "[category] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_SIZE}


async def detail(params, context):
    try:
        vid = str((params or {}).get("videoId") or "").strip()
        if not vid:
            return {"list": []}
        await OmniBox.log("info", "[detail] %s" % vid)
        html = await _fetch("%s/%s.html" % (_host, vid), referer=DEFAULT_HOST + "/")
        name = ""
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html or "")
        if m:
            name = m.group(1).strip()
        if not name:
            m = re.search(r"<title>([^<]+)</title>", html or "")
            if m:
                name = m.group(1).split("-")[0].strip()
        name = name or vid
        if _is_minor(name):
            return {"list": []}

        pic = ""
        m = re.search(r'background(?:-image)?:\s*url\(["\']?([^"\'\)]+)["\']?\)', html or "")
        if m:
            pic = m.group(1)

        play_url = ""
        m = re.search(r"const\s+rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html or "")
        if m:
            play_url = m.group(1)
        if not play_url:
            m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html or "")
            if m:
                play_url = m.group(1)

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": name,
        }
        if play_url:
            vod["vod_play_sources"] = [
                {"name": "欲语心镜", "episodes": [{"name": "正片", "playId": play_url}]}
            ]
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] 失败: %s" % e)
        return {"list": []}


async def search(params, context):
    try:
        keyword = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not keyword:
            return {"list": [], "page": page, "pagecount": page, "limit": PAGE_SIZE, "total": 0}
        await OmniBox.log("info", "[search] %s" % keyword)
        res = await OmniBox.request(
            _host + "/s/index.html",
            {
                "method": "POST",
                "headers": {
                    "User-Agent": UA,
                    "Referer": DEFAULT_HOST + "/",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                "body": "wd=%s" % quote(keyword),
                "timeout": 15,
            },
        )
        html = res.get("body") or ""
        items = _parse_list(html)
        return {
            "page": page,
            "pagecount": page,
            "limit": len(items) or PAGE_SIZE,
            "total": len(items),
            "list": items,
        }
    except Exception as e:
        await OmniBox.log("error", "[search] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_SIZE}


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "")
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            raise ValueError("playId 为空")
        parse = 0 if any(x in play_id.lower() for x in (".m3u8", ".mp4", ".mkv", ".flv")) else 1
        await OmniBox.log("info", "[play] parse=%s %s" % (parse, play_id[:80]))
        return {
            "urls": [{"name": "播放", "url": play_id}],
            "flag": flag,
            "header": {
                "User-Agent": UA,
                "Referer": DEFAULT_HOST + "/",
                "Origin": DEFAULT_HOST,
            },
            "parse": parse,
        }
    except Exception as e:
        await OmniBox.log("error", "[play] 失败: %s" % e)
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
