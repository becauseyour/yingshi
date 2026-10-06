# -*- coding: utf-8 -*-
# @name 采集合集
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/Silent1566/OmniBox-Spider/main/影视/采集/采集合集.py
# @indexs 1
# @dependencies requests
# @description 多站 CMS 聚合采集源：并发搜索、磁盘/内存缓存、成人源过滤

"""
采集合集 — OmniBox 适配版

原 T3 接口 (homeContent/categoryContent/detailContent/searchContent/playerContent)
已统一为 OmniBox handler 签名 (params, context)。

配置方式（任选其一）:
  1. 环境变量 SITE_API 指向 cj.json 地址
  2. extend 参数: "json_url" 或 "json_url|mode"
     mode: 0=全部 / 1=过滤成人 / 2=仅成人
  3. 默认远程地址见 DEFAULT_CJ_JSON

返回结构遵循 OmniBox 规范:
  - detail -> vod_play_sources
  - play   -> {urls, flag, header, parse}
"""

import json
import os
import time
import hashlib
from urllib.parse import urlencode

from spider_runner import OmniBox, run

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
DEFAULT_CJ_JSON = (
    "https://edgeone.gh-proxy.org/https://raw.githubusercontent.com/"
    "wliqi495-create/jaychouqq/refs/heads/main/yingshi/py3/cj.json"
)
DISK_TTL = 3600  # 磁盘缓存 1 小时
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _cache_dir():
    try:
        d = os.path.join(os.path.expanduser("~"), ".lz", "cache")
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        return "/tmp"


CACHE_DIR = _cache_dir()

# ---------------------------------------------------------------------------
# 全局状态（模块级，单次加载后复用）
# ---------------------------------------------------------------------------
_sites = []
_memory_cache = {}
_mode = "0"
_inited = False


async def _ensure_init(extend=""):
    """懒加载站点列表。"""
    global _sites, _mode, _inited
    if _inited and _sites:
        return

    json_path = os.environ.get("SITE_API", "").strip() or DEFAULT_CJ_JSON
    mode = "0"

    if extend:
        if "|" in str(extend):
            parts = str(extend).split("|")
            json_path = parts[0] if parts[0] else json_path
            mode = parts[1] if len(parts) > 1 else "0"
        elif str(extend) in ("0", "1", "2"):
            mode = str(extend)
        else:
            json_path = str(extend)

    _mode = mode
    try:
        if json_path.startswith(("http://", "https://")):
            res = await OmniBox.request(
                json_path,
                {"method": "GET", "headers": {"User-Agent": UA}, "timeout": 10},
            )
            if res.get("statusCode") == 200:
                data = json.loads(res.get("body") or "{}")
                all_sites = data.get("api_site") or []
                _sites = _filter_sites(all_sites, mode)
        else:
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    all_sites = data.get("api_site") or []
                    _sites = _filter_sites(all_sites, mode)
    except Exception as e:
        await OmniBox.log("error", f"[init] 加载配置失败: {e}")

    _inited = True
    await OmniBox.log("info", f"[init] 已加载 {len(_sites)} 个站点, mode={mode}")


def _filter_sites(sites, mode):
    if mode == "0":
        return list(sites or [])
    adult_kws = {"AV", "色", "福利", "成人", "18+", "偷拍", "自拍", "淫", "激情", "GAY", "SEX"}

    def is_adult(name):
        if not name:
            return False
        name_upper = name.upper()
        if name_upper.startswith("AV"):
            return True
        return any(k in name_upper for k in adult_kws)

    if mode == "1":
        return [s for s in (sites or []) if not is_adult(s.get("name", ""))]
    if mode == "2":
        return [s for s in (sites or []) if is_adult(s.get("name", ""))]
    return list(sites or [])


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------
def _disk_key(key):
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def _get_disk_cache(key):
    try:
        path = os.path.join(CACHE_DIR, f"{_disk_key(key)}.json")
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < DISK_TTL:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
    return None


