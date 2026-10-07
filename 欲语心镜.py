# -*- coding: utf-8 -*-
# @name 欲语心镜
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/Silent1566/OmniBox-Spider/main/影视/采集/欲语心镜.py
# @indexs 1
# @description 欲女心经站源（OmniBox 适配版）：分类/搜索/详情/直链播放

"""
站点默认: https://rzj.ynxj9.work
原 T3 接口已统一为 OmniBox handler (params, context)
脱敏与未成年过滤逻辑保留精简版
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

CLASSICAL_MAP = {
    "成人": "风月", "色情": "风月", "情色": "春宫", "淫": "风月", "黄色": "春宫",
    "激情": "云雨", "做爱": "云雨", "性交": "交欢", "偷拍": "窥帘", "乱伦": "禁脔",
    "强奸": "强占", "无码": "素纱", "有码": "遮面", "熟女": "徐娘",
    "萝莉": "豆蔻", "幼女": "玉蕊", "少女": "碧玉", "国产": "华夏",
}
_MINOR_KEYWORDS = ("豆蔻", "玉蕊", "碧玉", "未成年", "teen", "loli", "schoolgirl")


def desensitize(text):
    if text is None:
        return ""
    result = str(text)
    for key in sorted(CLASSICAL_MAP.keys(), key=len, reverse=True):
        if key in result:
            result = result.replace(key, CLASSICAL_MAP[key])
    lower = result.lower()
    for kw in _MINOR_KEYWORDS:
        if kw.lower() in lower:
            return ""
    return result


def _is_minor(text):
    if not text:
        return False
    lower = str(text).lower()
    return any(kw.lower() in lower for kw in _MINOR_KEYWORDS)


def _sanitize_vod(vod):
    if not isinstance(vod, dict):
        return vod
    name = vod.get("vod_name", "")
    if _is_minor(name) or _is_minor(vod.get("vod_remarks", "")) or _is_minor(vod.get("vod_content", "")):
        return None
    vod["vod_name"] = desensitize(name)
    if vod.get("vod_remarks") is not None:
        vod["vod_remarks"] = desensitize(vod.get("vod_remarks", ""))
    if vod.get("vod_content") is not None:
        vod["vod_content"] = desensitize(vod.get("vod_content", ""))
    if not vod["vod_name"]:
        return None
    return vod


def _sanitize_list(vod_list):
    return [x for x in (vod_list or []) if (lambda v: v is not None)(_sanitize_vod(x) or None) or False]


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


_host = DEFAULT_HOST
_categories = []


async def _fetch(url, referer=None, timeout=15):
    res = await OmniBox.request(
        url,
        {
            "method": "GET",
            "headers": {
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept-Encoding": "gzip, deflate",
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
        r'<a[^>]*href="/vodtype/(\d+)\.html"[^>]*>\s*<span>([^<]+)</span>',
        html_text or "",
    ):
        tid, tname = m.group(1), m.group(2).strip()
        if tid in seen or not tname or _is_minor(tname):
            continue
        seen.add(tid)
        classes.append({"type_id": tid, "type_name": desensitize(tname)})
    return classes


def _parse_list(html_text):
    items, seen, ids = [], set(), []
    text = html_text or ""
    for m in re.finditer(r'href="/(\d+)\.html"', text):
        vid = m.group(1)
        if vid not in seen:
            seen.add(vid)
            ids.append(vid)
    bg_imgs = re.findall(r'background(?:-image)?:\s*url\(["\']?([^"\'\)]+)["\']?\)', text)
    titles = []
    for m in re.finditer(r'<a[^>]*href="/\d+\.html"[^>]*>([^<]{5,})</a>', text):
        t = m.group(1).strip()
        if t:
            titles.append(t)
    for i, vid in enumerate(ids):
        name = titles[i] if i < len(titles) else ""
        if not name:
            continue
        pic = bg_imgs[i] if i < len(bg_imgs) else ""
        items.append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": ""})
    return items


def _parse_pagecount(html_text, current, tid):
    pages = [current]
    pattern = r"/vodtype/" + re.escape(str(tid)) + r"-(?:(\d+))\.html"
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
        _categories = []


async def home(params, context):
    try:
        await OmniBox.log("info", f"[home] from={(context or {}).get('from', 'web')}")
        await _ensure_host()
        html = await _fetch(_host + "/ynxj/", referer=DEFAULT_HOST + "/")
        lst = []
        for item in _parse_list(html):
            cleaned = _sanitize_vod(item)
            if cleaned:
                lst.append(cleaned)
        return {
            "class": _categories or [{"type_id": "1", "type_name": "全部"}],
            "list": lst,
            "filters": {},
        }
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {"class": [], "list": [], "filters": {}}


async def category(params, context):
    try:
        await _ensure_host()
        tid = str((params or {}).get("categoryId") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not tid:
            return {"list": [], "page": page, "pagecount": page, "limit": PAGE_SIZE, "total": 0}
        await OmniBox.log("info", f"[category] categoryId={tid}, page={page}")
        url = (
            f"{_host}/vodtype/{tid}.html"
            if page == 1
            else f"{_host}/vodtype/{tid}-{page}.html"
        )
        html = await _fetch(url, referer=DEFAULT_HOST + "/")
        items = []
        for item in _parse_list(html):
            cleaned = _sanitize_vod(item)
            if cleaned:
                items.append(cleaned)
        pagecount = _parse_pagecount(html, page, tid)
        limit = len(items) or PAGE_SIZE
        return {
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": pagecount * limit,
            "list": items,
        }
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_SIZE}


async def detail(params, context):
    try:
        vid = str((params or {}).get("videoId") or "").strip()
        if not vid:
            return {"list": []}
        await OmniBox.log("info", f"[detail] videoId={vid}")
        html = await _fetch(f"{_host}/{vid}.html", referer=DEFAULT_HOST + "/")
        name = ""
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html or "")
        if m:
            name = m.group(1).strip()
        if not name:
            m = re.search(r"<title>([^<]+)</title>", html or "")
            if m:
                name = m.group(1).split("-")[0].strip()
        name = name or vid
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
        content = name
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": content,
        }
        if play_url:
            vod["vod_play_sources"] = [
                {"name": "欲语心镜", "episodes": [{"name": "正片", "playId": play_url}]}
            ]
        cleaned = _sanitize_vod(vod)
        return {"list": [cleaned] if cleaned else []}
    except Exception as e:
        await OmniBox.log("error", f"[detail] 失败: {e}")
        return {"list": []}


async def search(params, context):
    try:
        keyword = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not keyword:
            return {"list": [], "page": page, "pagecount": page, "limit": PAGE_SIZE, "total": 0}
        await OmniBox.log("info", f"[search] keyword={keyword}")
        # 站点搜索为 POST
        res = await OmniBox.request(
            _host + "/s/index.html",
            {
                "method": "POST",
                "headers": {
                    "User-Agent": UA,
                    "Referer": DEFAULT_HOST + "/",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                "body": f"wd={quote(keyword)}",
                "timeout": 15,
            },
        )
        html = res.get("body") or ""
        items = []
        for item in _parse_list(html):
            cleaned = _sanitize_vod(item)
            if cleaned:
                items.append(cleaned)
        return {
            "page": page,
            "pagecount": page,
            "limit": len(items) or PAGE_SIZE,
            "total": len(items),
            "list": items,
        }
    except Exception as e:
        await OmniBox.log("error", f"[search] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_SIZE}


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "")
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            raise ValueError("playId 为空")
        parse = 0 if any(x in play_id.lower() for x in (".m3u8", ".mp4", ".mkv", ".flv")) else 1
        await OmniBox.log("info", f"[play] playId={play_id[:80]}, parse={parse}")
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
        await OmniBox.log("error", f"[play] 失败: {e}")
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
