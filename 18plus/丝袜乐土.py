# -*- coding: utf-8 -*-
# @name 丝袜乐土
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/丝袜乐土.py
# @description 丝袜乐土（OmniBox）

import re
import base64
from spider_runner import OmniBox, run

HOST = "https://xbffh.swwlt15.xyz"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

FALLBACK_CATS = [
    {"type_id": "6097633", "type_name": "精品推荐"},
    {"type_id": "6107633", "type_name": "国产精品"},
    {"type_id": "6117633", "type_name": "探花系列"},
    {"type_id": "6127633", "type_name": "自拍偷拍"},
    {"type_id": "6137633", "type_name": "少女少妇"},
    {"type_id": "6147633", "type_name": "无码专区"},
    {"type_id": "6157633", "type_name": "欧美性爱"},
    {"type_id": "6167633", "type_name": "颜值正妹"},
]

def _d(s):
    try:
        return base64.b64decode(s).decode("utf-8", "replace")
    except Exception:
        return s

async def _get(url):
    try:
        res = await OmniBox.request(url, {"method": "GET", "headers": {"User-Agent": UA, "Referer": HOST + "/"}, "timeout": 15})
        return res.get("body") or ""
    except Exception:
        return ""

def _cards(html):
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="/video\.php\?id=(\d+)"[^>]*>', html or ""):
        vid = m.group(1)
        if vid in seen:
            continue
        seen.add(vid)
        # 尝试找标题
        block = html[max(0, m.start()-500):m.end()+200]
        tm = re.search(r"d\('([^']+)'\)", block)
        title = _d(tm.group(1)) if tm else f"视频{vid}"
        title = re.sub(r"<[^>]+>", "", title).strip()[:60]
        im = re.search(r'data-original=["\']([^"\']+)["\']', block)
        pic = im.group(1) if im else ""
        if pic and not pic.startswith("http"):
            pic = HOST + pic if pic.startswith("/") else pic
        out.append({"vod_id": vid, "vod_name": title or vid, "vod_pic": pic, "vod_remarks": ""})
    return out

async def home(params, context):
    try:
        html = await _get(HOST + "/")
        cats = []
        for m in re.finditer(r'<a[^>]+href="/list\.php\?id=(\d+)&page=1"[^>]*>.*?d\(\'([^\']+)\'\)', html or "", re.S):
            tid, enc = m.group(1), m.group(2)
            name = re.sub(r"<[^>]+>", "", _d(enc)).strip()
            if name and len(name) < 20:
                cats.append({"type_id": tid, "type_name": name})
        if len(cats) < 3:
            cats = FALLBACK_CATS
        return {"class": cats[:16], "list": _cards(html)[:20], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": FALLBACK_CATS, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or "6097633")
        page = int(p.get("page") or 1)
        url = f"{HOST}/list.php?id={tid}&page={page}"
        html = await _get(url)
        items = _cards(html)
        return {"list": items, "page": page, "pagecount": page + (1 if len(items) >= 15 else 0), "total": len(items)}
    except Exception as e:
        await OmniBox.log("error", f"[category] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def search(params, context):
    try:
        p = params or {}
        key = (p.get("keyword") or "").strip()
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        res = await OmniBox.request(f"{HOST}/search.php", {"method": "POST", "headers": {"User-Agent": UA, "Referer": HOST + "/", "Content-Type": "application/x-www-form-urlencoded"}, "body": f"content={key}", "timeout": 15})
        html = res.get("body") or ""
        return {"list": _cards(html), "page": 1, "pagecount": 1, "total": 0}
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or "").strip()
        if not vid:
            return {"list": []}
        url = f"{HOST}/video.php?id={vid}"
        html = await _get(url)
        title = re.search(r"<h1[^>]*>(.*?)</h1>", html or "")
        title = re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else vid
        # 播放
        play = ""
        mm = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html or "")
        if mm:
            play = mm.group(1)
        if not play:
            for enc in re.findall(r"d\('([^']+)'\)", html or ""):
                dec = _d(enc)
                mm = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', dec)
                if mm:
                    play = mm.group(1)
                    break
        eps = [{"name": "播放", "playId": play or url}]
        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": "", "vod_play_sources": [{"name": "丝袜", "episodes": eps}]}]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] {e}")
        return {"list": []}

async def play(params, context):
    try:
        p = params or {}
        pid = str(p.get("playId") or "").strip()
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        if pid.startswith("http") and re.search(r"\.(m3u8|mp4)", pid, re.I):
            return {"urls": [{"name": "播放", "url": pid}], "parse": 0, "header": headers}
        if pid.startswith("http"):
            html = await _get(pid)
            mm = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html or "")
            if mm:
                return {"urls": [{"name": "播放", "url": mm.group(1)}], "parse": 0, "header": headers}
        return {"urls": [{"name": "播放", "url": pid}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
