# -*- coding: utf-8 -*-
# @name 影探网
# @author OmniBox-Spider
# @description 影视站：https://m.zhuayong.com，标准 MacCMS + stui 手机模板，支持首页、分类、搜索、详情与直链播放
# @version 1.0.0
# @indexs 1
# @downloadURL https://gh-proxy.org/https://github.com/Silent1566/OmniBox-Spider/raw/refs/heads/main/影视/采集/影探网.py
"""
影探网 OmniBox 爬虫源（Python）
================================
由 TVBox T4 版改写而来，改写点：
  1) 依赖 base.spider.Spider → spider_runner.OmniBox，五个 handler 改成 async (params, context)；
  2) HTTP 从 requests.Session 换成 OmniBox.request（无会话复用，顺带避开站点"同会话连搜返空"的限流）；
  3) 详情播放线路输出 vod_play_sources 新结构；play 返回 urls/header/parse（不含 flag）；
  4) 搜索补了空结果重试，站点搜索接口偶发返空。

站点接口（实测）：
    首页   GET  /
    分类   POST /ytwc/{slug}/          form: page=N
    搜索   POST /yins/                 form: wd=关键词&mid=1&page=N
    详情   GET  /yind/{id}/
    选集   GET  /play-eps/{id}-{sid}/  → JSON [{"t":"第01集","u":"/play/..."}]
    播放   GET  /play/{id}-{sid}-{n}/  页面内 var videoSrc = "https:\\/\\/...m3u8"
  搜索必须带 mid=1，否则中文关键词返空；片源是第三方 CDN 的 HLS，播放需带 Referer。
"""
import html as html_lib
import json
import os
import re
from urllib.parse import urlencode

try:
    from spider_runner import OmniBox, run
except Exception:  # 本地调试兜底，生产环境由 OmniBox 提供
    class OmniBox:  # type: ignore
        @staticmethod
        async def log(level, message):
            print("[{}] {}".format(level, message))

        @staticmethod
        async def request(url, options=None):
            raise RuntimeError("spider_runner 不可用")

    def run(handlers):
        pass

SOURCE = "影探网"
SITE_URL = os.environ.get("YINGTAN_HOST", "https://m.zhuayong.com").rstrip("/")
UA = os.environ.get(
    "YINGTAN_UA",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
)
PAGE_SIZE = 30
VIDEO_EXT = re.compile(r"\.(m3u8|mp4|flv|ts)(\?|$)", re.I)

# 分类：频道页本身不带分页，列表在子分类 slug 上
CATS = [
    ("电影", [("dongzuopian", "动作片"), ("xijupian", "喜剧片"), ("aiqingpian", "爱情片"),
             ("lunlipian", "伦理片"), ("kehuanpian", "科幻片"), ("kongbupian", "恐怖片"),
             ("juqingpian", "剧情片"), ("zhanzhengpian", "战争片"), ("fanzuipian", "犯罪片"),
             ("guzhuangpian", "古装片")]),
    ("电视剧", [("guochanju", "国产剧"), ("duanju", "短剧"), ("hanju", "韩剧"),
              ("oumeiju", "欧美剧"), ("riju", "日剧"), ("gangju", "港剧"),
              ("taiju", "泰剧"), ("taiwanju", "台剧")]),
    ("动漫", [("guochandongman", "国产动漫"), ("rimanhanman", "日韩动漫"),
             ("dongmandianying", "动漫电影"), ("oumeidongman", "欧美动漫"),
             ("jingdiandonghua", "经典动画")]),
    ("综艺", [("daluzongyi", "大陆综艺"), ("gangtaizongyi", "港台综艺"),
             ("rihanzongyi", "日韩综艺"), ("oumeizongyi", "欧美综艺")]),
    ("纪录片", [("jilupian", "纪录片")]),
]
CLASS_LIST = []
NAME_BY_SLUG = {}
for _top, _subs in CATS:
    for _slug, _name in _subs:
        _label = _top + "·" + _name if _top != _name else _name
        CLASS_LIST.append({"type_id": _slug, "type_name": _label})
        NAME_BY_SLUG[_slug] = _label