def _set_disk_cache(key, data):
    try:
        if not data or not data.get("list"):
            return
        path = os.path.join(CACHE_DIR, f"{_disk_key(key)}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 网络
# ---------------------------------------------------------------------------
async def _fetch(api_url, params=None, timeout=4.0):
    try:
        qs = urlencode({k: v for k, v in (params or {}).items() if v is not None and v != ""})
        sep = "&" if "?" in api_url else "?"
        full_url = f"{api_url}{sep}{qs}" if qs else api_url
        res = await OmniBox.request(
            full_url,
            {
                "method": "GET",
                "headers": {"User-Agent": UA, "Connection": "keep-alive"},
                "timeout": timeout,
            },
        )
        if res.get("statusCode") == 200:
            body = (res.get("body") or "").strip().lstrip("\ufeff")
            return json.loads(body) if body else {}
    except Exception:
        pass
    return {}


def _map_vod(item, prefix_id=""):
    """标准 VodItem 字段映射。"""
    vod_id = str(item.get("vod_id", ""))
    if prefix_id and "@@" not in vod_id:
        vod_id = f"{prefix_id}@@{vod_id}"
    return {
        "vod_id": vod_id,
        "vod_name": str(item.get("vod_name", "")),
        "vod_pic": str(item.get("vod_pic", "")),
        "type_id": str(item.get("type_id", "")),
        "type_name": str(item.get("type_name", "")),
        "vod_remarks": str(item.get("vod_remarks", "")),
        "vod_year": str(item.get("vod_year", "")),
        "vod_douban_score": str(item.get("vod_douban_score", "")),
    }


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
        extend = (params or {}).get("extend") or os.environ.get("EXTEND", "")
        await _ensure_init(extend)
        from_val = (context or {}).get("from", "web")
        await OmniBox.log("info", f"[home] from={from_val}, sites={len(_sites)}")

        universal_filter = [
            {
                "key": "cateId",
                "name": "分类",
                "value": [
                    {"n": "全部", "v": ""},
                    {"n": "动作片", "v": "动作"},
                    {"n": "喜剧片", "v": "喜剧"},
                    {"n": "爱情片", "v": "爱情"},
                    {"n": "科幻片", "v": "科幻"},
                    {"n": "恐怖片", "v": "恐怖"},
                    {"n": "剧情片", "v": "剧情"},
                    {"n": "战争片", "v": "战争"},
                    {"n": "国产剧", "v": "国产"},
                    {"n": "港剧", "v": "香港"},
                    {"n": "韩剧", "v": "韩国"},
                    {"n": "欧美剧", "v": "欧美"},
                    {"n": "台剧", "v": "台湾"},
                    {"n": "日剧", "v": "日本"},
                    {"n": "纪录片", "v": "记录"},
                    {"n": "动漫", "v": "动漫"},
                    {"n": "综艺", "v": "综艺"},
                ],
            }
        ]

        classes = []
        filters = {}
        for i, s in enumerate(_sites):
            type_id = str(i)
            clean_name = str(s.get("name", f"站点{i}")).replace("TV-", "").replace("AV-", "")
            classes.append({"type_id": type_id, "type_name": clean_name})
            filters[type_id] = universal_filter

        return {"class": classes, "list": [], "filters": filters}
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {"class": [], "list": [], "filters": {}}


async def category(params, context):
    try:
        await _ensure_init()
        category_id = str((params or {}).get("categoryId") or "0")
        page = _to_int((params or {}).get("page"), 1) or 1
        filters = (params or {}).get("filters") or {}
        cate_id_val = str(filters.get("cateId") or "")

        await OmniBox.log(
            "info",
            f"[category] categoryId={category_id}, page={page}, filters={filters}",
        )

        cache_key = f"CAT_{category_id}_{page}_{cate_id_val}"
        cached = _get_disk_cache(cache_key)
        if cached:
            return cached

        idx = int(category_id)
        if idx < 0 or idx >= len(_sites):
            return {"page": page, "pagecount": 0, "total": 0, "list": []}

        site = _sites[idx]
        paichu_str = str(site.get("paichu", ""))
        paichu = set(paichu_str.split(",")) if paichu_str else set()

        data = await _fetch(site["api"], {"ac": "detail", "pg": str(page)}, timeout=4.0)

        video_list = []
        if data and "list" in data:
            for item in data["list"]:
                if str(item.get("type_id")) in paichu:
                    continue
                if cate_id_val:
                    type_name = item.get("type_name", "")
                    if cate_id_val not in type_name:
                        continue
                video_list.append(_map_vod(item, prefix_id=str(idx)))

        result = {
            "page": _to_int(data.get("page"), page) if data else page,
            "pagecount": _to_int(data.get("pagecount"), 1) if data else 1,
            "total": _to_int(data.get("total"), 0) if data else 0,
            "list": video_list,
        }
        _set_disk_cache(cache_key, result)
        return result
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"page": 1, "pagecount": 0, "total": 0, "list": []}


