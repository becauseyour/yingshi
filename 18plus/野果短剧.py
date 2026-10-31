# -*- coding: utf-8 -*-
# @name 野果短剧
# @version 1.1.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/野果短剧.py
# @dependencies cryptography,pycryptodome
# @description 野果短剧站源（OmniBox v1.1）：双库 AES、嵌套 data 解包、episodeAll 播放

import json
import base64
from urllib.parse import quote

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
    _HAS_PYCRYPTODOME = True
except Exception:
    pass

SITE_URL = "https://www.yeguodj.com"
API_BASE = "https://www.yeguodj.com/api.php"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
API_KEY = b"2acf7e91e9864673"
API_IV = b"1c29882d3ddfcfd6"

CLASSES = [
    {"type_id": "explore", "type_name": "发现"},
    {"type_id": "rank", "type_name": "排行榜"},
    {"type_id": "dushi", "type_name": "都市"},
    {"type_id": "xiandai", "type_name": "现代"},
    {"type_id": "xiaoyuan", "type_name": "校园"},
    {"type_id": "gudai", "type_name": "古代"},
    {"type_id": "xiangcun", "type_name": "乡村"},
    {"type_id": "zhichang", "type_name": "职场"},
    {"type_id": "chongsheng", "type_name": "重生"},
    {"type_id": "chuanyue", "type_name": "穿越"},
    {"type_id": "xitong", "type_name": "系统"},
    {"type_id": "nixi", "type_name": "逆袭"},
    {"type_id": "mogai", "type_name": "魔改"},
]
BG_MAP = {"dushi": 40, "xiandai": 39, "xiaoyuan": 47, "gudai": 41, "xiangcun": 42, "zhichang": 44}
SETTING_MAP = {"chongsheng": 26, "chuanyue": 27, "xitong": 28, "nixi": 53, "mogai": 56}


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
            decryptor = _Cipher(_algorithms.AES(API_KEY), _modes.CBC(API_IV)).decryptor()
            plain = decryptor.update(data) + decryptor.finalize()
            unpadder = _padding.PKCS7(128).unpadder()
            plain = unpadder.update(plain) + unpadder.finalize()
            return json.loads(plain.decode("utf-8", "ignore"))
        except Exception as e:
            last_err = e
    if _HAS_PYCRYPTODOME:
        try:
            cipher = _AES.new(API_KEY, _AES.MODE_CBC, API_IV)
            raw = cipher.decrypt(data)
            if raw:
                pad = raw[-1]
                if 1 <= pad <= 16:
                    raw = raw[:-pad]
            return json.loads(raw.decode("utf-8", "ignore"))
        except Exception as e:
            last_err = e
    raise RuntimeError("AES 解密失败: %s" % last_err)


async def _api_post(path, body=None):
    url = "%s%s" % (API_BASE, path)
    res = await OmniBox.request(
        url,
        {
            "method": "POST",
            "headers": {
                "User-Agent": UA,
                "Referer": SITE_URL + "/",
                "Origin": SITE_URL,
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json;charset=UTF-8",
            },
            "body": json.dumps(body or {}),
            "timeout": 12,
        },
    )
    text = res.get("body") or ""
    if not text:
        return {}
    try:
        d = json.loads(text)
    except Exception:
        return {}
    data_val = d.get("data")
    if isinstance(data_val, str) and len(data_val) > 20:
        try:
            d["data"] = _aes_decrypt(data_val)
        except Exception as e:
            await OmniBox.log("error", "[api] 解密失败 %s: %s" % (path, e))
    return d


def _unwrap(d):
    """解密后结构: {data: {...业务...}, status, msg} 或 业务字段直接在 data。"""
    if not d:
        return {}
    x = d.get("data") if d.get("data") is not None else d
    # 再包一层 {data: {list/top_list/...}, status}
    if isinstance(x, dict) and isinstance(x.get("data"), dict):
        inner = x["data"]
        if any(k in inner for k in ("list", "top_list", "modules", "title", "video_url", "episodeAll", "episodes")):
            return inner
    return x if isinstance(x, dict) else {}


def _to_vod(it):
    if not it:
        return None
    vid = str(it.get("video_id") if it.get("video_id") is not None else (it.get("id") or "")).strip()
    if not vid:
        return None
    title = str(it.get("title") or it.get("video_title") or it.get("name") or vid).strip()
    raw_pic = str(it.get("cover") or it.get("cover_img") or it.get("pic") or "").strip()
    remark = str(
        it.get("serialize_status_text")
        or it.get("update_status")
        or it.get("play_count_text")
        or ""
    ).strip()
    ep = it.get("episode_count") or it.get("episodes") or it.get("total_serial") or ""
    if not remark and ep:
        remark = "更新至%s集" % ep
    return {
        "vod_id": vid,
        "vod_name": title,
        "vod_pic": raw_pic,
        "vod_remarks": remark,
    }


def _list_from_payload(d):
    inner = _unwrap(d)
    arr = []
    if isinstance(inner, dict):
        arr = inner.get("list") or inner.get("top_list") or []
        # modules.list[].items
        if not arr:
            mods = inner.get("modules") or {}
            mod_list = mods.get("list") if isinstance(mods, dict) else []
            for m in mod_list or []:
                if isinstance(m, dict) and isinstance(m.get("items"), list):
                    arr.extend(m["items"])
                elif isinstance(m, dict) and isinstance(m.get("list"), list):
                    arr.extend(m["list"])
    elif isinstance(inner, list):
        arr = inner
    out, seen = [], set()
    for it in arr:
        v = _to_vod(it)
        if v and v["vod_id"] not in seen:
            seen.add(v["vod_id"])
            out.append(v)
    return out


