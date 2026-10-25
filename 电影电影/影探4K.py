# -*- coding: utf-8 -*-
# @name 影探4K
# @version 1.1.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%94%B5%E5%BD%B1%E7%94%B5%E8%A7%86/影探4K.py
# @dependencies cryptography,pycryptodome
# @description 影探4K/lyyytv CMS 源（OmniBox）：app API、lvdou 解密、ldmax 解析兜底

"""
影探4K — OmniBox 适配版 v1.1.0
站点 CMS: http://cms.lyyytv.cn
保留 lvdou AES 解密；多组 JSON 解析轮询；失败则回退网页解析(jx)。
"""

import re
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

HOST = "http://cms.lyyytv.cn"
CMSKEY = "wP5bvxoc3yv7FoBQENFZuAF0EUYr4LTy"
# 内置 JSON 解析接口（按顺序尝试，返回 {code:200, url:...}）
PARSE_APIS = [
    "http://61.184.23.217:6163/api/index?parsesId=4&appid=10001&videoUrl=",
    "https://api.tyun77.cn/api.php/provide/parseDicturl?url=",
    "https://play.fuqizhishi.com/mov/API.php?appkey=QQ172598364&url=",
]
# 网页解析前缀（JSON 全失败时，交给壳子 parse=1 + jx）
WEB_JX = [
    "https://jx.xmflv.cc/?url=",
    "https://im1907.top/?jx=",
    "https://bfq.txnp.cn/player?url=",
    "https://jx.lxyy.club/index.php?url=",
]
UA = "okhttp/4.12.0"
PARSE_UA = "okhttp-okgo/jeasonlzy"
HEADERS = {"User-Agent": UA}


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _aes_cbc_decrypt(data, key, iv):
    last_err = None
    if _HAS_CRYPTOGRAPHY:
        try:
            decryptor = _Cipher(_algorithms.AES(key), _modes.CBC(iv)).decryptor()
            plain = decryptor.update(data) + decryptor.finalize()
            unpadder = _padding.PKCS7(128).unpadder()
            return unpadder.update(plain) + unpadder.finalize()
        except Exception as e:
            last_err = e
    if _HAS_PYCRYPTODOME:
        try:
            cipher = _AES.new(key, _AES.MODE_CBC, iv)
            return _unpad(cipher.decrypt(data), 16)
        except Exception as e:
            last_err = e
    raise RuntimeError("AES 解密失败: %s" % last_err)


def _lvdou(text):
    """解密 lvdou+ 前缀的播放地址。"""
    original = text or ""
    if not original.startswith("lvdou+"):
        return original
    key = CMSKEY[:16].encode("utf-8")
    iv = CMSKEY[-16:].encode("utf-8")
    try:
        ct = base64.b64decode(original[6:])
        pt = _aes_cbc_decrypt(ct, key, iv)
        return pt.decode("utf-8", "ignore")
    except Exception:
        return original


def _ldmax_decrypt(encrypted_base64, depth=0):
    """递归解密 ldmax.cooom 加密链接。"""
    if depth > 5:
        return None
    cleaned = re.sub(r"\s+", "", encrypted_base64 or "")
    try:
        decoded = base64.b64decode(cleaned, validate=True).decode("utf-8", "ignore")
    except Exception:
        return encrypted_base64
    url = re.sub(r"\s+", "", decoded)
    if "ldmax.cooom" not in url:
        return url
    path = re.sub(r"https?://ldmax\.cooom/", "", url)
    if len(path) < 16:
        return None
    key = path[:16][::-1].encode("utf-8")
    try:
        ciphertext = base64.b64decode(re.sub(r"\s+", "", path[16:]), validate=True)
    except Exception:
        return None
    try:
        plain = _aes_cbc_decrypt(ciphertext, key, key)
        result = plain.decode("utf-8", "ignore").strip()
    except Exception:
        return None
    if "ldmax.cooom" in result:
        return _ldmax_decrypt(base64.b64encode(result.encode("utf-8")).decode("utf-8"), depth + 1)
    return result


def _extract_play_url(resp):
    """从常见解析 JSON 结构中取出播放地址。"""
    if not isinstance(resp, dict):
        return ""
    # 直接 url
    for key in ("url", "play", "play_url", "video", "src"):
        v = resp.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
    data = resp.get("data")
    if isinstance(data, str) and data.startswith("http"):
        return data
    if isinstance(data, dict):
        for key in ("url", "play", "play_url", "video", "src"):
            v = data.get(key)
            if isinstance(v, str) and v.startswith("http"):
                return v
        if isinstance(data.get("url"), list) and data["url"]:
            first = data["url"][0]
            if isinstance(first, str) and first.startswith("http"):
                return first
            if isinstance(first, dict) and str(first.get("url") or "").startswith("http"):
                return first["url"]
    return ""


