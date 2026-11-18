# -*- coding: utf-8 -*-
# @name 饭搭子影视
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/电影电视/饭搭子影视.py
# @description 饭搭子影视（OmniBox）

import re
import json
from urllib.parse import quote
from spider_runner import OmniBox, run

HOST = "https://fdzys.net"
UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/124.0 Mobile Safari/537.36"

CLASSES = [
    {"type_id": "movie", "type_name": "电影"},
    {"type_id": "tv", "type_name": "电视剧"},
    {"type_id": "dongman", "type_name": "动漫"},
    {"type_id": "zongyi", "type_name": "综艺"},
    {"type_id": "duanju", "type_name": "短剧"},
    {"type_id": "tiyu", "type_name": "体育"},
]
CATE_MAP = {
    "movie": "movie/all", "tv": "tv/all", "dongman": "dongman/all",
    "zongyi": "zongyi/all", "duanju": "duanju/all", "tiyu": "tiyu",
}

async def _get(url):
    try:
        res = await OmniBox.request(url, {"method": "GET", "headers": {"User-Agent": UA, "Referer": HOST + "/"}, "timeout": 15})
        return res.get("body") or ""
    except Exception:
        return ""

def _cards(html):
    out, seen = [], set()
    pat = r'<a\b([^>]*href=["\'][^"\']*/(?:movie|tv|dongman|zongyi|duanju|tiyu)/[^"\']+["\'][^>]*)>(.*?)</a>'
    for m in re.finditer(pat, html or "", re.I | re.S):
        attrs, body = m.group(1), m.group(2)
        if "<img" not in body.lower():
            continue
        hm = re.search(r'href=["\']([^"\']+)["\']', attrs)
        if not hm:
            continue
        href = hm.group(1)
        if not href.startswith("/"):
            continue
        if href in seen:
            continue
        seen.add(href)
        im = re.search(r'<img[^>]+(?:alt|title)=["\']([^"\']*)["\']', body)
        title = im.group(1) if im else re.sub(r"<[^>]+>", "", body).strip()[:40]
        pm = re.search(r'(?:data-src|data-original|src)=["\']([^"\']+)["\']', body)
        pic = pm.group(1) if pm else ""
        if pic and not pic.startswith("http"):
            pic = HOST + pic if pic.startswith("/") else pic
        out.append({"vod_id": href.rstrip("/"), "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
    return out

async def home(params, context):
    try:
        html = await _get(HOST + "/")
        return {"class": CLASSES, "list": _cards(html)[:40], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": CLASSES, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or "movie")
        page = int(p.get("page") or 1)
        cate = CATE_MAP.get(tid, tid)
        url = f"{HOST}/{cate}"
        if page > 1:
            url += f"?page={page}"
        html = await _get(url)
        items = _cards(html)
        return {"list": items, "page": page, "pagecount": page + (1 if len(items) >= 20 else 0), "total": len(items)}
    except Exception as e:
        await OmniBox.log("error", f"[category] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def search(params, context):
    try:
        p = params or {}
        key = (p.get("keyword") or "").strip()
        page = int(p.get("page") or 1)
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        url = f"{HOST}/yu-{quote(key)}-xianguan-de-yingpian-shippin-zhibo"
        if page > 1:
            url += f"?page={page}"
        html = await _get(url)
        items = _cards(html)
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
        url = HOST + vid if vid.startswith("/") else vid
        html = await _get(url)
        m = re.search(r"var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>", html or "", re.S)
        data = json.loads(m.group(1)) if m else {}
        title = data.get("vod_data", {}).get("vod_name") or re.search(r"<h1[^>]*>(.*?)</h1>", html or "")
        title = title.group(1) if hasattr(title, "group") else (title or vid.split("/")[-1])
        title = re.sub(r"<[^>]+>", "", str(title)).strip()
        pic = ""
        pm = re.search(r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html or "")
        if pm:
            pic = pm.group(1)
        # 播放列表
        eps = []
        for a in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', html or ""):
            href, name = a.group(1), a.group(2).strip()
            if "/play/" in href or href.endswith(".html"):
                eps.append({"name": name or "播放", "playId": href})
        if not eps:
            eps = [{"name": "播放", "playId": vid}]
        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_play_sources": [{"name": "饭搭子", "episodes": eps[:50]}]}]}
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
        if re.search(r"\.(m3u8|mp4)", pid, re.I) and pid.startswith("http"):
            return {"urls": [{"name": "播放", "url": pid}], "parse": 0, "header": headers}
        url = HOST + pid if pid.startswith("/") else pid
        html = await _get(url)
        m = re.search(r"var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>", html or "", re.S)
        if m:
            data = json.loads(m.group(1))
            u = data.get("url", "")
            enc = int(data.get("encrypt", 0) or 0)
            if enc == 1:
                from urllib.parse import unquote
                u = unquote(u)
            elif enc == 2:
                import base64
                from urllib.parse import unquote
                u = unquote(base64.b64decode(u).decode("utf-8", "ignore"))
            u = u.replace("\\/", "/")
            if u:
                return {"urls": [{"name": "播放", "url": u}], "parse": 0 if re.search(r"\.(m3u8|mp4)", u, re.I) else 1, "header": headers}
        return {"urls": [{"name": "播放", "url": pid}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
