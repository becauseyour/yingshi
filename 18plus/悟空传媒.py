# -*- coding: utf-8 -*-
# @name 悟空传媒
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/悟空传媒.py
# @description 悟空传媒（视频/小说/图片），优先视频直链 m3u8

import re
import json
from urllib.parse import quote

from spider_runner import OmniBox, run

HOST = "https://a4j665s.bingyu4.sbs"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": HOST + "/",
}

VIDEO_CATS = [
    {"type_id": "shipin/1", "type_name": "国产"},
    {"type_id": "shipin/6", "type_name": "自拍"},
    {"type_id": "shipin/7", "type_name": "乱伦"},
    {"type_id": "shipin/8", "type_name": "强奸"},
    {"type_id": "shipin/9", "type_name": "传媒"},
    {"type_id": "shipin/10", "type_name": "反差嫔"},
    {"type_id": "shipin/11", "type_name": "网爆门"},
    {"type_id": "shipin/12", "type_name": "偷拍"},
    {"type_id": "shipin/2", "type_name": "网红"},
    {"type_id": "shipin/3", "type_name": "萝莉"},
    {"type_id": "shipin/13", "type_name": "福利姬"},
    {"type_id": "shipin/14", "type_name": "吃瓜"},
]


async def _get(url, timeout=15):
    try:
        if not url.startswith("http"):
            url = HOST + url
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


def _img_url(url):
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return HOST + url if url.startswith("/") else HOST + "/" + url


def _parse_video_list(text):
    items = []
    cards = re.findall(r'<div class="card">(.*?)</div>\s*</div>', text, re.S)
    for card in cards:
        m = re.search(r'<a class="pic" href="([^"]+)" title="([^"]*)"[^>]*style="background-image:url\(([^)]+)\)"', card, re.S)
        if not m:
            continue
        href, title, pic = m.groups()
        mm = re.search(r"/shipinnr/(\d+)\.html", href)
        if not mm:
            continue
        vid = mm.group(1)
        items.append({"vod_id": "video#" + vid, "vod_name": title.strip(), "vod_pic": _img_url(pic.strip()), "vod_remarks": ""})
    return items


def extract_m3u8(html_text):
    m = re.search(r"(https?://[^\s\"'<>]+?\.(?:m3u8|mp4))", html_text)
    if m:
        return m.group(1).replace("\\/", "/")
    m = re.search(r"var\s+player_data\s*=\s*(\{.*?\});", html_text, re.S)
    if m:
        try:
            data = json.loads(m.group(1).replace("\\/", "/"))
            for k in ["url", "url_next", "link", "video"]:
                u = data.get(k, "")
                if u and (".m3u8" in u or ".mp4" in u):
                    return u.replace("\\/", "/")
        except Exception:
            pass
    return ""


async def home(params, context):
    text = await _get("/shipin/1.html")
    list_items = _parse_video_list(text)[:40] if text else []
    return {"class": VIDEO_CATS, "list": list_items, "filters": {}}


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
    if page == 1:
        url = f"/{tid}.html"
    else:
        url = f"/{tid}-{page}.html"
    text = await _get(url)
    items = _parse_video_list(text) if text else []
    pagecount = page + 1
    m = re.search(r"共\d+条，\d+/(\d+)页", text or "")
    if m:
        pagecount = int(m.group(1))
    return {"list": items, "page": page, "pagecount": pagecount, "limit": len(items), "total": page * max(1, len(items))}


async def detail(params, context):
    vid_full = str((params or {}).get("videoId") or (params or {}).get("id") or (params or {}).get("vod_id") or "").strip()
    if not vid_full or "#" not in vid_full:
        return {"list": []}
    prefix, num = vid_full.split("#", 1)
    if prefix != "video":
        return {"list": []}
    url = f"/shipinnr/{num}.html"
    text = await _get(url)
    title = num
    pic = ""
    play_url = ""
    if text:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.S)
        if m:
            title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', text)
        if m:
            pic = _img_url(m.group(1))
        play_url = extract_m3u8(text)
        if not play_url:
            play_links = re.findall(r'<a[^>]*href="(/shipinlay/\d+-\d+-\d+\.html)"[^>]*>([^<]+)</a>', text)
            if play_links:
                play_url = HOST + play_links[0][0]
    return {"list": [{"vod_id": vid_full, "vod_name": title, "vod_pic": pic, "vod_remarks": "", "vod_play_sources": [{"name": "播放", "episodes": [{"name": "正片", "playId": play_url or (HOST + url)}]}]}]}


async def play(params, context):
    play_id = str((params or {}).get("playId") or (params or {}).get("id") or (params or {}).get("url") or "").strip()
    if not play_id:
        return {"parse": 0, "url": ""}
    if any(x in play_id for x in [".m3u8", ".mp4"]):
        return {"parse": 0, "url": play_id.replace("\\/", "/"), "header": {"User-Agent": UA, "Referer": HOST + "/"}}
    if play_id.startswith("http"):
        text = await _get(play_id)
        url = extract_m3u8(text) if text else ""
        if url:
            return {"parse": 0, "url": url, "header": {"User-Agent": UA, "Referer": HOST + "/"}}
        return {"parse": 1, "url": play_id, "header": {"User-Agent": UA, "Referer": HOST + "/"}}
    return {"parse": 0, "url": play_id}


async def search(params, context):
    key = str((params or {}).get("wd") or (params or {}).get("key") or "").strip()
    page = 1
    try:
        page = max(1, int((params or {}).get("page") or 1))
    except Exception:
        page = 1
    if not key:
        return {"list": []}
    url = f"/vodsearch/-------------.html?wd={quote(key)}"
    if page > 1:
        url = f"/vodsearch/{quote(key)}-{page}.html"
    text = await _get(url)
    items = _parse_video_list(text) if text else []
    return {"list": items}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
