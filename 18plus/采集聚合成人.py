# -*- coding: utf-8 -*-
# @name 采集聚合成人
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/%E9%87%87%E9%9B%86%E8%81%9A%E5%90%88%E6%88%90%E4%BA%BA.py
# @description 多源成人 MacCMS 聚合（OmniBox）

"""
采集聚合成人 v1.0.0
多资源站 provide/vod 并行聚合；失效源自动跳过
"""

import asyncio
import json
import re
from urllib.parse import quote

from spider_runner import OmniBox, run

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

SOURCES = {
    "s1": {"name": "杏吧资源", "api": "https://xingba111.com/api.php/provide/vod/"},
    "s2": {"name": "极品资源", "api": "https://jipinvip1.com/api.php/provide/vod/"},
    "s3": {"name": "香蕉资源网", "api": "https://www.xiangjiaozyw.com/api.php/provide/vod/"},
    "s4": {"name": "番茄资源", "api": "https://fqzy.me/api.php/provide/vod/"},
    "s6": {"name": "黄色仓库", "api": "https://hsckzy.vip/api.php/provide/vod/"},
    "s7": {"name": "奶香香资源", "api": "https://naixxzy.com/api.php/provide/vod/"},
    "s8": {"name": "桃花资源", "api": "https://thzy1.me/api.php/provide/vod/"},
    "s9": {"name": "CK伦理资源", "api": "https://ckzy.me/api.php/provide/vod/"},
    "s10": {"name": "大奶子资源", "api": "https://apidanaizi.com/api.php/provide/vod/"},
    "s11": {"name": "搜av资源", "api": "https://api.souavzyw.net/api.php/provide/vod/"},
    "s12": {"name": "奥斯卡资源", "api": "https://aosikazy1.com/api.php/provide/vod/"},
    "s13": {"name": "滴滴资源", "api": "https://api.ddapi.cc/api.php/provide/vod/at/json/"},
    "s14": {"name": "豆豆资源", "api": "https://api.douapi.cc/api.php/provide/vod/"},
    "s15": {"name": "鲨鱼资源", "api": "https://shayuapi.com/api.php/provide/vod/"},
    "s16": {"name": "辣椒资源", "api": "http://apilj.com/api.php/provide/vod/at/json/"},
    "s17": {"name": "森林资源", "api": "https://slapibf.com/api.php/provide/vod/"},
    "s18": {"name": "155资源", "api": "https://155api.com/api.php/provide/vod/"},
    "s19": {"name": "乐播资源", "api": "https://lbapi9.com/api.php/provide/vod/"},
    "s20": {"name": "玉兔资源", "api": "https://apiyutu.com/api.php/provide/vod/"},
    "s21": {"name": "番号资源", "api": "http://fhapi9.com/api.php/provide/vod/"},
    "s22": {"name": "精品X资源", "api": "https://www.jingpinx.com/api.php/provide/vod/"},
    "s23": {"name": "jkun资源", "api": "https://jkunzyapi.com/api.php/provide/vod/"},
    "s24": {"name": "湿乐园", "api": "https://xxavs.com/api.php/provide/vod/"},
    "s29": {"name": "lsb资源", "api": "https://apilsbzy1.com/api.php/provide/vod/"},
    "s30": {"name": "91麻豆", "api": "https://91md.me/api.php/provide/vod/"},
    "s32": {"name": "火速论理资源", "api": "https://api.huosuapi.cc/api.php/provide/vod/"},
    "s33": {"name": "嘿嘿资源", "api": "https://api.heiapi.cc/api.php/provide/vod/"},
}