async def _json_parse(video_url):
    """轮询 JSON 解析接口，成功返回直链。"""
    decrypted = _ldmax_decrypt(video_url) or video_url
    if not decrypted or not re.match(r"^https?://", str(decrypted)):
        decrypted = video_url
    for api in PARSE_APIS:
        try:
            parse_url = api + quote(str(decrypted), safe="")
            res = await OmniBox.request(
                parse_url,
                {
                    "method": "GET",
                    "headers": {
                        "User-Agent": PARSE_UA,
                        "Accept": "application/json, text/plain, */*",
                    },
                    "timeout": 12,
                },
            )
            text = (res.get("body") or "").strip()
            if not text.startswith("{"):
                continue
            resp = json.loads(text)
            code = resp.get("code")
            if code not in (None, 200, 1, "200", "1"):
                # 部分接口无 code 字段
                if not _extract_play_url(resp):
                    continue
            final_url = _extract_play_url(resp)
            if not final_url:
                continue
            # 可能仍是 ldmax 密文
            final2 = _ldmax_decrypt(final_url) or final_url
            if final2 and re.match(r"^https?://", str(final2)):
                await OmniBox.log("info", "[parse] 命中 %s" % api[:40])
                return str(final2)
        except Exception as e:
            await OmniBox.log("warn", "[parse] %s 失败: %s" % (api[:30], e))
            continue
    return None


async def _ldmax_parse(video_url):
    """兼容旧名：走 JSON 解析轮询。"""
    return await _json_parse(video_url)


def _is_media(url):
    low = (url or "").lower()
    return any(x in low for x in (".mp4", ".m3u8", ".flv", ".mkv", ".ts", ".mov", ".webm"))


async def _api(path, timeout=15):
    url = path if path.startswith("http") else HOST + path
    res = await OmniBox.request(
        url,
        {"method": "GET", "headers": HEADERS, "timeout": timeout},
    )
    text = res.get("body") or ""
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def _card(item):
    return {
        "vod_id": str(item.get("vod_id") or item.get("id") or ""),
        "vod_name": str(item.get("vod_name") or "").strip(),
        "vod_pic": str(item.get("vod_pic") or ""),
        "vod_remarks": str(item.get("vod_remarks") or item.get("vod_score") or ""),
    }


def _build_filters(type_extend):
    keys = ["class", "area", "lang", "year", "letter", "by", "sort"]
    names = {
        "class": "类型", "area": "地区", "lang": "语言", "year": "年份",
        "letter": "字母", "by": "排序", "sort": "排序",
    }
    groups = []
    for key in keys:
        raw = (type_extend or {}).get(key) or ""
        if not str(raw).strip():
            continue
        values = [{"n": "全部", "v": ""}]
        for v in str(raw).split(","):
            v = v.strip()
            if v:
                values.append({"n": v, "v": v})
        groups.append({"key": key, "name": names.get(key, key), "value": values})
    return groups


