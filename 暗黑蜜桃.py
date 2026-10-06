# -*- coding: utf-8 -*-
# @name 暗黑蜜桃
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/Silent1566/OmniBox-Spider/main/影视/采集/暗黑蜜桃.py
# @indexs 1
# @description 蜜桃站源（OmniBox 适配版）：握手鉴权 + HMAC 签名，支持视频/短剧/动漫/国产/黑料/直播分类

"""
暗黑蜜桃 — OmniBox 适配版

原 T3 接口已统一为 OmniBox handler 签名 (params, context)。
站点: https://honeypeach.cc/
核心逻辑（握手 challenge、HMAC 签名请求）原样保留。
"""

import json
import time
import random
import hashlib
import hmac
import urllib.parse
import gzip
import zlib

from spider_runner import OmniBox, run

SITE_URL = "https://honeypeach.cc"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# 模块级会话状态（握手 sid / skey）
# ---------------------------------------------------------------------------
_dev_id = "%x%x" % (random.randint(10000000, 99999999), int(time.time() * 1000))
_sid = ""
_skey = ""
_sk_exp = 0


# ---------------------------------------------------------------------------
# 签名 / 握手工具
# ---------------------------------------------------------------------------
def _hp_hash(s):
    h = 0x811C9DC5
    for ch in s:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def _hp_pow(chal, nonce):
    h = _hp_hash("%s:%s" % (chal, nonce))
    for _ in range(4):
        hex_str = ("%08x" % h)[-8:]
        h = _hp_hash(hex_str + chal)
    return ("%08x" % h)[-8:]


def _hp_solve(chal, bits=16):
    want = "0" * (bits >> 2)
    n = 0
    while n < 20000000:
        nx = hex(n)[2:]
        hx = _hp_pow(chal, nx)
        if hx.startswith(want):
            return "%s.%s" % (chal, nx)
        n += 1
    return ""


async def _raw_fetch(url, method="GET", headers=None, body=None, timeout=8):
    req_headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": SITE_URL + "/",
        "Connection": "close",
    }
    if headers:
        req_headers.update(headers)

    opts = {
        "method": method.upper(),
        "headers": req_headers,
        "timeout": timeout,
    }
    if body is not None:
        opts["body"] = body if isinstance(body, str) else body.decode("utf-8", "ignore")

    try:
        res = await OmniBox.request(url, opts)
        status = res.get("statusCode") or 0
        text = res.get("body") or ""
        # 部分环境可能返回 bytes
        if isinstance(text, bytes):
            try:
                text = gzip.decompress(text).decode("utf-8", "ignore")
            except Exception:
                try:
                    text = zlib.decompress(text).decode("utf-8", "ignore")
                except Exception:
                    text = text.decode("utf-8", "ignore")
        return {"status": status, "content": text, "error": ""}
    except Exception as e:
        return {"status": 0, "content": "", "error": str(e)}


async def _ensure_handshake():
    global _sid, _skey, _sk_exp
    now = int(time.time())
    if _sid and _skey and now < (_sk_exp - 60):
        return True

    hs_url = urllib.parse.urljoin(SITE_URL, "/api/handshake?dev=" + urllib.parse.quote(_dev_id))
    res = await _raw_fetch(hs_url, method="GET", timeout=6)
    if res["status"] != 200 or not res["content"]:
        return False

    try:
        d = json.loads(res["content"])
    except Exception:
        return False

    if d.get("need_chal"):
        chal = d["need_chal"]
        bits = int(d.get("bits", 16))
        tok = _hp_solve(chal, bits)
        if not tok:
            return False
        chal_url = hs_url + "&c=" + urllib.parse.quote(tok)
        res = await _raw_fetch(chal_url, method="GET", timeout=6)
        if res["status"] != 200 or not res["content"]:
            return False
        try:
            d = json.loads(res["content"])
        except Exception:
            return False

    if d.get("sid") and d.get("skey"):
        _sid = d["sid"]
        _skey = d["skey"]
        _sk_exp = int(d.get("exp", 0))
        return True
    return False


