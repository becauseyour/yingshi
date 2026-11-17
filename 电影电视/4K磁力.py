# -*- coding: utf-8 -*-
# @name 4K磁力
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%94%B5%E5%BD%B1%E7%94%B5%E8%A7%86/4K磁力.py
# @description 6v电影/xb6v 磁力站源（OmniBox 适配版）：磁力/网盘直链

import re
from urllib.parse import quote

from spider_runner import OmniBox, run

HOST = "https://www.xb6v.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

TOPS = [
    ("xijupian", "喜剧片"), ("dongzuopian", "动作片"), ("aiqingpian", "爱情片"),
    ("kehuanpian", "科幻片"), ("kongbupian", "恐怖片"), ("juqingpian", "剧情片"),
    ("zhanzhengpian", "战争片"), ("jilupian", "纪录片"), ("donghuapian", "动画片"),
    ("dianshiju", "电视剧"), ("ZongYi", "综艺"),
]
SUB = {
    "dianshiju": [("guoju", "国产剧"), ("duanju", "短剧"), ("rihanju", "日韩剧"), ("oumeiju", "欧美剧")],
}


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


async def _fetch(url, post=None):
    headers = {
        "User-Agent": UA,
        "Referer": HOST + "/",
    }
    opts = {"method": "GET", "headers": headers, "timeout": 20}
    if post:
        opts["method"] = "POST"
        opts["headers"] = dict(headers)
        opts["headers"]["Content-Type"] = "application/x-www-form-urlencoded"
        from urllib.parse import urlencode
        opts["body"] = urlencode(post)
    res = await OmniBox.request(url, opts)
    return res.get("body") or ""


def _cards(html):
    out, seen = [], set()
    pat = (
        r'<a[^>]*href="(/[^"]*?/[^"]*?\d+\.html)"[^>]*title="([^"]+)"[^>]*>'
        r'[\s\S]{0,300}?<img[^>]*src="([^"]+)"'
    )
    for m in re.finditer(pat, html or ""):
        href, title, pic = m.group(1), m.group(2), m.group(3)
        if not href or not title or href in seen:
            continue
        seen.add(href)
        out.append({"vod_id": href, "vod_name": title.strip(), "vod_pic": pic, "vod_remarks": ""})
    return out


async def home(params, context):
    try:
        await OmniBox.log("info", f"[home] from={(context or {}).get('from', 'web')}")
        classes = [{"type_id": t, "type_name": n} for t, n in TOPS]
        filters = {}
        for top, _ in TOPS:
            if top in SUB:
                filters[top] = [
                    {
                        "key": "class",
                        "name": "类型",
                        "value": [{"n": "全部", "v": ""}]
                        + [{"n": n, "v": "/%s/%s" % (top, s)} for s, n in SUB[top]],
                    }
                ]
        html = await _fetch(HOST + "/dongzuopian/")
        return {"class": classes, "list": _cards(html)[:24], "filters": filters}
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {"class": [], "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "dongzuopian")
        page = _to_int((params or {}).get("page"), 1) or 1
        extend = (params or {}).get("filters") or {}
        cls = extend.get("class") if isinstance(extend, dict) else ""
        if cls:
            tid = str(cls).lstrip("/")
        await OmniBox.log("info", f"[category] categoryId={tid}, page={page}")
        path = ("/" + tid.rstrip("/") + "/") if "/" in tid else ("/" + tid + "/")
        url = path if page == 1 else "%sindex_%d.html" % (path, page)
        cards = _cards(await _fetch(HOST + url))
        return {
            "list": cards,
            "page": page,
            "pagecount": 9999 if cards else page,
            "limit": 30,
            "total": 99999,
        }
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 30}


