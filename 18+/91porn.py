# -*- coding: utf-8 -*-
# @name 91porn
# @version 1.0.0
# @description 91porn OmniBox 源：域名池自愈 / strencode2 解码 / 未成年人标题过滤
# @downloadURL

import base64
import gzip
import html as html_lib
import re
import time
import urllib.parse
import zlib

from spider_runner import OmniBox, run

_TITLE_BLOCKLIST = ("萝莉", "幼女", "幼齒", "幼齿", "小学生", "初中生", "中学生", "儿童", "孩童", "正太")
_AD_TITLE_KEYWORDS = ("广告", "sponsor", "推广", "赞助")

HOSTS = [
    "https://716.sol148.com/",
    "https://sp2026.com/",
    "https://a.26702.app/",
    "https://91porn.com/",
    "https://a.91kp.net/",
    "https://9p234.com/",
    "https://btc620.com/",
    "https://91porn.fun/",
    "https://0708.fs708.com/",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

CLASS_MAP = {
    "watch": "最新",
    "ori": "91原创",
    "hot": "当前最热",
    "top": "本月最热",
    "long": "10分钟以上",
    "longer": "20分钟以上",
    "tf": "本月收藏",
    "rf": "最近加精",
    "hd": "高清",
    "top_m": "每月最热",
    "md": "本月讨论",
    "mf": "收藏最多",
}

_state = {"host": HOSTS[0], "checked": False}


def _strencode_decode(arg0, arg1, arg2):
    if not arg0 or not arg1:
        return ""
    try:
        if len(arg2) > 0 and arg2[-1] == "2":
            data_b64, key = arg1, arg0
        else:
            data_b64, key = arg0, arg1
        data = base64.b64decode(data_b64 + "=" * (-len(data_b64) % 4))
        key_bytes = key.encode("latin-1", errors="ignore") or b"\x00"
        xored = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data))
        return base64.b64decode(xored + b"=" * (-len(xored) % 4)).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _clean_text(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    return html_lib.unescape(s).strip()


def _abs_href(href, host=None):
    host = host or _state["host"]
    if not href:
        return ""
    href = _clean_text(href)
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    return host.rstrip("/") + "/" + href.lstrip("/")


def _is_video_format(url):
    low = (url or "").lower()
    return any(ext in low for ext in (".m3u8", ".mp4", ".ts"))


def _content_ok(text):
    if not text:
        return False
    t = text.strip()
    if len(t) < 300:
        return False
    low = t.lower()
    for bad in (
        "cf-browser-verification",
        "challenge-platform",
        "just a moment",
        "attention required",
        "cdn-cgi/l/chk_jsch",
    ):
        if bad in low:
            return False
    if "我已年满18岁" in t or "i am at least 18 years" in low:
        return False
    for good in ("view_video.php", "viewkey=", "strencode2", "strencode(", "player_one", "是真的"):
        if good in t:
            return True
    return len(t) > 3000


async def _request_once(url, referer="", timeout=12):
    headers = {
        "User-Agent": UA,
        "Referer": referer or _state["host"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cookie": "language=cn_CN; over18=1; CLIPSHARE=1",
    }
    try:
        res = await OmniBox.request(url, {"method": "GET", "headers": headers, "timeout": timeout})
        status = int(res.get("statusCode") or 0)
        body = res.get("body")
        if isinstance(body, bytes):
            if body[:2] == b"\x1f\x8b":
                try:
                    body = gzip.decompress(body)
                except Exception:
                    pass
            try:
                text = body.decode("utf-8")
            except Exception:
                text = body.decode("latin1", errors="ignore")
        else:
            text = str(body or "")
        return status, text
    except Exception as e:
        return -1, str(e)


async def _probe_host(host):
    base = host.rstrip("/")
    code, text = await _request_once(base + "/zj.php", referer=host, timeout=8)
    if code == 200 and "鉴别网站真假" in text and "是真的" in text:
        return True
    code, text = await _request_once(base + "/index.php", referer=host, timeout=8)
    return code == 200 and _content_ok(text)


async def _discover_host():
    # cache
    try:
        cached = await OmniBox.getCache("91porn_valid_host")
        if cached and str(cached).startswith("http"):
            cand = str(cached).strip().rstrip("/") + "/"
            if cand in HOSTS and await _probe_host(cand):
                _state["host"] = cand
                _state["checked"] = True
                return
    except Exception:
        pass
    for host in HOSTS:
        if await _probe_host(host):
            _state["host"] = host
            _state["checked"] = True
            try:
                await OmniBox.setCache("91porn_valid_host", host, 3600)
            except Exception:
                pass
            return
    _state["checked"] = True


async def _fetch(url, referer="", timeout=12):
    if not _state["checked"]:
        await _discover_host()

    host_order = [_state["host"]] + [h for h in HOSTS if h != _state["host"]]
    tried = set()
    for host in host_order:
        target = url
        replaced = False
        for old in HOSTS:
            if old in target:
                target = target.replace(old, host)
                replaced = True
                break
        if not replaced and not target.startswith("http"):
            target = host.rstrip("/") + "/" + target.lstrip("/")
        if target in tried:
            continue
        tried.add(target)
        code, text = await _request_once(target, referer=referer or host, timeout=timeout)
        if code == 200 and _content_ok(text):
            if host != _state["host"]:
                _state["host"] = host
                try:
                    await OmniBox.setCache("91porn_valid_host", host, 3600)
                except Exception:
                    pass
            return 200, text
    return 404, ""


def _parse_video_items(html_text, host=None):
    vlist = []
    if not html_text:
        return vlist
    blocks = re.findall(
        r'<a[^>]*href=["\']([^"\']*view_video[^"\']*viewkey=[^"\']*)["\'][^>]*>(.*?)</a>',
        html_text,
        re.I | re.S,
    )
    seen = set()
    for href, inner in blocks:
        try:
            href = html_lib.unescape(href).strip()
            url = _abs_href(href, host)
            vk_m = re.search(r"viewkey=([a-zA-Z0-9]+)", url)
            v_id = vk_m.group(1) if vk_m else url
            if v_id in seen:
                continue
            title = ""
            t_m = re.search(
                r'<span[^>]*class=["\'][^"\']*video-title[^"\']*["\'][^>]*>(.*?)</span>',
                inner,
                re.I | re.S,
            )
            if t_m:
                title = _clean_text(t_m.group(1))
            if not title:
                t_m = re.search(r'(?:title|alt)=["\']([^"\']+)["\']', inner, re.I)
                if t_m:
                    title = _clean_text(t_m.group(1))
            if not title:
                continue
            if any(kw in title.lower() for kw in _AD_TITLE_KEYWORDS):
                continue
            if any(kw in title for kw in _TITLE_BLOCKLIST):
                continue
            pic = ""
            p_m = re.search(r'<img[^>]*?\s(?:data-src|src)=["\']([^"\']+)["\']', inner, re.I)
            if p_m:
                pic = p_m.group(1)
            if pic and any(k in pic for k in ("loading", "blank", "default")):
                pic = ""
            pic = _abs_href(pic, host) if pic else ""
            duration = "未知"
            d_m = re.search(
                r'<span[^>]*class=["\'][^"\']*duration[^"\']*["\'][^>]*>(.*?)</span>',
                inner,
                re.I | re.S,
            )
            if d_m:
                duration = _clean_text(d_m.group(1)) or "未知"
            seen.add(v_id)
            vlist.append(
                {
                    "vod_id": url,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": duration,
                }
            )
        except Exception:
            continue
    return vlist


def _parse_pagecount(html_text):
    try:
        nums = [int(x) for x in re.findall(r"(?:[?&]|&amp;)page=(\d+)", html_text or "")]
        if nums:
            return max(nums)
        return 1
    except Exception:
        return 1


def _extract_video_url_from_html(html):
    if not html:
        return None
    page_vid = None
    vid_m = re.search(r'id=["\']VID["\'][^>]*?value=["\']([a-zA-Z0-9_-]+)["\']', html) or re.search(
        r'id=["\']VID["\'][^>]*>\s*([a-zA-Z0-9_-]+)', html
    )
    if vid_m:
        page_vid = vid_m.group(1)

    for enc_str in re.findall(r'strencode2\((?:["\'])(.*?)(?:["\'])\)', html):
        try:
            decoded_tag = urllib.parse.unquote(enc_str)
        except Exception:
            continue
        src_m = re.search(r"src=['\"]([^'\"]+)['\"]", decoded_tag, re.I)
        if src_m:
            real_url = src_m.group(1).replace("&amp;", "&").strip()
            if _is_video_format(real_url):
                return real_url

    for m in re.finditer(
        r'strencode\(\s*(["\'])(.*?)\1\s*,\s*(["\'])(.*?)\3\s*,\s*(["\'])(.*?)\5\s*\)',
        html,
        re.S,
    ):
        decoded = _strencode_decode(m.group(2), m.group(4), m.group(6))
        src_m = re.search(r"src=['\"]([^'\"]+)['\"]", decoded, re.I)
        if src_m and _is_video_format(src_m.group(1)):
            return src_m.group(1).replace("&amp;", "&").strip()

    ad_keywords = [
        "ad-i18n-dsp",
        "kwai.net",
        "googleads",
        "popads",
        "doubleclick",
        "analytics",
        "preview",
        "cover",
        "thumb",
        "poster",
    ]
    all_urls = re.findall(r'https?://[^\s"\'<>()]+\.(?:mp4|m3u8)[^\s"\'<>]*', html, re.I)
    clean_urls = []
    for u in all_urls:
        u_clean = u.replace("&amp;", "&").strip()
        if any(ad in u_clean.lower() for ad in ad_keywords):
            continue
        clean_urls.append(u_clean)

    for u_clean in clean_urls:
        low = u_clean.lower()
        if any(kw in low for kw in ("st=", "secure=", "token=", "get_file", "mp43")) or "e=" in low:
            if page_vid and page_vid not in u_clean:
                continue
            return u_clean
    for u_clean in clean_urls:
        if page_vid and page_vid in u_clean:
            return u_clean
    if not page_vid and clean_urls:
        return clean_urls[0]
    return None


def _get_ev_url(html, detail_url, host):
    m = re.search(r"<textarea[^>]*>\s*(https?://[^<]+/ev\.php\?VID=[^<\s]+)", html, re.I)
    if m:
        return m.group(1).strip()
    matches = re.findall(r'(https?://[^"\'\s<>]+/ev\.php\?VID=[a-zA-Z0-9_-]+)', html, re.I)
    if matches:
        return matches[0]
    vid_m = re.search(r"VID=([a-zA-Z0-9_-]+)", html) or re.search(
        r"viewkey=([a-zA-Z0-9]+)", detail_url or ""
    )
    if vid_m:
        return host.rstrip("/") + "/ev.php?VID=" + vid_m.group(1)
    return None


async def home(params, context):
    classes = [{"type_id": k, "type_name": v} for k, v in CLASS_MAP.items()]
    try:
        await _discover_host()
        code, html = await _fetch(_state["host"] + "index.php")
        lst = _parse_video_items(html, _state["host"])
        await OmniBox.log("info", "[91porn][home] host=%s list=%s" % (_state["host"], len(lst)))
        return {"class": classes, "list": lst}
    except Exception as e:
        await OmniBox.log("error", "[91porn][home] %s" % e)
        return {"class": classes, "list": []}


async def category(params, context):
    tid = str(params.get("categoryId") or params.get("tid") or "watch")
    pg = int(params.get("page") or params.get("pg") or 1)
    try:
        if tid == "top_m":
            url = "%sv.php?category=top&m=-1&viewtype=basic&page=%s" % (_state["host"], pg)
        else:
            url = "%sv.php?category=%s&viewtype=basic&page=%s" % (_state["host"], tid, pg)
        code, html = await _fetch(url)
        lst = _parse_video_items(html, _state["host"])
        pagecount = _parse_pagecount(html) or (pg + 1 if len(lst) >= 18 else pg)
        await OmniBox.log("info", "[91porn][category] tid=%s page=%s list=%s" % (tid, pg, len(lst)))
        return {"list": lst, "page": pg, "pagecount": pagecount, "total": pagecount * max(1, len(lst))}
    except Exception as e:
        await OmniBox.log("error", "[91porn][category] %s" % e)
        return {"list": [], "page": pg, "pagecount": 1, "total": 0}


async def search(params, context):
    key = str(params.get("keyword") or params.get("wd") or params.get("key") or "").strip()
    pg = int(params.get("page") or params.get("pg") or 1)
    if not key:
        return {"list": [], "page": pg, "pagecount": 0, "total": 0}
    try:
        encoded = urllib.parse.quote(key)
        url = (
            "%ssearch_result.php?search_id=%s&search_type=search_videos&min_duration=&page=%s"
            % (_state["host"], encoded, pg)
        )
        code, html = await _fetch(url)
        lst = _parse_video_items(html, _state["host"])
        pagecount = _parse_pagecount(html) or (pg + 1 if lst else pg)
        await OmniBox.log("info", "[91porn][search] kw=%s list=%s" % (key, len(lst)))
        return {"list": lst, "page": pg, "pagecount": pagecount, "total": pagecount * max(1, len(lst))}
    except Exception as e:
        await OmniBox.log("error", "[91porn][search] %s" % e)
        return {"list": [], "page": pg, "pagecount": 0, "total": 0}


async def detail(params, context):
    vod_id = str(params.get("videoId") or params.get("id") or params.get("ids") or "").strip()
    if not vod_id:
        return {"list": []}
    if isinstance(params.get("videoId") or params.get("id"), list):
        vod_id = str((params.get("videoId") or params.get("id"))[0])
    detail_url = vod_id if vod_id.startswith("http") else _abs_href(vod_id)
    try:
        code, html = await _fetch(detail_url, referer=_state["host"])
        video_url = _extract_video_url_from_html(html)

        if not video_url:
            candidates = []
            ev_url = _get_ev_url(html, detail_url, _state["host"])
            if ev_url:
                candidates.append(ev_url)
            if vid_m := re.search(r"VID=([a-zA-Z0-9_-]+)", html):
                rebuilt = _state["host"].rstrip("/") + "/ev.php?VID=" + vid_m.group(1)
                if rebuilt not in candidates:
                    candidates.append(rebuilt)
            for cand in candidates:
                try:
                    code, ev_html = await _fetch(cand, referer=_state["host"], timeout=10)
                    found = _extract_video_url_from_html(ev_html)
                    if found:
                        video_url = found
                        break
                except Exception:
                    continue

        if not video_url:
            video_url = detail_url

        title = "未知标题"
        t_m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        if t_m:
            title = _clean_text(t_m.group(1)).split("- 91porn")[0].strip() or "未知标题"

        pic = ""
        p_m = (
            re.search(
                r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
                html,
                re.I,
            )
            or re.search(r'poster=["\']([^"\']+)["\']', html, re.I)
        )
        if p_m:
            pic = _abs_href(p_m.group(1))

        duration = "未知"
        if m_dur := re.search(r"\d{2}:\d{2}:\d{2}|\d{2}:\d{2}", html):
            duration = m_dur.group(0)

        await OmniBox.log(
            "info",
            "[91porn][detail] direct=%s url=%s"
            % (_is_video_format(video_url), (video_url or "")[:80]),
        )
        return {
            "list": [
                {
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": duration,
                    "vod_content": title,
                    "vod_play_sources": [
                        {
                            "name": "91Porn",
                            "episodes": [{"name": "高清", "playId": video_url}],
                        }
                    ],
                }
            ]
        }
    except Exception as e:
        await OmniBox.log("error", "[91porn][detail] %s" % e)
        return {"list": []}


async def play(params, context):
    play_id = str(params.get("playId") or params.get("url") or "").strip()
    if not play_id:
        return {"urls": [], "parse": 0, "header": {}}
    base = _state["host"].rstrip("/")
    headers = {"User-Agent": UA, "Referer": base + "/", "Origin": base}
    if _is_video_format(play_id):
        return {"urls": [{"name": "高清", "url": play_id}], "parse": 0, "header": headers}
    # 可能是详情页：再解析一次
    try:
        code, html = await _fetch(play_id, referer=base + "/")
        video_url = _extract_video_url_from_html(html)
        if video_url and _is_video_format(video_url):
            return {"urls": [{"name": "高清", "url": video_url}], "parse": 0, "header": headers}
    except Exception:
        pass
    return {"urls": [{"name": "网页", "url": play_id}], "parse": 1, "header": headers}


run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