async def _signed_fetch(path, method="GET", params=None, body=None, timeout=8):
    global _sid, _skey
    if not await _ensure_handshake():
        url = urllib.parse.urljoin(SITE_URL, path)
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return await _raw_fetch(url, method=method, timeout=timeout)

    query_str = urllib.parse.urlencode(params) if params else ""
    body_str = json.dumps(body) if body is not None else ""
    body_bytes = body_str.encode("utf-8") if body_str else None

    body_hash = hashlib.sha256(body_str.encode("utf-8") if body_str else b"").hexdigest()
    ts = "%d" % int(time.time())
    nonce = "%x%x" % (random.randint(100000, 999999), int(time.time() * 1000))

    canon = "%s\n%s\n%s\n%s\n%s\n%s\n%s" % (
        method.upper(),
        path,
        query_str,
        body_hash,
        ts,
        nonce,
        _sid,
    )

    try:
        key_bytes = bytes.fromhex(_skey)
        sig = hmac.new(key_bytes, canon.encode("utf-8"), hashlib.sha256).hexdigest()
    except Exception:
        sig = ""

    req_headers = {
        "X-Hp-Sid": _sid,
        "X-Hp-Ts": ts,
        "X-Hp-Nonce": nonce,
        "X-Hp-Sign": sig,
    }
    if body_bytes:
        req_headers["Content-Type"] = "application/json"

    full_url = urllib.parse.urljoin(SITE_URL, path)
    if query_str:
        full_url += "?" + query_str

    res = await _raw_fetch(
        full_url,
        method=method,
        headers=req_headers,
        body=body_str if body_str else None,
        timeout=timeout,
    )
    if res["status"] == 401:
        _sid = ""
        _skey = ""
        if await _ensure_handshake():
            return await _signed_fetch(path, method=method, params=params, body=body, timeout=timeout)
    return res