async def detail(params, context):
    try:
        href = str((params or {}).get("videoId") or "").strip()
        if not href:
            return {"list": []}
        if not href.startswith("/"):
            href = "/" + href
        await OmniBox.log("info", f"[detail] videoId={href}")
        html = await _fetch(HOST + href)
        if not html:
            return {"list": []}
        vod = {
            "vod_id": href,
            "vod_name": "",
            "vod_pic": "",
            "vod_year": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_remarks": "",
        }
        t = re.search(r"<title>([^<]*)", html)
        if t:
            vod["vod_name"] = re.split(r"[_\-]", t.group(1))[0].strip()
        p = re.search(r'<img[^>]*src="([^"]+)"', html)
        if p:
            vod["vod_pic"] = p.group(1)

        def _field(lb):
            pat = r"◎\s*" + r"\s*".join(re.escape(c) for c in lb) + r"[：:]\s*([^\n<◎]{1,80})"
            m = re.search(pat, html)
            return m.group(1).strip().replace("&middot;", "·") if m else ""

        vod["vod_year"] = _field("年代")
        area = _field("产地")
        vod["vod_director"] = _field("导演")
        vod["vod_actor"] = _field("主演")
        if area:
            vod["vod_remarks"] = area
        dm = re.search(r"◎\s*简\s*介[\s\S]{0,40}?([\s\S]{0,1200}?)<", html)
        if dm:
            vod["vod_content"] = re.sub(r"<[^>]+>", "", dm.group(1)).strip()

        lines = {}
        for m in re.finditer(
            r'(magnet:[^"\'<\s]+)|https?://(pan\.\w+\.(?:com|cn|net)[^"\'<\s]+)',
            html,
        ):
            if m.group(1):
                lines.setdefault("磁力", []).append(m.group(1))
            elif m.group(2):
                u = m.group(2)
                if "xunlei" in u:
                    lines.setdefault("迅雷云盘", []).append(u)
                elif "quark" in u:
                    lines.setdefault("夸克云盘", []).append(u)
                elif "baidu" in u:
                    lines.setdefault("百度云盘", []).append(u)

        sources = []
        for name, eps in lines.items():
            episodes = [{"name": name, "playId": u.replace("&amp;", "&")} for u in eps]
            if episodes:
                sources.append({"name": name, "episodes": episodes})
        if sources:
            vod["vod_play_sources"] = sources
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] 失败: {e}")
        return {"list": []}


async def search(params, context):
    try:
        key = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if page > 1 or not key:
            return {"list": [], "page": page, "pagecount": page, "limit": 20, "total": 0}
        await OmniBox.log("info", f"[search] keyword={key}")
        html = await _fetch(
            HOST + "/e/search/so.php",
            {
                "keyboard": key,
                "show": "title",
                "tempid": "1",
                "tbname": "",
                "mid": "1",
                "dopost": "1",
                "submit": "搜索",
            },
        )
        cards = _cards(html)
        if not cards:
            seen = set()
            for m in re.finditer(r'href="(/[^"]*?/[^"]*?\d+\.html)"[^>]*>\s*([^<]{2,60})', html or ""):
                href, title = m.group(1), m.group(2).strip()
                if href and title and href not in seen and "第" not in title[:2]:
                    seen.add(href)
                    cards.append({"vod_id": href, "vod_name": title, "vod_pic": "", "vod_remarks": ""})
        return {
            "list": cards,
            "page": page,
            "pagecount": page if len(cards) < 20 else page + 1,
            "limit": 20,
            "total": len(cards),
        }
    except Exception as e:
        await OmniBox.log("error", f"[search] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 20}


async def play(params, context):
    try:
        u = str((params or {}).get("playId") or "").replace("&amp;", "&").strip()
        flag = str((params or {}).get("flag") or "play")
        if not u:
            raise ValueError("playId 为空")
        await OmniBox.log("info", f"[play] playId={u[:100]}")
        return {
            "urls": [{"name": "打开", "url": u}],
            "flag": flag,
            "header": {"User-Agent": UA, "Referer": HOST + "/"},
            "parse": 0,
        }
    except Exception as e:
        await OmniBox.log("error", f"[play] 失败: {e}")
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
