# -*- coding: utf-8 -*-
# @name 草莓视频
# @version 1.0.1
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/%E8%8D%89%E8%8E%93%E8%A7%86%E9%A2%91.py
# @description 草莓视频（OmniBox，AES解密）

import re
import json
import base64
from urllib.parse import quote
from spider_runner import OmniBox, run

HOST = "https://scor.t2j8l5ixcm.cc"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15"
AES_KEY = b"NHboMHZerxFQ401E"
AES_IV = b"i7JeCEIMVrj2W9xN"

CLASSES = [
    {"type_id": "featured", "type_name": "精选"},
    {"type_id": "51", "type_name": "国产"},
    {"type_id": "76", "type_name": "日韩"},
    {"type_id": "127", "type_name": "欧美"},
    {"type_id": "93", "type_name": "吃瓜"},
    {"type_id": "60", "type_name": "传媒"},
    {"type_id": "137", "type_name": "AI视频"},
    {"type_id": "83", "type_name": "动漫"},
]

def _aes_decrypt(data):
    """AES-CBC解密，优先 cryptography"""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        dec = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV)).decryptor()
        plain = dec.update(data) + dec.finalize()
        pad = plain[-1]
        if 1 <= pad <= 16:
            plain = plain[:-pad]
        return plain
    except Exception:
        pass
    try:
        from Crypto.Cipher import AES
        c = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        plain = c.decrypt(data)
        pad = plain[-1]
        if 1 <= pad <= 16:
            plain = plain[:-pad]
        return plain
    except Exception:
        pass
    return b""

async def _api(path):
    try:
        url = HOST + path
        res = await OmniBox.request(url, {
            "method": "GET",
            "headers": {"User-Agent": UA, "Accept": "application/json, text/plain, */*", "platform": "9", "Referer": HOST + "/"},
            "timeout": 15,
        })
        body = res.get("body") or ""
        if isinstance(body, str):
            body = body.strip()
            if body.startswith("{") or body.startswith("["):
                return json.loads(body)
            try:
                pad = len(body) % 4
                if pad:
                    body += "=" * (4 - pad)
                raw = base64.b64decode(body)
                plain = _aes_decrypt(raw)
                if plain:
                    return json.loads(plain.decode("utf-8", "ignore"))
            except Exception:
                pass
        return None
    except Exception as e:
        await OmniBox.log("error", f"[草莓] api failed: {e}")
        return None

def _cards(records):
    out = []
    if not isinstance(records, list):
        return out
    for r in records:
        if not isinstance(r, dict) or not r.get("viewKey"):
            continue
        out.append({"vod_id": str(r["viewKey"]), "vod_name": str(r.get("title") or "").strip(), "vod_pic": str(r.get("poster") or ""), "vod_remarks": str(r.get("duration") or "")})
    return out

async def home(params, context):
    try:
        data = await _api("/app/movie/getList?page=1&pageSize=18&sort=2")
        items = _cards((data or {}).get("records") or [])
        return {"class": CLASSES, "list": items, "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": CLASSES, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or "featured")
        page = int(p.get("page") or 1)
        if tid == "featured":
            path = f"/app/movie/getList?page={page}&pageSize=18&sort=2"
        else:
            path = f"/app/movie/getList?page={page}&pageSize=18&cid={tid}&sort=1"
        data = await _api(path)
        items = _cards((data or {}).get("records") or [])
        pc = int((data or {}).get("pageCount") or page)
        return {"list": items, "page": page, "pagecount": pc, "total": int((data or {}).get("total") or 0)}
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
        data = await _api(f"/app/movie/getList?keyword={quote(keyword)}&page={page}&pageSize=18")
        items = _cards((data or {}).get("records") or [])
        return {"list": items, "page": page, "pagecount": 1, "total": 0}
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def detail(params, context):
    try:
        p = params or {}
        vk = str(p.get("videoId") or p.get("id") or "").strip()
        if not vk:
            return {"list": []}
        data = await _api(f"/app/movie/getDetail?viewKey={quote(vk)}")
        d = (data or {}).get("data") if isinstance(data, dict) else None
        if not isinstance(d, dict):
            return {"list": []}
        title = str(d.get("title") or "").strip()
        pic = str(d.get("poster") or "")
        return {"list": [{"vod_id": vk, "vod_name": title, "vod_pic": pic, "vod_remarks": str(d.get("duration") or ""), "vod_play_sources": [{"name": "草莓", "episodes": [{"name": "正片", "playId": vk}]}]}]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] {e}")
        return {"list": []}

async def play(params, context):
    try:
        p = params or {}
        vk = str(p.get("playId") or "").strip()
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        if not vk:
            return {"urls": [], "parse": 0, "header": headers}
        data = await _api(f"/app/movie/getPlayUrl?viewKey={quote(vk)}")
        d = (data or {}).get("data") if isinstance(data, dict) else None
        if not isinstance(d, dict):
            return {"urls": [], "parse": 0, "header": headers}
        play_url = str(d.get("playUrl") or "")
        if not play_url:
            return {"urls": [], "parse": 0, "header": headers}
        if not play_url.startswith("http"):
            infos = d.get("sourceInfoListVO") or []
            if infos and isinstance(infos[0], dict):
                domain = str(infos[0].get("playDomain") or "").rstrip("/")
                if domain:
                    play_url = domain + play_url
        return {"urls": [{"name": "播放", "url": play_url}], "parse": 0, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
