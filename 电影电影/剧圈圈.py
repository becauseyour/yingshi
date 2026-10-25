# -*- coding: utf-8 -*-
# @name 剧圈圈
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%94%B5%E5%BD%B1%E7%94%B5%E8%A7%86/剧圈圈.py
# @description 剧圈圈在线站源（OmniBox 适配版）：移动端 UA、suggest 搜索、jx/api 解密直链

"""
剧圈圈 (jqqzx.one) — OmniBox 适配版
必须使用移动端 UA（PC UA 会被 404）
播放链路: player_aaaa vid → POST /jx/api.php → sign 解密直链
"""

import base64
import hashlib
import json
import re
from urllib.parse import quote, urlencode

from spider_runner import OmniBox, run

HOSTS = [
    "https://www.jqqzx.one",
    "https://www.jqqzx.cc",
    "https://jqqzx.cc",
]
HOST = HOSTS[0]
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
TIMEOUT = 12

CATE_MAP = {
    "dianying": "电影",
    "juji": "剧集",
    "dongman": "动漫",
    "zongyi": "综艺",
    "duanju": "短剧",
}

_FILTER_CLASS = {
    "dianying": ["Netflix", "喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "犯罪", "动画",
                 "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚", "古装", "历史", "家庭", "运动",
                 "儿童", "经典", "青春", "文艺", "微电影", "纪录片", "网络电影"],
    "juji": ["Netflix", "爱情", "言情", "都市", "家庭", "战争", "喜剧", "古装", "武侠", "偶像",
             "历史", "悬疑", "科幻", "冒险", "惊悚", "犯罪", "运动", "恐怖", "剧情", "奇幻",
             "纪录片", "灾难", "动作"],
    "dongman": ["Netflix", "奇幻", "动作", "科幻", "喜剧", "冒险", "后宫", "爱情", "悬疑", "机战", "战争"],
    "zongyi": ["Netflix", "纪录片", "真人秀", "音乐", "喜剧", "脱口秀", "文化", "美食"],
    "duanju": ["都市", "古装", "穿越", "重生", "逆袭", "赘婿", "战神", "神医", "甜宠", "虐恋", "言情"],
}
_AREA_FULL = ["大陆", "美国", "韩国", "日本", "泰国", "香港", "台湾", "新加坡", "马来西亚", "印度",
              "英国", "法国", "德国", "加拿大", "西班牙", "俄罗斯", "其它"]
_FILTER_AREA = {
    "dianying": _AREA_FULL,
    "juji": _AREA_FULL,
    "dongman": ["大陆", "日本", "美国"],
    "zongyi": ["大陆", "美国", "韩国", "日本", "香港", "台湾", "印度", "英国", "法国", "德国",
               "加拿大", "西班牙", "俄罗斯", "其它"],
    "duanju": [],
}
_FILTER_YEAR = [str(y) for y in range(2026, 1999, -1)]
_FILTER_BY = [("最新", "time"), ("人气", "hits"), ("评分", "score")]


def _filters(tid):
    def blk(key, name, pairs):
        return {
            "key": key,
            "name": name,
            "value": [{"n": "全部", "v": ""}] + [{"n": n, "v": v} for n, v in pairs],
        }
    out = []
    cls = _FILTER_CLASS.get(tid) or []
    if cls:
        out.append(blk("class", "类型", [(v, v) for v in cls]))
    area = _FILTER_AREA.get(tid) or []
    if area:
        out.append(blk("area", "地区", [(v, v) for v in area]))
    out.append(blk("year", "年份", [(v, v) for v in _FILTER_YEAR]))
    out.append(blk("by", "排序", _FILTER_BY))
    return out


CATE_FILTERS = {k: _filters(k) for k in CATE_MAP}


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _abs(u):
    if not u:
        return ""
    if u.startswith("http"):
        return u
    return HOST + (u if u.startswith("/") else "/" + u)