def _to_int(v, d=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return d


async def _get_json(url, timeout=10):
    try:
        res = await OmniBox.request(
            url,
            {
                "method": "GET",
                "headers": {"User-Agent": UA, "Accept": "application/json"},
                "timeout": timeout,
            },
        )
        body = (res.get("body") or "").strip()
        if (res.get("statusCode") or 0) != 200 or not body.startswith("{"):
            return None
        return json.loads(body)
    except Exception:
        return None


def _card(item, sk, sname):
    return {
        "vod_id": "%s@@%s" % (sk, item.get("vod_id", "")),
        "vod_name": str(item.get("vod_name") or "").strip(),
        "vod_pic": str(item.get("vod_pic") or ""),
        "vod_remarks": "%s | %s" % (sname, item.get("vod_remarks") or ""),
    }


def _play_sources(item, sname):
    froms = [x for x in str(item.get("vod_play_from") or "").split("$$$") if x]
    blocks = [x for x in str(item.get("vod_play_url") or "").split("$$$") if x]
    sources = []
    n = max(len(froms), len(blocks))
    for i in range(n):
        name = "%s-%s" % (sname, froms[i] if i < len(froms) else ("线路%s" % (i + 1)))
        block = blocks[i] if i < len(blocks) else ""
        eps = []
        for j, seg in enumerate(block.split("#")):
            seg = seg.strip()
            if not seg:
                continue
            if "$" in seg:
                en, pid = seg.split("$", 1)
            else:
                en, pid = "第%s集" % (j + 1), seg
            if pid.strip():
                eps.append({"name": en.strip() or ("第%s集" % (j + 1)), "playId": pid.strip()})
        if eps:
            sources.append({"name": name, "episodes": eps})
    return sources


async def home(params, context):
    try:
        classes = [{"type_id": k, "type_name": v["name"]} for k, v in SOURCES.items()]
        filters = {}

        async def load_cls(key, source):
            data = await _get_json(source["api"] + "?ac=list", 6)
            vals = [{"n": "全部(最新)", "v": ""}]
            if data:
                for c in data.get("class") or []:
                    vals.append({"n": str(c.get("type_name") or ""), "v": str(c.get("type_id") or "")})
            return key, vals

        results = await asyncio.gather(
            *[load_cls(k, s) for k, s in SOURCES.items()],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, Exception):
                continue
            key, vals = r
            filters[key] = [{"key": "cateId", "name": "分类", "value": vals}]
        return {"class": classes, "list": [], "filters": filters}
    except Exception as e:
        await OmniBox.log("error", "[home] %s" % e)
        return {"class": [], "list": [], "filters": {}}


async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("tid") or "")
        page = _to_int(p.get("page"), 1) or 1
        extend = p.get("filters") or p.get("extend") or {}
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if tid not in SOURCES:
            return {"list": [], "page": page, "pagecount": 0, "limit": 20, "total": 0}
        source = SOURCES[tid]
        cate = str(extend.get("cateId") or "")
        url = "%s?ac=detail&pg=%s" % (source["api"], page)
        if cate:
            url += "&t=" + quote(cate)
        data = await _get_json(url, 12)
        if not data:
            return {"list": [], "page": page, "pagecount": 0, "limit": 20, "total": 0}
        items = [_card(v, tid, source["name"]) for v in (data.get("list") or []) if v.get("vod_id")]
        return {
            "list": items,
            "page": _to_int(data.get("page"), page) or page,
            "pagecount": _to_int(data.get("pagecount"), 1) or 1,
            "limit": _to_int(data.get("limit"), len(items)) or len(items),
            "total": _to_int(data.get("total"), len(items)),
        }
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 20, "total": 0}


async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or p.get("vod_id") or "").strip()
        if "@@" not in vid:
            return {"list": []}
        sk, real = vid.split("@@", 1)
        if sk not in SOURCES:
            return {"list": []}
        source = SOURCES[sk]
        data = await _get_json("%s?ac=detail&ids=%s" % (source["api"], quote(real)), 12)
        if not data:
            return {"list": []}
        out = []
        for item in data.get("list") or []:
            out.append(
                {
                    "vod_id": vid,
                    "vod_name": str(item.get("vod_name") or "").strip(),
                    "vod_pic": str(item.get("vod_pic") or ""),
                    "vod_remarks": str(item.get("vod_remarks") or ""),
                    "vod_year": str(item.get("vod_year") or ""),
                    "vod_content": re.sub(r"<[^>]+>", "", str(item.get("vod_content") or "")),
                    "type_name": str(item.get("type_name") or ""),
                    "vod_play_sources": _play_sources(item, source["name"]),
                }
            )
        return {"list": out}
    except Exception as e:
        await OmniBox.log("error", "[detail] %s" % e)
        return {"list": []}


async def search(params, context):
    try:
        p = params or {}
        key = str(p.get("keyword") or p.get("wd") or "").strip()
        page = _to_int(p.get("page"), 1) or 1
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}

        async def one(sk, source):
            data = await _get_json(
                "%s?ac=detail&wd=%s&pg=%s" % (source["api"], quote(key), page),
                8,
            )
            if not data:
                return [], 1
            items = [_card(v, sk, source["name"]) for v in (data.get("list") or []) if v.get("vod_id")]
            return items, _to_int(data.get("pagecount"), 1) or 1

        results = await asyncio.gather(
            *[one(k, s) for k, s in SOURCES.items()],
            return_exceptions=True,
        )
        all_items = []
        max_pc = 1
        for r in results:
            if isinstance(r, Exception):
                continue
            items, pc = r
            all_items.extend(items)
            if pc > max_pc:
                max_pc = pc
        return {"list": all_items, "page": page, "pagecount": max_pc, "total": len(all_items)}
    except Exception as e:
        await OmniBox.log("error", "[search] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}


async def play(params, context):
    try:
        p = params or {}
        play_id = str(p.get("playId") or p.get("url") or "").strip()
        headers = {"User-Agent": UA}
        if not play_id:
            return {"urls": [], "parse": 0, "header": headers}
        if re.search(r"\.(m3u8|mp4)(\?|$)", play_id, re.I) or play_id.startswith("http"):
            return {"urls": [{"name": "播放", "url": play_id}], "parse": 0, "header": headers}
        return {"urls": [{"name": "播放", "url": play_id}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", "[play] %s" % e)
        return {"urls": [], "parse": 0, "header": {}}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