async def log(level, message):
    try:
        await OmniBox.log(level, "[{}] {}".format(SOURCE, message))
    except Exception:
        pass


def safe_text(value):
    return str(value if value is not None else "").strip()


async def request_text(url, method="GET", data=None, referer="", retries=2):
    """统一请求封装：失败返回空串，搜索等关键路径可据此重试"""
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer or (SITE_URL + "/"),
    }
    body = data
    if isinstance(body, dict):
        body = urlencode(body)
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    last_error = ""
    for attempt in range(retries + 1):
        try:
            response = await OmniBox.request(url, {"method": method, "headers": headers, "body": body})
            status = int(response.get("statusCode") or 0)
            raw = response.get("body", "")
            text = raw.decode("utf-8", "ignore") if isinstance(raw, (bytes, bytearray)) else str(raw or "")
            if status == 200 and text:
                return text
            last_error = "HTTP {}".format(status)
        except Exception as error:
            last_error = safe_text(error) or error.__class__.__name__
    await log("warn", "请求失败 {} ({})".format(url, last_error))
    return ""


def abs_url(url):
    raw = safe_text(url)
    if not raw or raw.startswith("data:"):
        return ""
    if raw.startswith("//"):
        return "https:" + raw
    if raw.startswith("/"):
        return SITE_URL + raw
    return raw


def clean_text(value):
    text = html_lib.unescape(safe_text(value))
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def page_count(html_text, fallback=1):
    for pattern in (r"var\s+tot\s*=\s*(\d+)", r'searchGoPage\(\s*(\d+)\s*\)">尾页', r"catOpenPicker\(this,\s*\d+\s*,\s*(\d+)"):
        m = re.search(pattern, html_text or "")
        if m:
            return max(1, int(m.group(1)))
    return max(1, fallback)


def container_index(text, cls):
    """定位列表容器：class 属性可能是多类名组合，这里按首类名匹配"""
    m = re.search(r'class="%s(?:["\s])' % re.escape(cls), text or "")
    return m.start() if m else -1


def extract_container(html_text, cls):
    """按容器类名截取列表区块，避开页面上每页重复的固定推荐块"""
    text = html_text or ""
    idx = container_index(text, cls)
    if idx < 0:
        return text  # 结构变动时退回整页，避免直接空结果
    start = text.rfind("<ul", 0, idx)
    if start < 0:
        return text
    depth = 0
    i = start
    while i < len(text):
        if text.startswith("<ul", i):
            depth += 1
        elif text.startswith("</ul>", i):
            depth -= 1
            if depth == 0:
                return text[start:i + 5]
        i += 1
    return text[start:]


def parse_cards(html_text, type_id="", type_name="", container="", require_container=False):
    """列表页/搜索页/首页通用卡片解析。
    container 限定主列表容器；require_container=True 时容器缺失直接判为失败，
    防止站点把请求回落到首页时被误当成真实结果。"""
    vods, seen = [], set()
    scope = html_text or ""
    if container:
        if require_container and container_index(scope, container) < 0:
            return []
        scope = extract_container(scope, container)
    for tag in re.findall(
        r'<a\b[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*>[\s\S]*?</a>', scope
    ):
        hm = re.search(r'href="(/yind/(\d+)/)"', tag)
        if not hm:
            continue
        vid = hm.group(2)
        if vid in seen:
            continue
        seen.add(vid)
        tm = re.search(r'title="([^"]*)"', tag)
        pm = re.search(r'data-original="([^"]*)"', tag) or re.search(r'src="([^"]*)"', tag)
        pic = abs_url(pm.group(1)) if pm else ""
        if pic.endswith("load.gif"):
            pic = ""
        # 卡片右下角备注：搜索页是更新状态（pic-text text-right），列表页是片名（text-center），只取前者
        rm = re.search(r'<span class="pic-text text-right">([^<]*)</span>', tag)
        vods.append({
            "vod_id": vid,
            "vod_name": clean_text(tm.group(1) if tm else ""),
            "vod_pic": pic,
            "vod_remarks": clean_text(rm.group(1) if rm else ""),
            "type_id": type_id,
            "type_name": type_name,
        })
    return vods


