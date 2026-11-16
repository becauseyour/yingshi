# -*- coding: utf-8 -*-
# @name 短剧聚合
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/影视/短剧/短剧聚合.py
# @description 短剧聚合（河马/围观，OmniBox）

import re
import json
from urllib.parse import quote
from spider_runner import OmniBox, run

CLASSES = [
    {"type_id": "河马", "type_name": "河马短剧"},
    {"type_id": "围观", "type_name": "围观短剧"},
]

HEMA_HOST = "https://www.kuaikaw.cn"
WEIGUAN_HOST = "https://api.drama.9ddm.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

async def _get(url, headers=None):
    try:
        res = await OmniBox.request(url, {"method": "GET", "headers": headers or {"User-Agent": UA}, "timeout": 15})
        return res.get("body") or ""
    except Exception:
        return ""

async def _post(url, data, headers=None):
    try:
        res = await OmniBox.request(url, {"method": "POST", "headers": headers or {"User-Agent": "okhttp/5.1.0", "Content-Type": "application/json"}, "body": json.dumps(data), "timeout": 15})
        body = res.get("body") or ""
        if isinstance(body, str) and body.startswith("{"):
            return json.loads(body)
        return {}
    except Exception:
        return {}

def _next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html or "", re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {}

async def home(params, context):
    try:
        html = await _get(HEMA_HOST + "/", {"User-Agent": UA, "Referer": HEMA_HOST + "/"})
        data = _next_data(html)
        props = data.get("props", {}).get("pageProps", {})
        items = []
        for b in (props.get("seoColumnVos") or [{}])[0].get("bookInfos") or []:
            if b.get("bookId"):
                items.append({"vod_id": f"河马@{b['bookId']}", "vod_name": str(b.get("bookName") or ""), "vod_pic": str(b.get("coverWap") or ""), "vod_remarks": f"[河马] {b.get('totalChapterNum','')}集"})
        return {"class": CLASSES, "list": items[:30], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": CLASSES, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or "河马")
        page = int(p.get("page") or 1)
        items = []
        if tid == "河马":
            url = f"{HEMA_HOST}/browse/462/{page}"
            html = await _get(url, {"User-Agent": UA, "Referer": HEMA_HOST + "/"})
            data = _next_data(html)
            for b in data.get("props", {}).get("pageProps", {}).get("bookList") or []:
                if b.get("bookId"):
                    items.append({"vod_id": f"河马@{b['bookId']}", "vod_name": str(b.get("bookName") or ""), "vod_pic": str(b.get("coverWap") or ""), "vod_remarks": f"{b.get('totalChapterNum','')}集"})
        elif tid == "围观":
            url = f"{WEIGUAN_HOST}/drama/home/search?version_code=1500&os_type=1"
            data = await _post(url, {"audience": "全部", "order": "最新", "page": page, "pageSize": 30, "searchWord": "", "subject": ""})
            for i in data.get("data") or []:
                items.append({"vod_id": f"围观@{i.get('oneId')}", "vod_name": str(i.get("title") or ""), "vod_pic": str(i.get("horzPoster") or i.get("vertPoster") or ""), "vod_remarks": f"{i.get('episodeCount','')}集"})
        return {"list": items, "page": page, "pagecount": page + (1 if len(items) >= 20 else 0), "total": len(items)}
    except Exception as e:
        await OmniBox.log("error", f"[category] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def search(params, context):
    try:
        p = params or {}
        keyword = (p.get("keyword") or "").strip()
        if not keyword:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        items = []
        url = f"{HEMA_HOST}/search?searchValue={quote(keyword)}&page=1"
        html = await _get(url, {"User-Agent": UA, "Referer": HEMA_HOST + "/"})
        data = _next_data(html)
        for b in data.get("props", {}).get("pageProps", {}).get("bookList") or []:
            if b.get("bookId"):
                items.append({"vod_id": f"河马@{b['bookId']}", "vod_name": str(b.get("bookName") or ""), "vod_pic": str(b.get("coverWap") or ""), "vod_remarks": "[河马]"})
        return {"list": items, "page": 1, "pagecount": 1, "total": len(items)}
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or "").strip()
        if not vid or "@" not in vid:
            return {"list": []}
        plat, did = vid.split("@", 1)
        if plat == "河马":
            url = f"{HEMA_HOST}/drama/{did}"
            html = await _get(url, {"User-Agent": UA, "Referer": HEMA_HOST + "/"})
            data = _next_data(html)
            props = data.get("props", {}).get("pageProps", {})
            book = props.get("bookInfoVo") or {}
            eps = []
            for ch in props.get("chapterList") or []:
                name = ch.get("chapterName") or "播放"
                vo = ch.get("chapterVideoVo") or {}
                direct = vo.get("mp4") or vo.get("mp4720p") or vo.get("vodMp4Url")
                if direct and re.search(r"\.(mp4|m3u8)", str(direct), re.I):
                    eps.append({"name": name, "playId": direct})
                else:
                    eps.append({"name": name, "playId": f"{did}+{ch.get('chapterId')}"})
            return {"list": [{"vod_id": vid, "vod_name": str(book.get("title") or book.get("bookName") or did), "vod_pic": str(book.get("coverWap") or ""), "vod_play_sources": [{"name": "河马", "episodes": eps}]}]}
        elif plat == "围观":
            url = f"{WEIGUAN_HOST}/drama/home/shortVideoDetail?oneId={did}&page=1&pageSize=1000&queryAll=true"
            res = await OmniBox.request(url, {"method": "GET", "headers": {"User-Agent": "okhttp/5.1.0"}, "timeout": 15})
            body = res.get("body") or ""
            data = json.loads(body) if body.startswith("{") else {}
            eps = []
            for e in data.get("data") or []:
                name = str(e.get("playOrder") or e.get("title") or "播放")
                clarities = e.get("videoClarityList") or []
                url_ = clarities[0].get("url") if clarities else ""
                if url_:
                    eps.append({"name": name, "playId": url_})
            return {"list": [{"vod_id": vid, "vod_name": str(data.get("title") or did), "vod_pic": str(data.get("vertPoster") or ""), "vod_play_sources": [{"name": "围观", "episodes": eps}]}]}
        return {"list": []}
    except Exception as e:
        await OmniBox.log("error", f"[detail] {e}")
        return {"list": []}

async def play(params, context):
    try:
        p = params or {}
        pid = str(p.get("playId") or "").strip()
        headers = {"User-Agent": UA, "Referer": HEMA_HOST + "/"}
        if not pid:
            return {"urls": [], "parse": 0, "header": headers}
        if pid.startswith("http") and re.search(r"\.(mp4|m3u8)", pid, re.I):
            return {"urls": [{"name": "播放", "url": pid}], "parse": 0, "header": headers}
        if "+" in pid:
            drama_id, chapter_id = pid.split("+", 1)
            url = f"{HEMA_HOST}/episode/{drama_id}/{chapter_id}"
            html = await _get(url, {"User-Agent": UA, "Referer": HEMA_HOST + "/"})
            data = _next_data(html)
            vo = data.get("props", {}).get("pageProps", {}).get("chapterInfo", {}).get("chapterVideoVo") or {}
            video = vo.get("mp4") or vo.get("mp4720p") or vo.get("vodMp4Url")
            if video:
                return {"urls": [{"name": "播放", "url": video}], "parse": 0, "header": headers}
        return {"urls": [{"name": "播放", "url": pid}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
