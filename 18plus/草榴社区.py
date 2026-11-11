# -*- coding: utf-8 -*-
# @name 草榴社区
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/草榴社区.py
# @description 草榴社区（国产传媒/剧情/黑料等），支持视频与图文，直连 m3u8 优先

import re
import json
import html
from urllib.parse import quote, unquote

from spider_runner import OmniBox, run

HOST = "https://g3h4i5j6.caoliu28.cc"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": HOST + "/",
}

CLASSES = [
    {"type_id": "1", "type_name": "国产传媒"},
    {"type_id": "2", "type_name": "国产剧情"},
    {"type_id": "58", "type_name": "网曝黑料"},
    {"type_id": "3", "type_name": "特色仓库"},
    {"type_id": "69", "type_name": "精品资源"},
    {"type_id": "78", "type_name": "热播片库"},
    {"type_id": "92", "type_name": "原创资源"},
    {"type_id": "6", "type_name": "偷拍自拍"},
    {"type_id": "7", "type_name": "国产大制作"},
    {"type_id": "8", "type_name": "乱伦毁三观"},
    {"type_id": "9", "type_name": "主播女网红"},
    {"type_id": "10", "type_name": "黑料网曝"},
    {"type_id": "11", "type_name": "会所技师"},
    {"type_id": "12", "type_name": "制服诱惑"},
    {"type_id": "20", "type_name": "淫乱学生妹"},
    {"type_id": "5", "type_name": "激情图区"},
    {"type_id": "38", "type_name": "情色小说"},
]

ARTICLE_IDS = {
    "5", "38", "25", "26", "27", "28", "29", "30", "31", "32",
    "33", "34", "35", "36", "37", "39", "40", "41",
}


async def _get(url, timeout=18):
    try:
        if not url.startswith("http"):
            url = HOST + ("" if url.startswith("/") else "/") + url
        res = await OmniBox.request(
            url, {"method": "GET", "headers": HEADERS, "timeout": timeout}
        )
        body = res.get("body") or ""
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="ignore")
        status = int(res.get("statusCode") or 0)
        if status and status >= 400:
            return ""
        return str(body)
    except Exception as e:
        await OmniBox.log("error", "[request] %s %s" % (url, e))
        return ""


def _parse_list(text, is_article=False):
    items = []
    if not text:
        return items
    seen = set()

    if not is_article:
        pattern = re.compile(
            r'<dt class="preview-item">\s*'
            r'<a[^>]+href="/voddetail/(\d+)\.html"[^>]*>.*?'
            r'data-original="([^"]*)"[^>]*>.*?'
            r'</dt>\s*<dd>.*?<h3>(.*?)</h3>',
            re.S,
        )
        for m in pattern.finditer(text):
            vid, pic, title = m.groups()
            if vid in seen:
                continue
            seen.add(vid)
            title = html.unescape(title).strip()
            if pic and any(x in pic for x in ["loading", "blank", "logo", "icon", "load.png"]):
                pic = ""
            items.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})

    if is_article and not items:
        pattern_art = re.compile(
            r'<li><a[^>]+href="/artdetail-(\d+)\.html"[^>]*>.*?<h3>(.*?)</h3>.*?</a></li>',
            re.S,
        )
        for m in pattern_art.finditer(text):
            vid, title = m.groups()
            if vid in seen:
                continue
            seen.add(vid)
            items.append({"vod_id": "art_" + vid, "vod_name": html.unescape(title).strip(), "vod_pic": "", "vod_remarks": ""})

    if not items:
        detail_prefix = "artdetail" if is_article else "voddetail"
        pattern3 = re.compile(
            r'<a[^>]+href="/' + detail_prefix + r'/(\d+)\.html"[^>]*(?:title="([^"]*)")?[^>]*>'
            r'.*?<img[^>]*?(?:data-original|src|data-src)="([^"]*)"[^>]*>.*?</a>',
            re.S,
        )
        for m in pattern3.finditer(text):
            vid, title, pic = m.groups()
            if vid in seen:
                continue
            seen.add(vid)
            if not title:
                title = "未知标题" + vid
            items.append({
                "vod_id": ("art_" + vid) if is_article else vid,
                "vod_name": html.unescape(title).strip(),
                "vod_pic": pic if pic and "loading" not in pic else "",
                "vod_remarks": "",
            })

    return items


