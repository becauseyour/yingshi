# -*- coding: utf-8 -*-
# @name 金莲AV
# @version 1.2.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/金莲AV.py
# @dependencies cryptography,pycryptodome
# @description 金莲AV站源（OmniBox）：AES 解密 API、分类/搜索/直链播放

import json
import base64
from urllib.parse import quote, urljoin

from spider_runner import OmniBox, run

_HAS_CRYPTOGRAPHY = False
_HAS_PYCRYPTODOME = False
try:
    from cryptography.hazmat.primitives.ciphers import Cipher as _Cipher
    from cryptography.hazmat.primitives.ciphers import algorithms as _algorithms
    from cryptography.hazmat.primitives.ciphers import modes as _modes
    from cryptography.hazmat.primitives import padding as _padding
    _HAS_CRYPTOGRAPHY = True
except Exception:
    pass
try:
    from Crypto.Cipher import AES as _AES
    from Crypto.Util.Padding import unpad as _unpad
    _HAS_PYCRYPTODOME = True
except Exception:
    pass

HOSTS = [
    "https://osazwl.jinlianav.cyou",
    "https://www.jinlianav.cyou",
]
HOST = HOSTS[0]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_AES_KEY = b"a9yX32LpQvUt7wBc"
_AES_IV = b"N7cPk2Bv38hWqFzM"
_SKIP_CATS = {"1741", "1743"}
_host = HOST


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _aes_decrypt(cipher_b64):
    data = base64.b64decode(cipher_b64)
    last_err = None
    if _HAS_CRYPTOGRAPHY:
        try:
            decryptor = _Cipher(_algorithms.AES(_AES_KEY), _modes.CBC(_AES_IV)).decryptor()
            plain = decryptor.update(data) + decryptor.finalize()
            unpadder = _padding.PKCS7(128).unpadder()
            plain = unpadder.update(plain) + unpadder.finalize()
            return json.loads(plain.decode("utf-8"))
        except Exception as e:
            last_err = e
    if _HAS_PYCRYPTODOME:
        try:
            cipher = _AES.new(_AES_KEY, _AES.MODE_CBC, _AES_IV)
            plain = _unpad(cipher.decrypt(data), 16)
            return json.loads(plain.decode("utf-8"))
        except Exception as e:
            last_err = e
    raise RuntimeError("AES 解密失败(无可用库或密钥变更): %s" % last_err)