async def home(params, context):
    try:
        await OmniBox.log("info", "[home] from=%s" % (context or {}).get("from", "web"))
        nav = await _api("/api.php/app/nav?token=")
        classes = []
        filters = {}
        for item in nav.get("list") or []:
            tid = str(item.get("type_id") or "")
            name = str(item.get("type_name") or "").strip()
            if not tid or not name:
                continue
            classes.append({"type_id": tid, "type_name": name})
            f = _build_filters(item.get("type_extend") or {})
            if f:
                filters[tid] = f

        videos = []
        idx = await _api("/api.php/app/index_video?token=")
        for group in idx.get("list") or []:
            for it in group.get("vlist") or []:
                c = _card(it)
                if c["vod_id"] and c["vod_name"]:
                    videos.append(c)
        return {"class": classes, "list": videos[:48], "filters": filters}
    except Exception as e:
        await OmniBox.log("error", "[home] 失败: %s" % e)
        return {"class": [], "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "1")
        page = _to_int((params or {}).get("page"), 1) or 1
        extend = (params or {}).get("filters") or {}
        await OmniBox.log("info", "[category] id=%s page=%s" % (tid, page))
        qs = ["tid=%s" % quote(tid), "pg=%s" % page, "limit=18"]
        for key in ("class", "area", "lang", "year"):
            val = extend.get(key) if isinstance(extend, dict) else None
            if val:
                qs.append("%s=%s" % (key, quote(str(val))))
        data = await _api("/api.php/app/video?" + "&".join(qs))
        items = [_card(it) for it in (data.get("list") or []) if it]
        items = [x for x in items if x["vod_id"] and x["vod_name"]]
        pagecount = _to_int(data.get("pagecount"), page) or page
        return {
            "list": items,
            "page": _to_int(data.get("page"), page) or page,
            "pagecount": pagecount,
            "limit": _to_int(data.get("limit"), 18) or 18,
            "total": _to_int(data.get("total"), 0),
        }
    except Exception as e:
        await OmniBox.log("error", "[category] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 18}


async def detail(params, context):
    try:
        vid = str((params or {}).get("videoId") or "").strip()
        if not vid:
            return {"list": []}
        await OmniBox.log("info", "[detail] %s" % vid)
        raw = await _api("/api.php/app/video_detail?id=%s" % quote(vid))
        data = raw.get("data") or {}
        if not data:
            return {"list": []}

        vod = {
            "vod_id": str(data.get("vod_id") or vid),
            "vod_name": str(data.get("vod_name") or "").strip(),
            "vod_pic": str(data.get("vod_pic") or ""),
            "vod_year": str(data.get("vod_year") or ""),
            "vod_area": str(data.get("vod_area") or ""),
            "vod_remarks": str(data.get("vod_remarks") or data.get("vod_score") or ""),
            "vod_actor": str(data.get("vod_actor") or ""),
            "vod_director": str(data.get("vod_director") or ""),
            "vod_content": str(data.get("vod_content") or ""),
        }

        sources = []
        for i, line in enumerate(data.get("vod_url_with_player") or []):
            if not isinstance(line, dict):
                continue
            line_name = str(line.get("name") or ("线路%s" % (i + 1))).strip()
            episodes = []
            for j, seg in enumerate(str(line.get("url") or "").split("#")):
                seg = seg.strip()
                if not seg:
                    continue
                if "$" in seg:
                    name, play_id = seg.split("$", 1)
                    play_id = _lvdou(play_id.strip())
                    name = name.strip() or ("第%s集" % (j + 1))
                else:
                    name, play_id = "第%s集" % (j + 1), _lvdou(seg)
                if play_id:
                    episodes.append({"name": name, "playId": play_id})
            if episodes:
                sources.append({"name": line_name, "episodes": episodes})

        if sources:
            vod["vod_play_sources"] = sources
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] 失败: %s" % e)
        return {"list": []}


async def search(params, context):
    try:
        key = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 20}
        await OmniBox.log("info", "[search] %s page=%s" % (key, page))
        data = await _api(
            "/api.php/app/search?text=%s&pg=%s" % (quote(key), page)
        )
        items = []
        for it in data.get("list") or []:
            c = _card(it)
            if c["vod_id"] and c["vod_name"]:
                items.append(c)
        return {
            "list": items,
            "page": page,
            "pagecount": page + 1 if len(items) >= 10 else page,
            "limit": 20,
            "total": len(items),
        }
    except Exception as e:
        await OmniBox.log("error", "[search] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 20}


def _is_official(url):
    low = (url or "").lower()
    return any(
        d in low
        for d in (
            "iqiyi.com", "qiyi.com", "youku.com", "v.qq.com", "qq.com/x/cover",
            "mgtv.com", "bilibili.com", "pptv.com", "sohu.com", "le.com", "1905.com",
        )
    )


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            raise ValueError("playId 为空")
        play_id = re.sub(r"%[0-9A-Fa-f]{2}", "", play_id)
        await OmniBox.log("info", "[play] %s" % play_id[:120])

        url = play_id
        is_http = url.startswith(("http://", "https://"))
        headers = dict(HEADERS)

        # 1) 已是媒体直链
        if is_http and _is_media(url):
            return {
                "urls": [{"name": "播放", "url": url}],
                "flag": flag,
                "header": headers,
                "parse": 0,
            }

        # 2) 密文 / 本站伪直链 / 官站 → 先试 JSON 解析拿直链
        need_parse = (not is_http) or (is_http and ("lyyytv.cn" in url or _is_official(url)))
        if need_parse:
            parsed = await _json_parse(url)
            if parsed and _is_media(parsed):
                return {
                    "urls": [{"name": "播放", "url": parsed}],
                    "flag": flag,
                    "header": headers,
                    "parse": 0,
                }
            if parsed and parsed.startswith("http"):
                url = parsed

        # 3) 官站：交给壳子用网页解析（jx 前缀）
        if _is_official(url) or (is_http and not _is_media(url)):
            jx = WEB_JX[0] if WEB_JX else ""
            return {
                "urls": [{"name": "播放", "url": url}],
                "flag": flag,
                "header": headers,
                "parse": 1,
                "jx": jx,
            }

        # 4) 其它
        parse = 0 if _is_media(url) else 1
        result = {
            "urls": [{"name": "播放", "url": url}] if url else [],
            "flag": flag,
            "header": headers,
            "parse": parse,
        }
        if parse == 1 and WEB_JX:
            result["jx"] = WEB_JX[0]
        return result
    except Exception as e:
        await OmniBox.log("error", "[play] 失败: %s" % e)
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