def page_result(page, pagecount, vods, total=None):
    pages = max(1, pagecount)
    return {
        "page": page,
        "pagecount": pages,
        "limit": PAGE_SIZE,
        "total": total if total is not None else len(vods),
        "list": vods,
    }


async def home(params, context):
    try:
        html_text = await request_text(SITE_URL + "/")
        return {"class": CLASS_LIST, "list": parse_cards(html_text)[:60]}
    except Exception as error:
        await log("error", "home 失败: {}".format(error))
        return {"class": CLASS_LIST, "list": []}


async def category(params, context):
    params = params or {}
    slug = safe_text(params.get("categoryId") or params.get("tid") or params.get("typeId") or params.get("type_id"))
    page = int(params.get("page") or 1)
    if slug not in NAME_BY_SLUG:
        # 站点非法 slug 会回落到首页内容，这里直接挡掉
        await log("warn", "category 未知分类 slug={}".format(slug))
        return page_result(page, 1, [])
    try:
        url = "{}/ytwc/{}/".format(SITE_URL, slug)
        html_text = await request_text(url, "POST", {"page": page}, referer=url)
        vods = parse_cards(html_text, slug, NAME_BY_SLUG.get(slug, ""),
                           "stui-vodlist clearfix", True)
        pages = page_count(html_text, page)
        await log("info", "category slug={} page={} 命中={} 总页={}".format(slug, page, len(vods), pages))
        return page_result(page, pages, vods, pages * PAGE_SIZE)
    except Exception as error:
        await log("error", "category 失败 slug={}: {}".format(slug, error))
        return page_result(page, 1, [])


async def search(params, context):
    params = params or {}
    keyword = safe_text(params.get("keyword") or params.get("wd") or params.get("query"))
    page = int(params.get("page") or 1)
    if not keyword:
        return page_result(page, 1, [])
    url = SITE_URL + "/yins/"
    try:
        html_text = ""
        vods = []
        # 站点搜索接口偶发返空（实测同一会话连搜第二条起返空），这里做有限重试
        for attempt in range(3):
            html_text = await request_text(url, "POST", {"wd": keyword, "mid": 1, "page": page},
                                           referer="{}/?".format(SITE_URL))
            vods = parse_cards(html_text, container="stui-vodlist__media", require_container=True)
            # 结果容器存在说明站点正常应答（哪怕 0 条）；缺失说明被限流回落到首页，重试
            if vods or ('class="stui-vodlist__media' in html_text):
                break
            if attempt < 2:
                await log("warn", "search keyword={} page={} 应答异常(无结果容器)，重试".format(keyword, page))
        pages = page_count(html_text, page)
        await log("info", "search keyword={} page={} 命中={} 总页={}".format(keyword, page, len(vods), pages))
        return page_result(page, pages, vods, pages * PAGE_SIZE)
    except Exception as error:
        await log("error", "search 失败 keyword={}: {}".format(keyword, error))
        return page_result(page, 1, [])


async def fetch_episodes(vid, sid):
    raw = await request_text("{}/play-eps/{}-{}/".format(SITE_URL, vid, sid),
                             referer="{}/yind/{}/".format(SITE_URL, vid))
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return []
    out = []
    if not isinstance(data, list):
        return []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        play_url = abs_url(item.get("u"))
        if not play_url:
            continue
        m = re.search(r"-(\d+)/?$", safe_text(item.get("u")))
        out.append({
            "name": clean_text(item.get("t")) or "第{}集".format(index + 1),
            "playId": play_url,
            "_n": int(m.group(1)) if m else index,
        })
    out.sort(key=lambda e: e["_n"])
    return [{"name": e["name"], "playId": e["playId"]} for e in out]