async def home(params, context):
    try:
        await OmniBox.log(
            "info",
            "[home] crypto=%s/%s" % (_HAS_CRYPTOGRAPHY, _HAS_PYCRYPTODOME),
        )
        if not _HAS_CRYPTOGRAPHY and not _HAS_PYCRYPTODOME:
            await OmniBox.log("error", "[home] 缺少 cryptography 或 pycryptodome")
            return {"class": CLASSES, "list": [], "filters": {}}
        d = await _api_post("/api/home/homePage", {})
        v_list = _list_from_payload(d)
        return {"class": CLASSES, "list": v_list[:30], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[home] 失败: %s" % e)
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "explore").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        await OmniBox.log("info", "[category] %s page=%s" % (tid, page))
        if tid == "rank":
            d = await _api_post("/api/theater/videoRank", {"page": page, "limit": 24})
        elif tid in BG_MAP:
            d = await _api_post(
                "/api/theater/exploreList",
                {"page": page, "limit": 24, "background": BG_MAP[tid]},
            )
        elif tid in SETTING_MAP:
            d = await _api_post(
                "/api/theater/exploreList",
                {"page": page, "limit": 24, "setting": SETTING_MAP[tid]},
            )
        else:
            d = await _api_post("/api/theater/exploreList", {"page": page, "limit": 24})
        v_list = _list_from_payload(d)
        return {
            "page": page,
            "pagecount": page + 1 if len(v_list) >= 20 else page,
            "limit": 24,
            "total": 9999,
            "list": v_list,
        }
    except Exception as e:
        await OmniBox.log("error", "[category] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 24}


async def detail(params, context):
    try:
        vid = str((params or {}).get("videoId") or "").strip()
        if not vid:
            return {"list": []}
        await OmniBox.log("info", "[detail] %s" % vid)
        v_num = int(vid) if vid.isdigit() else vid
        d = await _api_post("/api/playlet/detail", {"video_id": v_num})
        info = _unwrap(d)
        title = str(info.get("title") or vid).strip()
        raw_pic = str(info.get("cover") or info.get("cover_img") or "").strip()
        raw_desc = str(info.get("description") or info.get("intro") or "").strip()
        eps = info.get("episodes") if isinstance(info.get("episodes"), list) else []
        episodes = []
        if eps:
            for idx, ep in enumerate(eps):
                n = str(ep.get("sort") or ep.get("episode") or (idx + 1)).strip()
                t_name = str(ep.get("title") or ("第%s集" % n)).strip()
                t_name = t_name.replace("$", "").replace("#", "")
                episodes.append({"name": t_name, "playId": "%s:%s" % (vid, n)})
        else:
            total_cnt = int(info.get("episode_count") or info.get("total_serial") or 1)
            for i in range(1, max(total_cnt, 1) + 1):
                episodes.append({"name": "第%s集" % i, "playId": "%s:%s" % (vid, i)})
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": raw_pic,
            "vod_remarks": "全%d集" % len(episodes),
            "vod_content": raw_desc,
        }
        if episodes:
            vod["vod_play_sources"] = [{"name": "野果专线", "episodes": episodes}]
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] 失败: %s" % e)
        return {"list": []}


async def search(params, context):
    try:
        kw = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not kw:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 0}
        await OmniBox.log("info", "[search] %s" % kw)
        d = await _api_post("/api/search/result", {"keyword": kw, "page": page})
        v_list = _list_from_payload(d)
        return {
            "page": page,
            "pagecount": page + 1 if len(v_list) >= 20 else page,
            "limit": len(v_list) or 24,
            "total": 9999,
            "list": v_list,
        }
    except Exception as e:
        await OmniBox.log("error", "[search] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 0}


async def play(params, context):
    try:
        raw = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not raw:
            raise ValueError("playId 为空")
        await OmniBox.log("info", "[play] %s" % raw)
        parts = raw.split(":")
        vid = parts[0]
        ep = parts[1] if len(parts) > 1 else "1"
        v_num = int(vid) if vid.isdigit() else vid
        ep_num = int(ep) if str(ep).isdigit() else ep
        d = await _api_post("/api/playlet/play", {"video_id": v_num, "ep": ep_num})
        info = _unwrap(d)
        target_ep = str(ep).strip()
        video_url = ""
        episode_all = info.get("episodeAll")
        if isinstance(episode_all, list) and episode_all:
            for idx, episode in enumerate(episode_all):
                if not isinstance(episode, dict):
                    continue
                episode_no = str(
                    episode.get("sort")
                    or episode.get("episode")
                    or episode.get("index")
                    or (idx + 1)
                ).strip()
                if episode_no == target_ep:
                    video_url = str(episode.get("video_url") or "").strip()
                    break
            if not video_url:
                video_url = str(info.get("video_url") or "").strip()
        else:
            video_url = str(info.get("video_url") or "").strip()
        return {
            "urls": [{"name": "播放", "url": video_url}] if video_url else [],
            "flag": flag,
            "header": {
                "User-Agent": UA,
                "Referer": SITE_URL + "/",
                "Origin": SITE_URL,
            },
            "parse": 0 if video_url else 1,
        }
    except Exception as e:
        await OmniBox.log("error", "[play] 失败: %s" % e)
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
