# -*- coding: utf-8 -*-
# @name 巨婴云播
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/%E5%B7%A8%E5%A9%B4%E4%BA%91%E6%92%AD.py
# @description 巨婴云播（OmniBox）

import re
import json
import base64
from urllib.parse import quote, unquote
from spider_runner import OmniBox, run

SITE = "https://vngxt9ep5ahq.qdcypxxx.com"
UA = "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

GROUPS = [("精选推荐", 0, 6), ("国产AV", 6, 10), ("日本AV", 16, 10), ("欧美AV", 26, 4), ("H动漫", 30, 6)]

def _html_unescape(s):
    import html as _h
    return _h.unescape(s) if s else s

async def _get(url, referer=None):
    try:
        headers = {"User-Agent": UA, "Referer": referer or SITE, "Accept-Language": "zh-CN,zh;q=0.9"}
        res = await OmniBox.request(url, {"method": "GET", "headers": headers, "timeout": 15})
        return res.get("body") or ""
    except Exception as e:
        await OmniBox.log("error", f"[巨婴] get failed: {e}")
        return ""

def _dec_page(raw):
    if not raw:
        return ""
    try:
        m = re.search(r'var a="([^"]+)"', raw)
        if not m:
            return raw
        s = unquote(m.group(1))
        b = base64.b64decode(s)
        return unquote(b.decode("utf-8", "ignore"))
    except Exception:
        return raw

def _dec_api(raw):
    try:
        j = json.loads(raw)
        c = j.get("content", "")
        if not c:
            return ""
        b = base64.b64decode(c)
        return unquote(b.decode("utf-8", "ignore"))
    except Exception:
        return ""

def _u(u):
    if not u:
        return u
    u = u.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http"):
        return u
    if u.startswith("/"):
        return SITE.rstrip("/") + u
    return SITE.rstrip("/") + "/" + u.lstrip("/")

def _items(html):
    out, seen = [], set()
    if not html:
        return out
    for bm in re.finditer(r'<a[^>]*class=["\']?label vlink["\']?[^>]*>([\s\S]*?)</a>', html):
        block = bm.group(0)
        hm = re.search(r'href=["\']?(/video/[^"\'\s>]+)["\']?', block)
        im = re.search(r'<img[^>]+src=["\']?([^"\'\s>]+)["\']?', block)
        tm = re.search(r'<div[^>]*class=["\']?title["\']?>([^<]+)</div>', block)
        if not (hm and tm):
            continue
        vid = _u(hm.group(1))
        if vid in seen:
            continue
        seen.add(vid)
        out.append({"vod_id": vid, "vod_name": _html_unescape(tm.group(1)).strip(), "vod_pic": _u(im.group(1)) if im else "", "vod_remarks": ""})
    return out

async def _cats():
    html = _dec_page(await _get(SITE))
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="/list/video/(CC[0-9A-Za-z]+)\.html"[^>]*>(.*?)</a>', html, re.S):
        cid = m.group(1)
        name = _html_unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        if not name or name.startswith("更多") or len(name) > 16 or cid in seen:
            continue
        seen.add(cid)
        out.append({"type_id": cid, "type_name": name})
    return out

async def home(params, context):
    try:
        cats = await _cats()
        classes = [{"type_id": f"g:{i}", "type_name": n} for i, (n, _, _) in enumerate(GROUPS)]
        html = _dec_page(await _get(SITE))
        return {"class": classes or cats, "list": _items(html), "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": [], "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or "").strip()
        page = int(p.get("page") or 1)
        cid = tid
        m = re.search(r'(CC[0-9A-Za-z]+)', tid)
        if m:
            cid = m.group(1)
        elif tid.startswith("g:"):
            cats = await _cats()
            gi = int(tid.split(":")[1])
            if 0 <= gi < len(GROUPS):
                _, st, cnt = GROUPS[gi]
                subs = cats[st:st + cnt]
                if subs:
                    cid = subs[0]["type_id"]
        list_url = f"{SITE}/list/video/{cid}.html"
        if page == 1:
            html = _dec_page(await _get(list_url))
            items = _items(html)
            return {"list": items, "page": 1, "pagecount": 2 if len(items) >= 20 else 1, "total": len(items)}
        api_url = f"{SITE}/xapi/list/loadmore/{cid}/video/{page}"
        raw = await _get(api_url, referer=list_url)
        html = _dec_api(raw)
        items = _items(html)
        return {"list": items, "page": page, "pagecount": page + (1 if items else 0), "total": len(items)}
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
        url = f"{SITE}/xapi/search/data/{page}/video/{quote(keyword)}"
        raw = await _get(url, referer=SITE + "/search.html")
        html = _dec_api(raw)
        return {"list": _items(html), "page": page, "pagecount": 1, "total": 0}
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or "").strip()
        m = re.search(r'/video/([A-Za-z0-9]+)', vid)
        if m:
            vid = m.group(1)
        if not vid:
            return {"list": []}
        url = f"{SITE}/video/{vid}.html"
        html = _dec_page(await _get(url))
        title = ""
        tm = re.search(r'<div class="title">(.*?)</div>', html, re.S)
        if tm:
            title = _html_unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip()
        pic, vurl = "", ""
        dm = re.search(r'id="dplayers"[^>]*>', html)
        if dm:
            tag = dm.group(0)
            pm = re.search(r'vpic="([^"]*)"', tag)
            if pm:
                pic = _u(pm.group(1))
            um = re.search(r'vurl="([^"]*)"', tag)
            if um:
                vurl = _html_unescape(um.group(1)).strip()
        eps = []
        if vurl:
            parts = [x.strip() for x in vurl.split("#") if x.strip()]
            for i, part in enumerate(parts):
                eps.append({"name": f"第{i+1}集" if len(parts) > 1 else "正片", "playId": _u(part)})
        if not eps:
            eps = [{"name": "播放", "playId": url}]
        return {"list": [{"vod_id": vid, "vod_name": title or vid, "vod_pic": pic, "vod_play_sources": [{"name": "巨婴", "episodes": eps}]}]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] {e}")
        return {"list": []}

async def play(params, context):
    try:
        p = params or {}
        url = str(p.get("playId") or "").strip()
        headers = {"User-Agent": UA, "Referer": SITE + "/"}
        if not url:
            return {"urls": [], "parse": 0, "header": headers}
        if not url.startswith("http"):
            url = _u(url)
        if re.search(r"\.(m3u8|mp4|flv)", url, re.I) or "m3u8" in url.lower():
            return {"urls": [{"name": "播放", "url": url}], "parse": 0, "header": headers}
        return {"urls": [{"name": "播放", "url": url}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