def _format_cover(mod, url):
    if not url:
        return ""
    if mod == "live" or url.startswith("/") or "://" not in url:
        if url.startswith("/"):
            return urllib.parse.urljoin(SITE_URL, url)
        return url
    return urllib.parse.urljoin(SITE_URL, "/cover/%s?u=%s" % (mod, urllib.parse.quote(url)))


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def home(params, context):
    try:
        from_val = (context or {}).get("from", "web")
        await OmniBox.log("info", f"[home] from={from_val}")

        classes = [
            {"type_id": "video", "type_name": "蜜桃视频"},
            {"type_id": "duanju", "type_name": "蜜桃短剧"},
            {"type_id": "caibian", "type_name": "擦边短剧"},
            {"type_id": "shortv", "type_name": "蜜桃动漫"},
            {"type_id": "guochan", "type_name": "国产精品"},
            {"type_id": "heiliao", "type_name": "黑料吃瓜"},
            {"type_id": "live", "type_name": "蜜桃直播"},
        ]

        filters = {
            "video": [
                {
                    "key": "cat",
                    "name": "分类",
                    "value": [
                        {"n": "最近更新", "v": "new"},
                        {"n": "新作上市", "v": "release"},
                        {"n": "中文字幕", "v": "chinese-subtitle"},
                        {"n": "麻豆传媒", "v": "madou"},
                        {"n": "无码流出", "v": "uncensored-leak"},
                        {"n": "FC2", "v": "fc2"},
                        {"n": "热门", "v": "monthly-hot"},
                        {"n": "VR", "v": "genres/VR"},
                        {"n": "HEYZO", "v": "heyzo"},
                        {"n": "东京热", "v": "tokyohot"},
                        {"n": "一本道", "v": "1pondo"},
                        {"n": "Caribbeancom", "v": "caribbeancom"},
                        {"n": "Caribbeancompr", "v": "caribbeancompr"},
                        {"n": "SIRO", "v": "siro"},
                        {"n": "LUXU", "v": "luxu"},
                        {"n": "TWAV", "v": "twav"},
                        {"n": "Furuke", "v": "furuke"},
                        {"n": "今日热门", "v": "today-hot"},
                        {"n": "本週热门", "v": "weekly-hot"},
                    ],
                }
            ],
            "duanju": [
                {
                    "key": "cat",
                    "name": "板块",
                    "value": [
                        {"n": "精选", "v": "all"},
                        {"n": "赤果短剧", "v": "chiguo"},
                        {"n": "魔改短剧", "v": "mod"},
                        {"n": "黄豆原创", "v": "yuandou"},
                        {"n": "真人短剧", "v": "zhenren"},
                        {"n": "动漫", "v": "erciyuan"},
                        {"n": "影院", "v": "aiman"},
                        {"n": "推荐", "v": "tuijian"},
                        {"n": "AI成人短剧", "v": "duanju"},
                        {"n": "AI成人漫剧", "v": "manju"},
                        {"n": "AI换脸", "v": "huanlian"},
                        {"n": "AI魔改", "v": "mogai"},
                        {"n": "排行榜", "v": "rank"},
                        {"n": "怦然心动", "v": "pengran"},
                    ],
                }
            ],
            "caibian": [
                {
                    "key": "cat",
                    "name": "排序",
                    "value": [
                        {"n": "最新", "v": "0"},
                        {"n": "推荐", "v": "1"},
                        {"n": "全部", "v": "2"},
                    ],
                }
            ],
            "shortv": [
                {
                    "key": "cat",
                    "name": "源频道",
                    "value": [
                        {"n": "全部", "v": "all"},
                        {"n": "Hanime", "v": "Hanime"},
                        {"n": "NaughtyMachinima", "v": "NaughtyMachinima"},
                        {"n": "HS日本4K动漫", "v": "HS日本4K动漫"},
                    ],
                }
            ],
            "heiliao": [
                {
                    "key": "cat",
                    "name": "频道",
                    "value": [
                        {"n": "最新", "v": "0"},
                        {"n": "推荐", "v": "1"},
                    ],
                }
            ],
            "live": [
                {
                    "key": "cat",
                    "name": "分类与地区",
                    "value": [
                        {"n": "女主播", "v": "girls"},
                        {"n": "情侣", "v": "couples"},
                        {"n": "男主播", "v": "men"},
                        {"n": "跨性别", "v": "trans"},
                        {"n": "中国", "v": "cn"},
                        {"n": "日本", "v": "jp"},
                        {"n": "韩国", "v": "kr"},
                        {"n": "美国", "v": "us"},
                        {"n": "泰国", "v": "th"},
                        {"n": "越南", "v": "vn"},
                        {"n": "俄罗斯", "v": "ru"},
                    ],
                }
            ],
        }

        return {"class": classes, "list": [], "filters": filters}
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {"class": [], "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "video")
        page = _to_int((params or {}).get("page"), 1) or 1
        extend = (params or {}).get("filters") or {}
        cat = str(extend.get("cat") or "")

        await OmniBox.log("info", f"[category] categoryId={tid}, page={page}, cat={cat}")

        src_map = {
            "video": "missav",
            "shortv": "dongman",
            "chiguo": "chiguo",
            "pengran": "pengran",
            "tuijian": "huangguo",
            "duanju": "huangguo",
            "manju": "huangguo",
            "huanlian": "huangguo",
            "mogai": "huangguo",
            "rank": "huangguo",
        }

        src = src_map.get(cat, src_map.get(tid, "huangdou"))
        if tid == "guochan":
            src = "guochan"

        req_params = {"key": tid, "page": page}
        if cat:
            req_params["cat"] = cat
        if src:
            req_params["src"] = src
        if extend.get("sub"):
            req_params["sub"] = extend.get("sub")
        if extend.get("nav"):
            req_params["nav"] = extend.get("nav")

        res = await _signed_fetch("/api/module", params=req_params, timeout=10)

        cards = []
        has_more = False
        pagecount = page

        try:
            data = json.loads(res["content"])
            raw_list = data.get("list", [])
            has_more = bool(data.get("has_more", False))
            if has_more:
                pagecount = page + 1

            cover_mod = src if tid == "duanju" else tid
            for item in raw_list:
                item_id = str(item.get("id") or item.get("code") or "")
                if not item_id:
                    continue
                title = str(item.get("title") or item_id).strip()
                cover_url = item.get("cover_n") or item.get("cover") or ""
                pic = _format_cover(cover_mod, cover_url)
                raw_remark = item.get("remark") or item.get("desc") or ""
                remarks = ("蜜桃 | %s" % raw_remark.strip()) if raw_remark else "蜜桃"
                cards.append(
                    {
                        "vod_id": "%s@@%s@@%s" % (tid, item_id, src),
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": remarks,
                    }
                )
        except Exception as e:
            await OmniBox.log("error", f"[category] 解析失败: {e}")

        return {
            "list": cards,
            "page": page,
            "pagecount": pagecount,
            "limit": len(cards) or 20,
            "total": 9999 if has_more else (page * len(cards)),
        }
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"page": 1, "pagecount": 0, "total": 0, "list": []}