async def build_detail(vid):
    vid = re.sub(r"\D", "", safe_text(vid).rstrip("/").split("/")[-1])
    if not vid:
        return None
    url = "{}/yind/{}/".format(SITE_URL, vid)
    html_text = await request_text(url)
    if not html_text:
        return None

    def pick(pattern):
        m = re.search(pattern, html_text, re.S)
        return clean_text(m.group(1)) if m else ""

    pic = pick(r'<div class="stui-content__thumb">[\s\S]*?data-original="([^"]+)"')
    if not pic:
        pic = pick(r'<div class="stui-content__thumb">[\s\S]*?src="([^"]+)"')
    if pic.endswith("load.gif"):
        pic = ""
    content = pick(r'id="desc"[\s\S]*?<p class="col-pd">([\s\S]*?)</p>') or \
        pick(r'<p class="desc hidden-xs">([\s\S]*?)<a href="#desc">')

    line_names = {}
    for idx, tname in re.findall(r'switchPlayLine\(\s*(\d+)\s*\)"[^>]*>([^<]+)</a>', html_text):
        line_names[int(idx)] = clean_text(tname)
    panes = re.findall(r'id="playline(\d+)"[^>]*data-sid="(\d+)"', html_text)

    sources = []
    for idx_s, sid in panes:
        idx = int(idx_s)
        episodes = await fetch_episodes(vid, sid)
        if not episodes:
            continue
        sources.append({
            "name": line_names.get(idx) or "线路{}".format(idx + 1),
            "episodes": episodes,
        })
    await log("info", "detail id={} 线路={} 集数={}".format(
        vid, len(sources), [len(s["episodes"]) for s in sources]))

    return {
        "vod_id": vid,
        "vod_name": pick(r'<h1 class="title">(.*?)</h1>'),
        "vod_pic": abs_url(pic),
        "type_name": pick(r"类型：</span>(.*?)<"),
        "vod_year": pick(r"年份：</span>(.*?)<"),
        "vod_area": pick(r"地区：</span>(.*?)<"),
        "vod_actor": pick(r"主演：</span>(.*?)</p>"),
        "vod_director": pick(r"导演：</span>(.*?)</p>"),
        "vod_remarks": pick(r'<span class="pic-text text-right">(.*?)</span>'),
        "vod_content": content,
        "vod_play_sources": sources,
    }


async def detail(params, context):
    params = params or {}
    raw_ids = params.get("videoId") or params.get("ids") or params.get("id") or params.get("vodId") or ""
    if isinstance(raw_ids, (list, tuple)):
        ids = [safe_text(x) for x in raw_ids if safe_text(x)]
    else:
        ids = [x for x in safe_text(raw_ids).split(",") if x]
    try:
        items = []
        for vid in ids:
            try:
                item = await build_detail(vid)
                if item:
                    items.append(item)
            except Exception as error:
                await log("warn", "detail 单条失败 id={}: {}".format(vid, error))
        return {"list": items}
    except Exception as error:
        await log("error", "detail 失败: {}".format(error))
        return {"list": []}


async def play(params, context):
    params = params or {}
    play_id = safe_text(params.get("playId") or params.get("id") or params.get("url"))
    try:
        if not play_id:
            raise ValueError("播放地址不能为空")
        target = abs_url(play_id)
        html_text = await request_text(target, referer=SITE_URL + "/")
        real_url = ""
        m = re.search(r'var\s+videoSrc\s*=\s*["\']([^"\']+)["\']', html_text or "")
        if m:
            real_url = m.group(1).replace("\\/", "/").replace("\\u002F", "/").strip()
        if not real_url:
            m = re.search(r'https?://[^"\'\\\s]+?\.m3u8[^"\'\\\s]*', html_text or "")
            if m:
                real_url = m.group(0).replace("\\/", "/")
        header = {"User-Agent": UA, "Referer": SITE_URL + "/"}
        if not real_url:
            await log("warn", "play 未解析到播放地址 target={}".format(target))
            return {"urls": [], "header": header, "parse": 0}
        await log("info", "play ok host={} 直链={}".format(real_url.split("/")[2] if "/" in real_url else "", bool(VIDEO_EXT.search(real_url))))
        return {
            "urls": [{"name": "播放", "url": real_url}],
            "header": header,
            "parse": 0 if VIDEO_EXT.search(real_url) else 1,
        }
    except Exception as error:
        await log("error", "play 失败: {}".format(error))
        return {"urls": [], "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
