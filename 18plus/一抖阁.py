# -*- coding: utf-8 -*-
# @name 一抖阁
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/%E4%B8%80%E6%8A%96%E9%98%81.py
# @description 一抖阁（OmniBox）

import re
import html
from urllib.parse import quote, urljoin, unquote
from spider_runner import OmniBox, run

HOST = "https://yidouge.vip"
UA = "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

CATS = [
    {"type_id": HOST + "/v2/ai%E7%9F%AD%E5%89%A7/", "type_name": "AI短剧"},
    {"type_id": HOST + "/v2/%E7%BB%BF%E5%B8%BDntr/", "type_name": "伦理绿帽NTR"},
    {"type_id": HOST + "/v2/%E9%83%BD%E5%B8%82/", "type_name": "现代"},
    {"type_id": HOST + "/v2/%E5%8F%A4%E8%A3%85/", "type_name": "古装"},
    {"type_id": HOST + "/v2/pmv/", "type_name": "PMV"},
]

async def _get(url):
    try:
        res = await OmniBox.request(url, {
            "method": "GET",
            "headers": {"User-Agent": UA, "Referer": HOST + "/", "Accept-Language": "zh-CN,zh;q=0.9"},
            "timeout": 15,
        })
        return res.get("body") or ""
    except Exception as e:
        await OmniBox.log("error", f"[一抖阁] get failed: {e}")
        return ""

def _clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()

def _href(h):
    return urljoin(HOST, html.unescape(h or "").replace("\\/", "/"))

def _items(text):
    out, seen = [], set()
    for m in re.finditer(r'href="(https://yidouge\.vip/video/[^"]+)"[^>]*>(.*?)</a>', text or "", re.I | re.S):
        u = m.group(1)
        if u in seen:
            continue
        title = _clean(m.group(2))
        if not title:
            title = unquote(u.rstrip("/").split("/")[-1])
        lo = max(0, m.start() - 500)
        seg = (text or "")[lo:m.end() + 200]
        pic = ""
        pm = re.search(r'<img[^>]+(?:data-src|src)=["\']([^"\']+)', seg, re.I)
        if pm:
            pic = _href(pm.group(1))
        out.append({"vod_id": u, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
        seen.add(u)
    return out

async def home(params, context):
    try:
        html_text = await _get(HOST)
        return {"class": CATS, "list": _items(html_text), "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": CATS, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or CATS[0]["type_id"])
        page = int(p.get("page") or 1)
        u = tid if tid.startswith("http") else _href(tid)
        u = u.rstrip("/") + "/"
        if page > 1:
            u = u.rstrip("/") + f"/page/{page}/"
        html_text = await _get(u)
        items = _items(html_text)
        return {"list": items, "page": page, "pagecount": page + (1 if len(items) >= 10 else 0), "total": len(items)}
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
        u = f"{HOST}/?s={quote(keyword)}"
        if page > 1:
            u += f"&paged={page}"
        html_text = await _get(u)
        items = _items(html_text)
        return {"list": items, "page": page, "pagecount": page + (1 if items else 0), "total": len(items)}
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or "").strip()
        if not vid:
            return {"list": []}
        u = _href(vid)
        html_text = await _get(u)
        title = ""
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.I | re.S)
        if m:
            title = _clean(m.group(1))
        if not title:
            title = unquote(u.rstrip("/").split("/")[-1])
        pic = ""
        pm = re.search(r'data-video-poster=["\']([^"\']+)', html_text, re.I)
        if pm:
            pic = _href(pm.group(1))
        return {"list": [{"vod_id": u, "vod_name": title, "vod_pic": pic, "vod_remarks": "", "vod_play_sources": [{"name": "一抖阁", "episodes": [{"name": "正片", "playId": u}]}]}]}
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
        if re.search(r"\.(mp4|m3u8|flv)", url, re.I):
            return {"urls": [{"name": "播放", "url": url}], "parse": 0, "header": headers}
        html_text = await _get(url)
        vm = re.search(r'data-video-url=["\']([^"\']+)', html_text, re.I)
        if not vm:
            vm = re.search(r'<video[^>]+src=["\']([^"\']+)', html_text, re.I)
        if not vm:
            vm = re.search(r'<source[^>]+src=["\']([^"\']+)', html_text, re.I)
        if not vm:
            vm = re.search(r'["\'](https?://[^"\']+\.(?:mp4|m3u8)[^"\']*)["\']', html_text, re.I)
        if vm:
            real = _href(vm.group(1))
            return {"urls": [{"name": "播放", "url": real}], "parse": 0, "header": headers}
        return {"urls": [{"name": "播放", "url": url}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