async def detail(params, context):
    try:
        await _ensure_init()
        video_id = str((params or {}).get("videoId") or "")
        if not video_id:
            return {"list": []}

        await OmniBox.log("info", f"[detail] videoId={video_id}")

        if video_id in _memory_cache:
            return _memory_cache[video_id]

        if "@@" not in video_id:
            return {"list": []}

        idx_s, vid = video_id.split("@@", 1)
        idx = int(idx_s)
        if idx < 0 or idx >= len(_sites):
            return {"list": []}

        site = _sites[idx]
        data = await _fetch(site["api"], {"ac": "detail", "ids": vid}, timeout=5.0)
        if not data or "list" not in data or not data["list"]:
            return {"list": []}

        item = data["list"][0]
        vod = _map_vod(item, prefix_id=str(idx))
        vod.update(
            {
                "vod_content": str(item.get("vod_content", "")),
                "vod_actor": str(item.get("vod_actor", "")),
                "vod_director": str(item.get("vod_director", "")),
                "vod_area": str(item.get("vod_area", "")),
            }
        )

        # 拆分 vod_play_url -> vod_play_sources
        play_from = str(item.get("vod_play_from") or "线路1").split("$$$")
        play_url = str(item.get("vod_play_url") or "").split("$$$")
        sources = []
        for i, from_name in enumerate(play_from):
            url_part = play_url[i] if i < len(play_url) else ""
            episodes = []
            if url_part:
                for j, seg in enumerate(url_part.split("#")):
                    parts = seg.strip().split("$")
                    if len(parts) >= 2:
                        episodes.append(
                            {"name": parts[0].strip(), "playId": "$".join(parts[1:]).strip()}
                        )
                    elif parts[0]:
                        episodes.append(
                            {"name": f"第{j + 1}集", "playId": parts[0].strip()}
                        )
            if episodes:
                sources.append({"name": from_name.strip() or f"线路{i + 1}", "episodes": episodes})

        if sources:
            vod["vod_play_sources"] = sources

        result = {"list": [vod]}
        _memory_cache[video_id] = result
        return result
    except Exception as e:
        await OmniBox.log("error", f"[detail] 失败: {e}")
        return {"list": []}


async def search(params, context):
    try:
        await _ensure_init()
        keyword = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not keyword:
            return {"page": 1, "pagecount": 0, "total": 0, "list": []}

        await OmniBox.log("info", f"[search] keyword={keyword}, page={page}")

        cache_key = f"SEARCH_{keyword}"
        cached = _get_disk_cache(cache_key)
        if cached:
            all_list = cached.get("list") or []
            limit = 20
            start = (page - 1) * limit
            chunk = all_list[start : start + limit]
            return {
                "page": page,
                "pagecount": max(1, (len(all_list) + limit - 1) // limit),
                "total": len(all_list),
                "list": chunk,
            }

        search_targets = []
        for i, s in enumerate(_sites):
            bz_val = str(s.get("bz", "1")).strip()
            if bz_val != "0" and s.get("api"):
                search_targets.append((i, s))

        final_list = []
        for idx, site in search_targets:
            try:
                paichu_str = str(site.get("paichu", ""))
                paichu = set(paichu_str.split(",")) if paichu_str else set()
                data = await _fetch(site["api"], {"ac": "detail", "wd": keyword}, timeout=2.5)
                if data and "list" in data:
                    site_name = str(site.get("name", "")).replace("TV-", "").replace("AV-", "")
                    for item in data["list"]:
                        if str(item.get("type_id")) in paichu:
                            continue
                        mapped = _map_vod(item, prefix_id=str(idx))
                        mapped["vod_name"] = f"[{site_name}] {mapped['vod_name']}"
                        final_list.append(mapped)
            except Exception:
                pass

        result_data = {"list": final_list}
        _set_disk_cache(cache_key, result_data)

        limit = 20
        start = (page - 1) * limit
        chunk = final_list[start : start + limit]
        return {
            "page": page,
            "pagecount": max(1, (len(final_list) + limit - 1) // limit) if final_list else 0,
            "total": len(final_list),
            "list": chunk,
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

        parse = 0 if any(ext in play_id.lower() for ext in (".m3u8", ".mp4", ".flv", ".mkv")) else 1
        await OmniBox.log("info", f"[play] playId={play_id[:80]}, flag={flag}, parse={parse}")

        return {
            "urls": [{"name": "播放", "url": play_id}],
            "flag": flag,
            "header": {"User-Agent": UA},
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