async def detail(params, context):
    try:
        video_id = str((params or {}).get("videoId") or "")
        if not video_id:
            return {"list": []}

        await OmniBox.log("info", f"[detail] videoId={video_id}")

        parts = video_id.split("@@")
        mod = parts[0]
        real_id = parts[1] if len(parts) > 1 else video_id
        src = parts[2] if len(parts) > 2 else ""

        detail_path = "/api/detail/%s/%s" % (mod, urllib.parse.quote(real_id))
        req_params = {}
        if src:
            req_params["src"] = src

        res = await _signed_fetch(detail_path, params=req_params, timeout=10)

        vod = {
            "vod_id": video_id,
            "vod_name": real_id,
            "vod_pic": "",
            "vod_year": "",
            "vod_area": "蜜桃",
            "vod_remarks": "蜜桃",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
        }

        episodes = []
        try:
            data = json.loads(res["content"])
            det = data.get("detail", {})
            if det:
                title = det.get("title") or real_id
                vod["vod_name"] = str(title).strip()

                cover_mod = src if mod == "duanju" else mod
                cover_raw = det.get("cover") or ""
                pic_url = _format_cover(cover_mod, cover_raw)
                vod["vod_pic"] = pic_url

                if det.get("date"):
                    vod["vod_year"] = str(det["date"])

                raw_desc = det.get("desc") or ""
                vod["vod_content"] = str(raw_desc)

                ep_list = det.get("episodes", [])
                if ep_list:
                    for ep_item in ep_list:
                        ep_no = str(ep_item.get("ep", "1"))
                        raw_name = str(ep_item.get("name") or ("第%s集" % ep_no))
                        if raw_name.isdigit():
                            raw_name = "第%s集" % raw_name
                        is_lock = ep_item.get("lock")
                        ep_display = ("%s[预告10s]" % raw_name) if is_lock else raw_name
                        play_token = "%s@@%s@@%s@@%s" % (mod, real_id, ep_no, src)
                        episodes.append({"name": ep_display, "playId": play_token})
                else:
                    play_token = "%s@@%s@@1@@%s" % (mod, real_id, src)
                    episodes.append({"name": "正片", "playId": play_token})
        except Exception as e:
            await OmniBox.log("error", f"[detail] 解析失败: {e}")
            play_token = "%s@@%s@@1@@%s" % (mod, real_id, src)
            episodes.append({"name": "正片", "playId": play_token})

        if episodes:
            vod["vod_play_sources"] = [{"name": "蜜桃专线", "episodes": episodes}]

        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] 失败: {e}")
        return {"list": []}


