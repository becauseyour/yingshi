# -*- coding: utf-8 -*-
# @name 野果短剧
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/Silent1566/OmniBox-Spider/main/短剧/野果短剧.py
# @indexs 1
# @dependencies pycryptodome
# @description 野果短剧站源（OmniBox 适配版）：AES 解密 API、分类/搜索/播放

import re
import json
import base64
from urllib.parse import quote

from spider_runner import OmniBox, run

try:
    from Crypto.Cipher import AES
except Exception:
    AES = None

SITE_URL = "https://www.yeguodj.com"
API_BASE = "https://www.yeguodj.com/api.php"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
API_KEY = b"2acf7e91e9864673"
API_IV = b"1c29882d3ddfcfd6"


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def aes_cbc_decrypt(cipher_bytes, key_bytes, iv_bytes):
    if not AES or not cipher_bytes or len(cipher_bytes) % 16 != 0:
        return b""
    try:
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
        raw = cipher.decrypt(cipher_bytes)
        if raw:
            pad = raw[-1]
            if 1 <= pad <= 16:
                return raw[:-pad]
        return raw
    except Exception:
        return b""


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
            "timeout": 10,
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
            raw_cipher = base64.b64decode(data_val)
            dec = aes_cbc_decrypt(raw_cipher, API_KEY, API_IV)
            if dec:
                d["data"] = json.loads(dec.decode("utf-8", "ignore"))
        except Exception:
            pass
    return d


def _unwrap(d):
    if not d:
        return {}
    x = d.get("data") if d.get("data") is not None else d
    if isinstance(x, dict) and x.get("data") is not None and isinstance(x.get("data"), dict):
        return x.get("data")
    return x


def _to_vod(it):
    if not it:
        return None
    vid = str(it.get("video_id") if it.get("video_id") is not None else (it.get("id") or "")).strip()
    if not vid:
        return None
    title = str(it.get("title") or it.get("video_title") or it.get("name") or vid).strip()
    raw_pic = str(it.get("cover") or it.get("cover_img") or it.get("pic") or "").strip()
    ep = it.get("episode_count") or it.get("episodes") or it.get("total_serial") or ""
    remark = str(it.get("update_status") or it.get("serialize_status_text") or "").strip()
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
    elif isinstance(inner, list):
        arr = inner
    out = []
    for it in arr:
        v = _to_vod(it)
        if v:
            out.append(v)
    return out


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


async def home(params, context):
    try:
        await OmniBox.log("info", f"[home] from={(context or {}).get('from', 'web')}")
        d = await _api_post("/api/home/homePage", {})
        inner = _unwrap(d)
        combined = []
        if isinstance(inner, dict):
            combined.extend(inner.get("top_list") or [])
            mods = (inner.get("modules") or {}).get("list") or []
            for m in mods:
                if isinstance(m, dict):
                    if isinstance(m.get("list"), list):
                        combined.extend(m.get("list"))
                    elif m.get("video_id"):
                        combined.append(m)
        seen, v_list = set(), []
        for it in combined:
            v = _to_vod(it)
            if v and v["vod_id"] not in seen:
                seen.add(v["vod_id"])
                v_list.append(v)
        return {"class": CLASSES, "list": v_list[:30], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "explore").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        await OmniBox.log("info", f"[category] categoryId={tid}, page={page}")
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
            "pagecount": page + 1 if len(v_list) >= 24 else page,
            "limit": 24,
            "total": 9999,
            "list": v_list,
        }
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 24}


async def detail(params, context):
    try:
        vid = str((params or {}).get("videoId") or "").strip()
        if not vid:
            return {"list": []}
        await OmniBox.log("info", f"[detail] videoId={vid}")
        v_num = int(vid) if vid.isdigit() else vid
        d = await _api_post("/api/playlet/detail", {"video_id": v_num})
        info = _unwrap(d)
        if isinstance(info, dict) and info.get("video_id") is None and isinstance(info.get("data"), dict):
            info = info.get("data")
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
            for i in range(1, total_cnt + 1):
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
        await OmniBox.log("error", f"[detail] 失败: {e}")
        return {"list": []}


async def search(params, context):
    try:
        kw = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not kw:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 0}
        await OmniBox.log("info", f"[search] keyword={kw}, page={page}")
        d = await _api_post("/api/search/result", {"keyword": kw, "page": page})
        v_list = _list_from_payload(d)
        return {
            "page": page,
            "pagecount": page + 1 if len(v_list) >= 20 else page,
            "limit": len(v_list),
            "total": 9999,
            "list": v_list,
        }
    except Exception as e:
        await OmniBox.log("error", f"[search] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 0}


async def play(params, context):
    try:
        raw = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not raw:
            raise ValueError("playId 为空")
        await OmniBox.log("info", f"[play] playId={raw}")
        parts = raw.split(":")
        vid = parts[0]
        ep = parts[1] if len(parts) > 1 else "1"
        v_num = int(vid) if vid.isdigit() else vid
        ep_num = int(ep) if ep.isdigit() else ep
        d = await _api_post("/api/playlet/play", {"video_id": v_num, "ep": ep_num})
        info = _unwrap(d)
        if isinstance(info, dict) and info.get("video_url") is None and isinstance(info.get("data"), dict):
            info = info.get("data")
        target_ep = str(ep).strip()
        episode_all = info.get("episodeAll")
        video_url = ""
        if isinstance(episode_all, list) and episode_all:
            for idx, episode in enumerate(episode_all):
                if not isinstance(episode, dict):
                    continue
                episode_no = str(
                    episode.get("sort") or episode.get("episode") or episode.get("index") or (idx + 1)
                ).strip()
                if episode_no == target_ep:
                    video_url = str(episode.get("video_url") or "").strip()
                    break
            if not video_url and str(info.get("episode_sort") or "").strip() == target_ep:
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
        await OmniBox.log("error", f"[play] 失败: {e}")
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