def extract_play_url(text):
    if not text:
        return ""
    for var_name in ["player_aaaa", "player", "mac_player", "player_data", "cms_player"]:
        m = re.search(rf"var\s+{var_name}\s*=\s*(\{{.*?\}})\s*</script>", text, re.S)
        if m:
            try:
                player = json.loads(m.group(1))
                raw = player.get("url", "")
                if raw and isinstance(raw, str):
                    decoded = raw.strip()
                    if re.match(r"^[A-Za-z0-9+/=]{20,}$", decoded):
                        try:
                            import base64
                            decoded = base64.b64decode(decoded).decode("utf-8")
                        except Exception:
                            pass
                    if "%" in decoded:
                        try:
                            decoded = unquote(decoded)
                        except Exception:
                            pass
                    if decoded.startswith("http"):
                        return decoded
            except Exception:
                continue
    m = re.search(r'["\'](https?://[^\s"<>]+?\.(?:m3u8|mp4|ts|flv))["\']', text)
    if m:
        return m.group(1)
    return ""


async def home(params, context):
    text = await _get(HOST + "/")
    list_items = _parse_list(text, is_article=False)[:30] if text else []
    return {"class": CLASSES, "list": list_items, "filters": {}}


async def category(params, context):
    p = params or {}
    tid = str(p.get("categoryId") or p.get("tid") or "").strip()
    page = 1
    try:
        page = max(1, int(p.get("page") or 1))
    except Exception:
        page = 1
    if not tid:
        return {"list": [], "page": 1, "pagecount": 0, "limit": 0, "total": 0}

    is_article = tid in ARTICLE_IDS
    if is_article:
        url = f"{HOST}/arttype/{tid}-{page}.html" if page > 1 else f"{HOST}/arttype/{tid}.html"
    else:
        url = f"{HOST}/vodtype/{tid}-{page}.html" if page > 1 else f"{HOST}/vodtype/{tid}.html"
    text = await _get(url)
    items = _parse_list(text, is_article=is_article) if text else []
    pagecount = page + 1 if items else page
    return {"list": items, "page": page, "pagecount": pagecount, "limit": len(items), "total": page * max(1, len(items))}


async def detail(params, context):
    vid = str((params or {}).get("videoId") or (params or {}).get("id") or (params or {}).get("vod_id") or "").strip()
    if not vid:
        return {"list": []}

    if vid.startswith("art_"):
        real = vid.replace("art_", "")
        url = f"{HOST}/artdetail-{real}.html"
        text = await _get(url)
        title = real
        if text:
            m = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.S)
            if m:
                title = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": "", "vod_remarks": "图文", "vod_play_sources": [{"name": "内容", "episodes": [{"name": "查看", "playId": url}]}]}]}

    url = f"{HOST}/voddetail/{vid}.html"
    text = await _get(url)
    title = vid
    pic = ""
    play_id = f"/vodplay/{vid}-1-1.html"
    if text:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.S)
        if m:
            title = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', text)
        if m:
            pic = m.group(1)
        eps = re.findall(r'<a[^>]+href="(/vodplay/[^"]+)"[^>]*>([^<]+)</a>', text)
        if eps:
            play_id = eps[0][0]

    return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": "", "vod_play_sources": [{"name": "正片", "episodes": [{"name": "播放", "playId": play_id}]}]}]}


async def play(params, context):
    play_id = str((params or {}).get("playId") or (params or {}).get("id") or (params or {}).get("url") or "").strip()
    if not play_id:
        return {"parse": 0, "url": ""}

    if any(x in play_id for x in [".m3u8", ".mp4", ".flv"]):
        return {"parse": 0, "url": play_id, "header": {"User-Agent": UA, "Referer": HOST + "/"}}

    if play_id.startswith("http") and "vodplay" not in play_id and "artdetail" not in play_id:
        return {"parse": 0, "url": play_id, "header": {"User-Agent": UA, "Referer": HOST + "/"}}

    url = play_id if play_id.startswith("http") else HOST + ("" if play_id.startswith("/") else "/") + play_id
    text = await _get(url)
    m3u8 = extract_play_url(text)
    if m3u8:
        return {"parse": 0, "url": m3u8, "header": {"User-Agent": UA, "Referer": HOST + "/"}}
    return {"parse": 1, "url": url, "header": {"User-Agent": UA, "Referer": HOST + "/"}}


async def search(params, context):
    key = str((params or {}).get("wd") or (params or {}).get("key") or "").strip()
    page = 1
    try:
        page = max(1, int((params or {}).get("page") or 1))
    except Exception:
        page = 1
    if not key:
        return {"list": []}
    if page == 1:
        url = f"{HOST}/vodsearch/-------------.html?wd={quote(key)}"
    else:
        url = f"{HOST}/vodsearch/{quote(key)}----------{page}---.html"
    text = await _get(url)
    items = _parse_list(text, is_article=False) if text else []
    return {"list": items}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