async def search(params, context):
    try:
        keyword = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not keyword:
            return {"page": 1, "pagecount": 0, "total": 0, "list": []}

        await OmniBox.log("info", f"[search] keyword={keyword}, page={page}")

        search_mods = ["video", "duanju", "shortv", "guochan", "caibian"]
        cards = []

        for mod in search_mods:
            req_params = {"key": mod, "kw": keyword, "page": page}
            res = await _signed_fetch("/api/search", params=req_params, timeout=8)
            try:
                data = json.loads(res["content"])
                raw_list = data.get("list", [])
                for item in raw_list:
                    item_id = str(item.get("id") or item.get("code") or "")
                    if not item_id:
                        continue
                    item_src = str(item.get("src") or mod)
                    title = str(item.get("title") or item_id).strip()
                    cover_url = item.get("cover_n") or item.get("cover") or ""
                    pic = _format_cover(item_src if mod == "duanju" else mod, cover_url)
                    raw_remark = item.get("remark") or item.get("desc") or ""
                    remarks = ("蜜桃 | %s" % raw_remark.strip()) if raw_remark else "蜜桃"
                    cards.append(
                        {
                            "vod_id": "%s@@%s@@%s" % (mod, item_id, item_src),
                            "vod_name": title,
                            "vod_pic": pic,
                            "vod_remarks": remarks,
                        }
                    )
            except Exception:
                continue

        return {
            "list": cards,
            "page": page,
            "pagecount": page + 1 if len(cards) >= 10 else page,
            "limit": len(cards) or 20,
            "total": len(cards),
        }
    except Exception as e:
        await OmniBox.log("error", f"[search] 失败: {e}")
        return {"page": 1, "pagecount": 0, "total": 0, "list": []}


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "")
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            raise ValueError("playId 不能为空")

        await OmniBox.log("info", f"[play] playId={play_id[:80]}, flag={flag}")

        parts = play_id.split("@@")
        mod = parts[0]
        real_id = parts[1] if len(parts) > 1 else play_id
        ep = parts[2] if len(parts) > 2 else "1"
        src = parts[3] if len(parts) > 3 else ""

        play_path = "/api/play/%s/%s/%s" % (mod, urllib.parse.quote(real_id), ep)
        req_params = {}
        if src:
            req_params["src"] = src

        res = await _signed_fetch(play_path, params=req_params, timeout=10)

        final_url = ""
        try:
            data = json.loads(res["content"])
            pl = data.get("play", {})
            raw_src = pl.get("src") or ""
            raw_proxy = pl.get("src_proxy") or ""

            if "preview-r10" in raw_src and raw_proxy:
                chosen = raw_proxy
            else:
                chosen = raw_src or raw_proxy

            if chosen:
                if chosen.startswith("/"):
                    final_url = urllib.parse.urljoin(SITE_URL, chosen)
                else:
                    final_url = chosen
        except Exception as e:
            await OmniBox.log("error", f"[play] 解析失败: {e}")

        if final_url:
            lower_url = final_url.lower()
            if ".m3u8" not in lower_url and ".mp4" not in lower_url and ".mpd" not in lower_url:
                sep = "&" if "?" in final_url else "?"
                final_url = final_url + sep + "format=.m3u8"

        headers = {
            "User-Agent": UA,
            "Referer": SITE_URL + "/",
        }
        if "hembed.com" in final_url or "hanime" in final_url:
            headers["Referer"] = "https://hanime1.me/"

        parse = 0 if any(ext in final_url.lower() for ext in (".m3u8", ".mp4", ".mpd", ".flv")) else 1

        return {
            "urls": [{"name": "播放", "url": final_url}] if final_url else [],
            "flag": flag,
            "header": headers,
            "parse": parse,
        }
    except Exception as e:
        await OmniBox.log("error", f"[play] 失败: {e}")
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run(
        {
            "home": home,
            "category": category,
            "detail": detail,
            "search": search,
            "play": play,
        }
    )
