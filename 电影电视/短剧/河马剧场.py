# -*- coding: utf-8 -*-
# @name 河马剧场
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/电影电视/短剧/河马剧场.py
# @description 河马剧场短剧（OmniBox）

import re
import json
from urllib.parse import quote
from spider_runner import OmniBox, run

HOST = "https://www.kuaikaw.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

CLASSES = [
    {"type_id": "462", "type_name": "甜宠"},
    {"type_id": "1102", "type_name": "古装仙侠"},
    {"type_id": "1145", "type_name": "现代言情"},
    {"type_id": "1170", "type_name": "青春"},
    {"type_id": "585", "type_name": "豪门恩怨"},
    {"type_id": "417-464", "type_name": "逆袭"},
    {"type_id": "439-465", "type_name": "重生"},
    {"type_id": "1159", "type_name": "系统"},
    {"type_id": "1147", "type_name": "总裁"},
    {"type_id": "943", "type_name": "职场商战"},
]

async def _get(url):
    try:
        res = await OmniBox.request(url, {"method": "GET", "headers": {"User-Agent": UA, "Referer": HOST + "/"}, "timeout": 15})
        return res.get("body") or ""
    except Exception as e:
        await OmniBox.log("error", f"[河马] get failed: {e}")
        return ""

def _next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html or "", re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {}

def _cards(books):
    out = []
    for b in books or []:
        if not isinstance(b, dict) or not b.get("bookId"):
            continue
        out.append({"vod_id": str(b["bookId"]), "vod_name": str(b.get("bookName") or b.get("title") or ""), "vod_pic": str(b.get("coverWap") or ""), "vod_remarks": f"{b.get('statusDesc','')} {b.get('totalChapterNum','')}集".strip()})
    return out

async def home(params, context):
    try:
        html = await _get(HOST + "/")
        data = _next_data(html)
        props = data.get("props", {}).get("pageProps", {})
        items = []
        for banner in props.get("bannerList") or []:
            if banner.get("bookId"):
                items.append({"vod_id": str(banner["bookId"]), "vod_name": str(banner.get("bookName") or ""), "vod_pic": str(banner.get("coverWap") or ""), "vod_remarks": f"{banner.get('statusDesc','')} {banner.get('totalChapterNum','')}集".strip()})
        for col in props.get("seoColumnVos") or []:
            items.extend(_cards(col.get("bookInfos")))
        seen, uniq = set(), []
        for it in items:
            if it["vod_id"] not in seen:
                seen.add(it["vod_id"])
                uniq.append(it)
        return {"class": CLASSES, "list": uniq[:40], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": CLASSES, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or "462")
        page = int(p.get("page") or 1)
        url = f"{HOST}/browse/{tid}/{page}"
        html = await _get(url)
        data = _next_data(html)
        props = data.get("props", {}).get("pageProps", {})
        items = _cards(props.get("bookList"))
        pc = int(props.get("pages") or page)
        return {"list": items, "page": page, "pagecount": pc, "total": len(items) * pc}
    except Exception as e:
        await OmniBox.log("error", f"[category] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def search(params, context):
    try:
        p = params or {}
        keyword = (p.get("keyword") or "").strip()
        page = int(p.get("page") or 1)
        if not keyword:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        url = f"{HOST}/search?searchValue={quote(keyword)}&page={page}"
        html = await _get(url)
        data = _next_data(html)
        props = data.get("props", {}).get("pageProps", {})
        items = _cards(props.get("bookList"))
        return {"list": items, "page": page, "pagecount": int(props.get("pages") or 1), "total": len(items)}
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or "").strip()
        if not vid:
            return {"list": []}
        if vid.startswith("/drama/"):
            vid = vid.split("/")[-1]
        url = f"{HOST}/drama/{vid}"
        html = await _get(url)
        data = _next_data(html)
        props = data.get("props", {}).get("pageProps", {})
        book = props.get("bookInfoVo") or {}
        chapters = props.get("chapterList") or []
        eps = []
        for ch in chapters:
            cid = ch.get("chapterId")
            name = ch.get("chapterName") or "播放"
            vo = ch.get("chapterVideoVo") or {}
            direct = vo.get("mp4") or vo.get("mp4720p") or vo.get("vodMp4Url")
            if direct and re.search(r"\.(mp4|m3u8)", str(direct), re.I):
                eps.append({"name": name, "playId": direct})
            else:
                eps.append({"name": name, "playId": f"{vid}+{cid}"})
        if not eps:
            eps = [{"name": "播放", "playId": vid}]
        return {"list": [{"vod_id": vid, "vod_name": str(book.get("title") or book.get("bookName") or vid), "vod_pic": str(book.get("coverWap") or ""), "vod_remarks": f"{book.get('statusDesc','')} {book.get('totalChapterNum','')}集".strip(), "vod_content": str(book.get("introduction") or ""), "vod_play_sources": [{"name": "河马剧场", "episodes": eps}]}]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] {e}")
        return {"list": []}

async def play(params, context):
    try:
        p = params or {}
        pid = str(p.get("playId") or "").strip()
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        if not pid:
            return {"urls": [], "parse": 0, "header": headers}
        if re.search(r"\.(mp4|m3u8)", pid, re.I) and pid.startswith("http"):
            return {"urls": [{"name": "播放", "url": pid}], "parse": 0, "header": headers}
        if "+" in pid:
            drama_id, chapter_id = pid.split("+", 1)
            url = f"{HOST}/episode/{drama_id}/{chapter_id}"
            html = await _get(url)
            data = _next_data(html)
            vo = data.get("props", {}).get("pageProps", {}).get("chapterInfo", {}).get("chapterVideoVo") or {}
            video = vo.get("mp4") or vo.get("mp4720p") or vo.get("vodMp4Url")
            if not video:
                m = re.search(r'(https?://[^"\']+\.mp4[^"\']*)', html or "")
                video = m.group(1) if m else ""
            if video:
                return {"urls": [{"name": "播放", "url": video}], "parse": 0, "header": headers}
        return {"urls": [{"name": "播放", "url": pid}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
