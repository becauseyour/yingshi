# -*- coding: utf-8 -*-
# @name 爆色
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/%E7%88%86%E8%89%B2.py
# @description 爆色 BaoPorn（OmniBox）

"""
爆色 v1.0.0
主站: https://baoporn.com
"""

import base64
import re
from urllib.parse import quote

from spider_runner import OmniBox, run

HOST = "https://baoporn.com"
UA = "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36"

CATS = [
    ("1", "最新视频", "video"),
    ("2", "国产", "tag/%E5%9B%BD%E4%BA%A7"),
    ("3", "日本", "tag/%E6%97%A5%E6%9C%AC"),
    ("4", "自拍", "tag/%E8%87%AA%E6%8B%8D"),
    ("5", "剧情", "tag/%E5%89%A7%E6%83%85"),
    ("10", "人妻", "tag/%E4%BA%BA%E5%A6%BB"),
    ("12", "麻豆传媒", "tag/%E9%BA%BB%E8%B1%86%E4%BC%A0%E5%AA%92"),
    ("15", "巨乳", "tag/%E5%B7%A8%E4%B9%B3"),
    ("18", "中出", "tag/%E4%B8%AD%E5%87%BA"),
    ("25", "素人", "tag/%E7%B4%A0%E4%BA%BA"),
    ("41", "OnlyFans", "tag/onlyfans"),
]
CAT_MAP = {cid: path for cid, _, path in CATS}

async def _get(url):
    try:
        res = await OmniBox.request(
            url,
            method="GET",
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        )
        return res.body or ""
    except Exception as e:
        await OmniBox.log("error", f"[爆色] get failed: {e}")
        return ""

def _decrypt(encoded):
    try:
        s = encoded[::-1]
        pad = len(s) % 4
        if pad:
            s += "=" * (4 - pad)
        return base64.b64decode(s).decode("utf-8", errors="replace")
    except Exception:
        return ""

def _parse_cards(html):
    items = []
    parts = (html or "").split('class="video-card group"')
    for part in parts[1:]:
        m = re.search(r'href="/video/([A-Za-z0-9]+)"', part)
        if not m:
            continue
        vid = m.group(1)
        m2 = re.search(r'<img src="([^"]+)" alt="([^"]*)"', part)
        pic = m2.group(1) if m2 else ""
        title = m2.group(2) if m2 else ""
        if not title:
            m3 = re.search(r'<p class="text-sm[^"]*">([^<]+)</p>', part)
            title = m3.group(1).strip() if m3 else vid
        m4 = re.search(r'right-1 bg-black[^>]*>([^<]+)</span>', part)
        duration = m4.group(1) if m4 else ""
        items.append({
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": duration,
        })
    return items

async def home(params, context):
    classes = [{"type_id": cid, "type_name": name} for cid, name, _ in CATS]
    return {"class": classes, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("type_id") or p.get("tid") or "1")
        page = int(p.get("page") or 1)
        path = CAT_MAP.get(tid, "video")
        url = f"{HOST}/{path}" if page <= 1 else f"{HOST}/{path}/page/{page}"
        html = await _get(url)
        items = _parse_cards(html)
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
        url = f"{HOST}/search?q={quote(keyword)}"
        if page > 1:
            url += f"&page={page}"
        html = await _get(url)
        items = _parse_cards(html)
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
        html = await _get(f"{HOST}/video/{vid}")
        title = ""
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
        if m:
            title = m.group(1).strip()
        pic = ""
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if m:
            pic = m.group(1)
        play_url = ""
        m = re.search(r'data-url="([^"]+)"', html)
        if m:
            play_url = _decrypt(m.group(1))
        if not play_url:
            return {"list": []}
        return {
            "list": [
                {
                    "vod_id": vid,
                    "vod_name": title or vid,
                    "vod_pic": pic,
                    "vod_remarks": "MP4",
                    "vod_play_sources": [
                        {"name": "BaoPorn", "episodes": [{"name": "播放", "playId": play_url}]}
                    ],
                }
            ]
        }
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
        return {"urls": [{"name": "播放", "url": url}], "parse": 0, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