_B64_JUNK = re.compile(r"[^A-Za-z0-9+/=]")


def _b64d(s):
    if isinstance(s, bytes):
        s = s.decode("utf-8", "ignore")
    s = _B64_JUNK.sub("", s)
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s).decode("utf-8")


def _custom_str_decode(s):
    key = hashlib.md5(b"test").hexdigest()
    t = _b64d(s)
    code = "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(t))
    return _b64d(code)


def _de_string(a, b, c):
    out = []
    for ch in c:
        if ("a" <= ch <= "z" or "A" <= ch <= "Z") and ch in b:
            idx = a.find(ch) if isinstance(a, str) else (a.index(ch) if ch in a else -1)
            if idx >= 0:
                out.append(b[idx])
                continue
        out.append(ch)
    return "".join(out)


def _sign_url(enc_url):
    s = _custom_str_decode(enc_url)
    parts = s.split("/")
    if len(parts) < 3:
        return ""
    payload = _b64d("/".join(parts[2:]))
    a = json.loads(_b64d(parts[1]))
    b = json.loads(_b64d(parts[0]))
    return _de_string(a, b, payload)


def unquote_js(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s):
            try:
                out.append(chr(int(s[i + 1:i + 3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        out.append(s[i])
        i += 1
    return "".join(out)


def _extract_vid(html):
    i = (html or "").find("player_aaaa")
    if i < 0:
        return ""
    j = (html or "").find("</script>", i)
    seg = (html or "")[i:j if j > 0 else len(html or "")]
    m = re.search(r'"url":"([^"]+)"', seg)
    if not m:
        return ""
    vid = m.group(1).replace("\\/", "/")
    em = re.search(r'"encrypt":(\d)', seg)
    enc = em.group(1) if em else "0"
    try:
        if enc == "2":
            vid = unquote_js(_b64d(vid))
        elif enc == "1":
            vid = unquote_js(vid)
    except Exception:
        pass
    return vid


def _cards(html, limit=30):
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]*href="/vod/(\d+)\.html"[^>]*>([\s\S]{0,1200}?)</a>', html or ""):
        head, body = m.group(0), m.group(2)
        vid = m.group(1)
        if vid in seen:
            continue
        nm = re.search(r'title="([^"]+)"', head) or re.search(r'alt="([^"]+)"', body)
        if not nm:
            continue
        pic = re.search(r'data-original="([^"]+)"', body)
        rm = re.search(r"module-item-note[^>]*>\s*([^<]{1,20})\s*<", body)
        seen.add(vid)
        out.append({
            "vod_id": vid,
            "vod_name": nm.group(1).strip(),
            "vod_pic": _abs(pic.group(1)) if pic else "",
            "vod_remarks": (rm.group(1).strip() if rm else ""),
        })
        if len(out) >= limit:
            break
    return out


def _detail_parse(html, vid):
    v = {"vod_id": vid}
    nm = re.search(r"<h1[^>]*>\s*([^<]{1,60}?)\s*</h1>", html or "")
    v["vod_name"] = nm.group(1).strip() if nm else ""
    if not v["vod_name"]:
        t = re.search(r"<title>([^<]+)", html or "")
        if t:
            v["vod_name"] = re.split(r"[-|]", t.group(1))[0].strip()
    pic = re.search(r'data-original="([^"]+)"', html or "")
    v["vod_pic"] = _abs(pic.group(1)) if pic else ""
    v["vod_year"] = ""
    v["vod_area"] = ""
    v["vod_actor"] = ""
    v["vod_director"] = ""
    for key, field in (
        ("类型", "type_name"),
        ("年份", "vod_year"),
        ("地区", "vod_area"),
        ("主演", "vod_actor"),
        ("导演", "vod_director"),
    ):
        m = re.search(re.escape(key) + r"[^>]*>\s*(?:<[^>]+>\s*)*([^<]{1,80})", html or "")
        if m:
            v[field] = re.sub(r"\s+", "", m.group(1)).strip()[:60]
    d = re.search(r'<meta name="description"[^>]*content="([^"]+)"', html or "")
    v["vod_content"] = d.group(1).strip()[:300] if d else ""

    tab_names = []
    i = (html or "").find("选择播放源")
    if i > 0:
        seg = (html or "")[i:i + 4000]
        for m in re.finditer(r">\s*([^<>]{2,16}?)\s*<", seg):
            t = m.group(1).strip()
            if (
                t
                and len(t) <= 16
                and "选择" not in t
                and not t.isdigit()
                and re.search(r"[\u4e00-\u9fa5A-Za-z]", t)
                and t not in tab_names
            ):
                tab_names.append(t)
    tab_names = tab_names[:24]

    groups = {}
    for u, sid, n in re.findall(
        r'href="(/play/\d+-(\d+)-\d+\.html)"[^>]*>\s*([^<]{0,16})\s*<', html or ""
    ):
        title = (n or "").strip()
        item = groups.setdefault(sid, [])
        if not any(x[0] == u for x in item):
            item.append((u, title))

    sources = []
    for i2, sid in enumerate(sorted(groups, key=lambda x: int(x) if x.isdigit() else 0)):
        items = groups[sid]
        label = tab_names[i2] if i2 < len(tab_names) else ("线路%s" % sid)
        episodes = [
            {"name": n or ("第%d集" % (j + 1)), "playId": u}
            for j, (u, n) in enumerate(items)
        ]
        if episodes:
            sources.append({"name": label, "episodes": episodes})
    if sources:
        v["vod_play_sources"] = sources
    return v


async def _get(path, referer=None, xhr=False):
    global HOST
    h = {"User-Agent": UA}
    if referer:
        h["Referer"] = referer
    if xhr:
        h["X-Requested-With"] = "XMLHttpRequest"
    if path.startswith("http"):
        res = await OmniBox.request(path, {"method": "GET", "headers": h, "timeout": TIMEOUT})
        if (res.get("statusCode") or 0) == 200:
            return res.get("body") or ""
        return ""
    hosts = [HOST] + [x for x in HOSTS if x != HOST]
    for base in hosts:
        url = base + path
        try:
            res = await OmniBox.request(url, {"method": "GET", "headers": h, "timeout": TIMEOUT})
            body = res.get("body") or ""
            if (res.get("statusCode") or 0) == 200 and len(body) > 500:
                HOST = base
                return body
        except Exception:
            continue
    return ""


async def _post_form(url, data, referer=None):
    body = urlencode(data)
    h = {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    }
    if referer:
        h["Referer"] = referer
    res = await OmniBox.request(
        url, {"method": "POST", "headers": h, "body": body, "timeout": TIMEOUT}
    )
    if (res.get("statusCode") or 0) == 200:
        return res.get("body") or ""
    return ""


def _final_from(raw):
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except Exception:
        return ""
    if not isinstance(data, dict) or data.get("code") != 200:
        return ""
    enc = (data.get("data") or {}).get("url") or ""
    if not enc:
        return ""
    try:
        return _sign_url(enc)
    except Exception:
        return ""


async def _resolve_direct(play_url):
    html = await _get(play_url, referer=HOST + "/")
    vid = _extract_vid(html)
    if not vid:
        return ""
    raw = await _post_form(HOST + "/jx/api.php", {"vid": vid}, referer=play_url)
    return _final_from(raw)


async def home(params, context):
    try:
        await OmniBox.log("info", f"[home] from={(context or {}).get('from', 'web')}")
        classes = [{"type_id": k, "type_name": v} for k, v in CATE_MAP.items()]
        html = await _get("/")
        return {"class": classes, "list": _cards(html, limit=24), "filters": CATE_FILTERS}
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {
            "class": [{"type_id": k, "type_name": v} for k, v in CATE_MAP.items()],
            "list": [],
            "filters": CATE_FILTERS,
        }


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "juji")
        page = _to_int((params or {}).get("page"), 1) or 1
        extend = (params or {}).get("filters") or {}
        by = (extend.get("by") or "").strip() if isinstance(extend, dict) else ""
        cls = (extend.get("class") or "").strip() if isinstance(extend, dict) else ""
        area = (extend.get("area") or "").strip() if isinstance(extend, dict) else ""
        year = (extend.get("year") or "").strip() if isinstance(extend, dict) else ""
        await OmniBox.log("info", f"[category] categoryId={tid}, page={page}")
        seg = ""
        if by:
            seg += "by/%s/" % quote(by)
        if cls:
            seg += "class/%s/" % quote(cls)
        if area:
            seg += "area/%s/" % quote(area)
        seg += "id/%s" % tid
        if year:
            seg += "/year/%s" % quote(year)
        path = "/vodshow/%s/page/%d.html" % (seg, page)
        html = await _get(path)
        lst = _cards(html, limit=40)
        pagecount = page if lst else max(page - 1, 1)
        m = re.search(r'href="[^"]*/page/(\d+)\.html"[^>]*title="尾页"', html or "")
        if m:
            pagecount = max(int(m.group(1)), 1)
        return {
            "list": lst,
            "page": page,
            "pagecount": pagecount,
            "limit": 40,
            "total": pagecount * 40,
        }
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 40}


async def detail(params, context):
    try:
        vid = str((params or {}).get("videoId") or "")
        if not vid:
            return {"list": []}
        await OmniBox.log("info", f"[detail] videoId={vid}")
        html = await _get("/vod/%s.html" % vid)
        v = _detail_parse(html, vid)
        if not v.get("vod_play_sources"):
            html = await _get("/vod/%s.html" % vid, referer=HOST + "/")
            v = _detail_parse(html, vid)
        return {"list": [v]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] 失败: {e}")
        return {"list": []}


async def search(params, context):
    try:
        key = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 20}
        await OmniBox.log("info", f"[search] keyword={key}, page={page}")
        path = "/index.php/ajax/suggest?mid=1&wd=%s&limit=50" % quote(key)
        html = await _get(path, referer=HOST + "/", xhr=True)
        items = []
        try:
            data = json.loads(html) if html else {}
            for it in data.get("list") or []:
                vid = str(it.get("id") or "").strip()
                name = (it.get("name") or "").strip()
                if vid and name:
                    items.append({
                        "vod_id": vid,
                        "vod_name": name,
                        "vod_pic": _abs(it.get("pic") or ""),
                        "vod_remarks": "",
                    })
        except Exception:
            pass
        per = 20
        chunk = items[(page - 1) * per: page * per]
        pagecount = (len(items) + per - 1) // per or 1
        return {
            "list": chunk,
            "page": page,
            "pagecount": pagecount,
            "limit": per,
            "total": len(items),
        }
    except Exception as e:
        await OmniBox.log("error", f"[search] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 20}


async def play(params, context):
    try:
        video_id = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not video_id:
            raise ValueError("playId 为空")
        url = video_id if video_id.startswith("http") else _abs(video_id)
        await OmniBox.log("info", f"[play] playId={url[:100]}")
        direct = await _resolve_direct(url)
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        if direct:
            return {
                "urls": [{"name": "播放", "url": direct}],
                "flag": flag,
                "header": headers,
                "parse": 0,
            }
        html = await _get(url, referer=HOST + "/")
        m = re.search(r'(https?://[^"\'>\s]+\.m3u8[^"\'>\s]*)', html or "")
        if m:
            return {
                "urls": [{"name": "播放", "url": m.group(1)}],
                "flag": flag,
                "header": headers,
                "parse": 0,
            }
        return {
            "urls": [{"name": "播放", "url": url}],
            "flag": flag,
            "header": headers,
            "parse": 1,
        }
    except Exception as e:
        await OmniBox.log("error", f"[play] 失败: {e}")
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