async def _api(path):
    global _host
    last_err = None
    hosts = [_host] + [h for h in HOSTS if h != _host]
    for host in hosts:
        url = path if path.startswith("http") else host + "/api" + path
        headers = {
            "User-Agent": UA,
            "Referer": host + "/",
            "Origin": host,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        for i in range(2):
            try:
                res = await OmniBox.request(url, {"method": "GET", "headers": headers, "timeout": 15})
                status = res.get("statusCode") or 0
                text = res.get("body") or ""
                if status and status >= 400:
                    raise RuntimeError("HTTP %s" % status)
                body = json.loads(text) if text.strip().startswith("{") else {}
                if isinstance(body, dict) and body.get("cipher"):
                    _host = host
                    return _aes_decrypt(body["cipher"])
                if isinstance(body, dict) and body.get("code") == 0:
                    _host = host
                    return body
                if body:
                    _host = host
                    return body
            except Exception as e:
                last_err = e
                await OmniBox.log("warn", "[api] %s try%d: %s" % (host, i + 1, e))
    await OmniBox.log("error", "[api] 全部失败 %s: %s" % (path, last_err))
    return {}


def _map_list(items):
    out = []
    for it in items or []:
        vid = str(it.get("id") or "")
        name = (it.get("title") or "").strip()
        if not vid or not name:
            continue
        out.append({
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": it.get("cover_url") or "",
            "vod_remarks": it.get("category") or "",
        })
    return out


async def home(params, context):
    try:
        await OmniBox.log("info", "[home] crypto=%s/%s" % (_HAS_CRYPTOGRAPHY, _HAS_PYCRYPTODOME))
        if not _HAS_CRYPTOGRAPHY and not _HAS_PYCRYPTODOME:
            await OmniBox.log("error", "[home] 缺少 cryptography 或 pycryptodome")
            return {"class": [], "list": [], "filters": {}}
        data = await _api("/categories")
        lst = ((data or {}).get("data") or {}).get("list") or []
        classes = []
        for c in lst:
            if c.get("module") != "video":
                continue
            cid = str(c.get("id") or "")
            name = (c.get("name") or "").strip()
            if not cid or not name or cid in _SKIP_CATS:
                continue
            if any(k in name for k in ("萝莉", "幼女", "人兽")):
                continue
            classes.append({"type_id": cid, "type_name": name})
        home_data = await _api("/videos?page=1&ps=24")
        videos = _map_list(((home_data or {}).get("data") or {}).get("list") or [])
        return {"class": classes, "list": videos, "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[home] 失败: %s" % e)
        return {"class": [], "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "")
        page = _to_int((params or {}).get("page"), 1) or 1
        if tid in _SKIP_CATS:
            return {"list": [], "page": page, "pagecount": 1, "limit": 0, "total": 0}
        await OmniBox.log("info", "[category] id=%s page=%s" % (tid, page))
        data = await _api("/videos?category_id=%s&page=%s&ps=24" % (quote(tid), page))
        d = (data or {}).get("data") or {}
        videos = _map_list(d.get("list") or [])
        pages = int(d.get("pages") or 1) or 1
        return {
            "list": videos,
            "page": int(d.get("page") or page),
            "pagecount": pages,
            "limit": 24,
            "total": int(d.get("total") or pages * 24),
        }
    except Exception as e:
        await OmniBox.log("error", "[category] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 24}


async def detail(params, context):
    try:
        vod_id = str((params or {}).get("videoId") or "")
        if not vod_id:
            return {"list": []}
        await OmniBox.log("info", "[detail] id=%s" % vod_id)
        data = await _api("/movie?id=%s" % quote(vod_id))
        info = ((data or {}).get("data") or {}).get("info") or {}
        # 部分接口直接把字段放在 data
        if not info and isinstance((data or {}).get("data"), dict):
            cand = data["data"]
            if cand.get("play_url") or cand.get("title"):
                info = cand
        if not info:
            return {"list": []}
        name = (info.get("title") or ("视频%s" % vod_id)).strip()
        pic = info.get("cover_url") or ""
        play = (info.get("play_url") or "").strip()
        vod = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": name,
        }
        if play:
            vod["vod_play_sources"] = [{"name": "线路1", "episodes": [{"name": "正片", "playId": play}]}]
        else:
            vod["vod_play_sources"] = [{"name": "线路1", "episodes": [{"name": "正片", "playId": vod_id}]}]
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] 失败: %s" % e)
        return {"list": []}


async def search(params, context):
    try:
        key = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 24}
        await OmniBox.log("info", "[search] %s" % key)
        data = await _api("/videos?kw=%s&page=%s&ps=24" % (quote(key), page))
        d = (data or {}).get("data") or {}
        return {
            "list": _map_list(d.get("list") or []),
            "page": page,
            "pagecount": int(d.get("pages") or 1) or 1,
            "limit": 24,
            "total": int(d.get("total") or 0),
        }
    except Exception as e:
        await OmniBox.log("error", "[search] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 24}


async def _resolve_m3u8(url):
    if not url or ".m3u8" not in url:
        return url
    try:
        res = await OmniBox.request(
            url,
            {"method": "GET", "headers": {"User-Agent": UA, "Referer": _host + "/"}, "timeout": 15},
        )
        body = res.get("body") or ""
        if not body or ("#EXTINF" in body and "#EXT-X-STREAM-INF" not in body):
            return url
        for line in body.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and ".m3u8" in line:
                return line if line.startswith("http") else urljoin(url, line)
    except Exception:
        pass
    return url


async def play(params, context):
    try:
        raw = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not raw:
            raise ValueError("playId 为空")
        await OmniBox.log("info", "[play] %s" % raw[:100])
        if raw.startswith("http"):
            url = await _resolve_m3u8(raw)
        else:
            data = await _api("/movie?id=%s" % quote(raw))
            info = ((data or {}).get("data") or {}).get("info") or {}
            if not info and isinstance((data or {}).get("data"), dict):
                info = data["data"]
            url = (info.get("play_url") or "").strip()
            if url:
                url = await _resolve_m3u8(url)
        headers = {"User-Agent": UA, "Referer": _host + "/"}
        parse = 0 if url and any(x in url.lower() for x in (".m3u8", ".mp4")) else 1
        return {
            "urls": [{"name": "播放", "url": url}] if url else [],
            "flag": flag,
            "header": headers,
            "parse": parse,
        }
    except Exception as e:
        await OmniBox.log("error", "[play] 失败: %s" % e)
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
