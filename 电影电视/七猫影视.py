# -*- coding: utf-8 -*-
# @name 七猫影视
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/电影电视/七猫影视.py
# @description 七猫影视（OmniBox）

import re
import json
from urllib.parse import quote
from spider_runner import OmniBox, run

HOST = "https://www.qmao.net"
UA = "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "动漫"},
    {"type_id": "4", "type_name": "短剧"},
]

async def _get(url):
    try:
        res = await OmniBox.request(url, {"method": "GET", "headers": {"User-Agent": UA, "Referer": HOST + "/"}, "timeout": 15})
        return res.get("body") or ""
    except Exception as e:
        await OmniBox.log("error", f"[七猫] get failed: {e}")
        return ""

def _clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

def _extract_list(html):
    videos, seen = [], set()
    for m in re.finditer(r'href="/voddetail/(\d+)\.html"', html or ""):
        vid = m.group(1)
        if vid in seen:
            continue
        seen.add(vid)
        snippet = html[m.start():m.start()+800]
        title = ""
        tm = re.search(r'(BrowseList|FeaturedList|MTagBookList)_bookName[^>]*>(.*?)</a>', snippet, re.S)
        if tm:
            title = _clean(tm.group(2))
        if not title:
            tm = re.search(r'title="([^"]*)"', snippet)
            title = _clean(tm.group(1)) if tm else ""
        pic = ""
        pm = re.search(r'src="([^"]*\.(?:jpg|webp)[^"]*)"', snippet)
        if pm:
            pic = pm.group(1)
            if not pic.startswith("http"):
                pic = HOST + pic
        note = ""
        nm = re.search(r'(BrowseList|FeaturedList)_(?:lastChapter|tagsBox)[^>]*>(.*?)</(?:a|div)', snippet, re.S)
        if nm:
            note = _clean(nm.group(2))
        if title:
            videos.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": note})
    return videos

async def home(params, context):
    try:
        html = await _get(HOST + "/")
        return {"class": CLASSES, "list": _extract_list(html)[:40], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": CLASSES, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or "1")
        page = int(p.get("page") or 1)
        url = f"{HOST}/vodtype/{tid}.html" if page == 1 else f"{HOST}/vodtype/{tid}-{page}.html"
        html = await _get(url)
        items = _extract_list(html)
        return {"list": items, "page": page, "pagecount": page + (1 if items else 0), "total": len(items)}
    except Exception as e:
        await OmniBox.log("error", f"[category] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def search(params, context):
    try:
        p = params or {}
        keyword = (p.get("keyword") or "").strip()
        if not keyword:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        url = f"{HOST}/vodsearch/-------------.html?wd={quote(keyword)}"
        html = await _get(url)
        return {"list": _extract_list(html), "page": 1, "pagecount": 1, "total": 0}
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or "").strip()
        if not vid:
            return {"list": []}
        play_html = await _get(f"{HOST}/vodplay/{vid}-1-1.html")
        detail_html = await _get(f"{HOST}/voddetail/{vid}.html")
        title = ""
        m = re.search(r'dramaDetail_bookName[^>]*>([^<]+)<', detail_html or "")
        if m:
            title = _clean(m.group(1))
        if not title:
            m = re.search(r'<title>([^<]+)', detail_html or "")
            title = _clean(re.sub(r"\s*[-\u2013\u2014].*$", "", m.group(1))) if m else vid
        pic = ""
        m = re.search(r'dramaDetail_bookCover[^>]*>\s*<img[^>]*src="([^"]*)"', detail_html or "")
        if m:
            pic = m.group(1)
            if not pic.startswith("http"):
                pic = HOST + pic
        eps = []
        for em in re.finditer(r'<a[^>]*class="CatalogList_linkBox"[^>]*href="(/vodplay/[^"]+)"', play_html or ""):
            href = em.group(1)
            snippet = play_html[em.start():em.start()+600]
            num = re.search(r'>\s*(?:<[^>]*>\s*)*(\d+)\s*</a>', snippet)
            name = f"第{num.group(1)}集" if num else "播放"
            eps.append({"name": name, "playId": HOST + href})
        if not eps:
            eps = [{"name": "播放", "playId": f"{HOST}/vodplay/{vid}-1-1.html"}]
        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_play_sources": [{"name": "七猫", "episodes": eps}]}]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] {e}")
        return {"list": []}

async def play(params, context):
    try:
        p = params or {}
        url = str(p.get("playId") or "").strip()
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        if not url:
            return {"urls": [], "parse": 0, "header": headers}
        if not url.startswith("http"):
            url = HOST + url
        if re.search(r"\.(m3u8|mp4)", url, re.I):
            return {"urls": [{"name": "播放", "url": url}], "parse": 0, "header": headers}
        html = await _get(url)
        m = re.search(r'var player_aaaa=(\{[^<]+\})', html or "")
        if m:
            try:
                pd = json.loads(m.group(1))
                real = pd.get("url") or ""
                if real:
                    return {"urls": [{"name": "播放", "url": real}], "parse": 0, "header": headers}
            except Exception:
                pass
        return {"urls": [{"name": "播放", "url": url}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
