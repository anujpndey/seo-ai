import json
import re
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from statistics import median
from urllib.parse import unquote, urlparse

import pandas as pd
import streamlit as st
import yt_dlp
from google import genai
from googleapiclient.discovery import build
from sqlalchemy import (
    Boolean, Column, DateTime, Integer, MetaData, String, Table, Text,
    and_, create_engine, delete, desc, func, insert, select, update,
)

# ================= SETTINGS =================
APP_NAME = "VidSEO Pro"
LOGIN_BUTTON_TEXT = "Continue with Google"
DAILY_LIMIT = 0  # 0 = unlimited analyses per user per day
PREFERRED_MODELS = [
    "gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest", "gemini-2.0-flash", "gemini-2.0-flash-lite",
]
BAD_MODEL_WORDS = ("image", "tts", "live", "audio", "embedding", "native", "robotics", "computer", "vision")
IST = timezone(timedelta(hours=5, minutes=30))
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SOCIAL_HOSTS = ("instagram.com", "tiktok.com", "facebook.com", "fb.watch",
                "twitter.com", "x.com", "linkedin.com", "pinterest.")

st.set_page_config(page_title=APP_NAME, page_icon="🔍", layout="wide", initial_sidebar_state="expanded")

LOGIN_CSS = """
<style>
[data-testid="stHeader"], [data-testid="stSidebar"], #MainMenu, footer {display: none !important;}
[data-testid="stAppViewContainer"] {
  background: linear-gradient(-45deg, #0b0f1f, #1b1464, #2a0f4d, #0b3a5b);
  background-size: 400% 400%; animation: bgShift 16s ease infinite;
}
@keyframes bgShift {0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%}}
.orb {position: fixed; border-radius: 50%; filter: blur(90px); opacity: .45; pointer-events: none; z-index: 0;}
.orb.o1 {width: 420px; height: 420px; background: #7c3aed; top: -120px; left: -100px; animation: floatA 14s ease-in-out infinite;}
.orb.o2 {width: 380px; height: 380px; background: #06b6d4; bottom: -140px; right: -80px; animation: floatB 17s ease-in-out infinite;}
.orb.o3 {width: 300px; height: 300px; background: #ec4899; top: 40%; left: 58%; animation: floatA 20s ease-in-out infinite reverse;}
@keyframes floatA {0%,100%{transform: translate(0,0)} 50%{transform: translate(60px,50px)}}
@keyframes floatB {0%,100%{transform: translate(0,0)} 50%{transform: translate(-70px,-40px)}}
.block-container {position: relative; z-index: 1; padding-top: 10vh; max-width: 560px; margin-left: auto; margin-right: auto;}
.st-key-login_box {
  background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.16);
  backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
  border-radius: 24px; padding: 38px 32px 30px; text-align: center;
  box-shadow: 0 25px 60px rgba(0,0,0,.45);
  animation: cardIn .9s cubic-bezier(.2,.8,.2,1) both;
}
@keyframes cardIn {from{opacity: 0; transform: translateY(30px) scale(.97)} to{opacity: 1; transform: none}}
.logo {font-size: 2.6rem; animation: pulse 3s ease-in-out infinite;}
@keyframes pulse {0%,100%{transform: scale(1)} 50%{transform: scale(1.12)}}
.login-title {color: #fff; font-size: 1.9rem; font-weight: 800; margin: 6px 0 4px;}
.login-sub {color: rgba(255,255,255,.7); margin-bottom: 10px;}
.rotator {position: relative; height: 1.7em; margin: 8px 0 20px; color: #c4b5fd; font-weight: 600;}
.rotator span {position: absolute; left: 0; right: 0; opacity: 0; animation: rot 12s infinite;}
.rotator span:nth-child(2) {animation-delay: 3s}
.rotator span:nth-child(3) {animation-delay: 6s}
.rotator span:nth-child(4) {animation-delay: 9s}
@keyframes rot {0%{opacity: 0; transform: translateY(12px)} 5%,25%{opacity: 1; transform: translateY(0)} 30%,100%{opacity: 0; transform: translateY(-12px)}}
.st-key-login_box .stButton > button {
  width: 100%; background: #fff !important; color: #111 !important; border: none !important;
  border-radius: 999px; padding: 12px 18px; font-weight: 600; transition: transform .2s, box-shadow .2s;
}
.st-key-login_box .stButton > button p {color: #111 !important; font-size: 1rem;}
.st-key-login_box .stButton > button:hover {transform: translateY(-2px); box-shadow: 0 10px 25px rgba(255,255,255,.25);}
.fine {color: rgba(255,255,255,.5); font-size: .78rem; margin-top: 14px;}
</style>
"""

APP_CSS = """
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 2rem; max-width: 1150px; margin-left: auto; margin-right: auto;}
.hero {
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #db2777 100%);
  padding: 26px 32px; border-radius: 18px; color: #fff; margin-bottom: 22px;
  box-shadow: 0 10px 30px rgba(79,70,229,.25);
}
.hero h1 {margin: 0; font-size: 1.9rem; color: #fff; font-weight: 800;}
.hero p {margin: 6px 0 0; opacity: .92;}
div[data-testid="stMetric"] {
  background: rgba(99,102,241,.08); border: 1px solid rgba(99,102,241,.28);
  padding: 14px 16px; border-radius: 12px;
}
.stButton > button {border-radius: 10px; font-weight: 600;}
button[kind="primary"] {background: linear-gradient(135deg, #4f46e5, #7c3aed); border: none; color: #fff;}
</style>
"""


def hero(title, sub):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{sub}</p></div>', unsafe_allow_html=True)


def secret(name, default=""):
    try:
        return st.secrets[name]
    except Exception:
        return default


# ================= DATABASE =================
@st.cache_resource
def get_db():
    url = secret("DATABASE_URL", "sqlite:///seo_history.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(url, pool_pre_ping=True)
    meta = MetaData()
    table = Table(
        "analyses", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_email", String(255), index=True),
        Column("platform", String(30)),
        Column("url", Text),
        Column("title", Text),
        Column("topic", Text),
        Column("data_json", Text),
        Column("ai_text", Text),
        Column("saved", Boolean, default=False),
        Column("created_at", DateTime),
    )
    meta.create_all(engine)
    return engine, table


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def db_add(email, data, url, topic, ai_text):
    engine, t = get_db()
    with engine.begin() as c:
        r = c.execute(insert(t).values(
            user_email=email, platform=data.get("platform", "Web"), url=url,
            title=display_title(data)[:300], topic=topic,
            data_json=json.dumps(data, ensure_ascii=False), ai_text=ai_text,
            saved=False, created_at=utcnow(),
        ))
        return r.inserted_primary_key[0]


def db_get(rid, email):
    engine, t = get_db()
    with engine.connect() as c:
        return c.execute(select(t).where(and_(t.c.id == rid, t.c.user_email == email))).mappings().first()


def db_list(email, only_saved=False, search="", limit=30):
    engine, t = get_db()
    q = select(t).where(t.c.user_email == email)
    if only_saved:
        q = q.where(t.c.saved.is_(True))
    if search:
        q = q.where(t.c.title.ilike(f"%{search}%"))
    q = q.order_by(desc(t.c.created_at))
    if limit:
        q = q.limit(limit)
    with engine.connect() as c:
        return c.execute(q).mappings().all()


def db_set_saved(rid, email, value):
    engine, t = get_db()
    with engine.begin() as c:
        c.execute(update(t).where(and_(t.c.id == rid, t.c.user_email == email)).values(saved=value))


def db_delete(rid, email):
    engine, t = get_db()
    with engine.begin() as c:
        c.execute(delete(t).where(and_(t.c.id == rid, t.c.user_email == email)))


def db_clear(email):
    engine, t = get_db()
    with engine.begin() as c:
        c.execute(delete(t).where(t.c.user_email == email))


def db_today_count(email):
    engine, t = get_db()
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    with engine.connect() as c:
        return c.execute(select(func.count()).select_from(t).where(
            and_(t.c.user_email == email, t.c.created_at >= start))).scalar() or 0


def db_stats(email):
    engine, t = get_db()
    mine = t.c.user_email == email
    with engine.connect() as c:
        total = c.execute(select(func.count()).select_from(t).where(mine)).scalar() or 0
        saved = c.execute(select(func.count()).select_from(t).where(and_(mine, t.c.saved.is_(True)))).scalar() or 0
        first = c.execute(select(func.min(t.c.created_at)).where(mine)).scalar()
        last = c.execute(select(func.max(t.c.created_at)).where(mine)).scalar()
        rows = c.execute(select(t.c.platform, func.count()).where(mine).group_by(t.c.platform)).all()
    return total, saved, first, last, {(p or "Other"): n for p, n in rows}


# ================= HELPERS =================
def yt_id(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def to_ist(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(IST)


def dur_secs(iso):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def fmt_secs(s):
    s = int(s or 0)
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    return f"{h}h {m}m {sec}s" if h else f"{m}m {sec}s"


def fmt_num(x):
    try:
        return f"{int(x):,}"
    except Exception:
        return "-"


def ist_label(dt):
    return (dt + timedelta(hours=5, minutes=30)).strftime("%d %b %Y, %I:%M %p") if dt else "-"


def normalize_url(u):
    u = (u or "").strip()
    if not u:
        return ""
    if not u.lower().startswith("http"):
        u = "https://" + u
    return u if "." in urlparse(u).netloc else ""


def avg_sorted(d, label):
    out = {label(k): round(sum(x) / len(x)) for k, x in d.items()}
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def timing_maps(rows):
    by_hour, by_day = {}, {}
    for t, v in rows:
        by_hour.setdefault(t.hour, []).append(v)
        by_day.setdefault(DAYS[t.weekday()], []).append(v)
    return avg_sorted(by_hour, lambda h: f"{h:02d}:00"), avg_sorted(by_day, lambda d: d)


def display_title(d):
    k = d.get("kind", "video")
    if k == "channel":
        return d.get("channel") or "Channel"
    if k == "profile":
        return d.get("account") or "Profile"
    if k == "page":
        return d.get("title") or d.get("url") or "Web page"
    if d.get("platform") == "YouTube":
        return d.get("title") or "Untitled"
    text = (d.get("description") or d.get("title") or "Untitled").strip()
    return text.split("\n")[0][:100]


def kind_label(d):
    names = {"video": "Video", "channel": "Channel", "profile": "Profile", "page": "Page"}
    return f"{d.get('platform', 'Web')} · {names.get(d.get('kind', 'video'), 'Video')}"


def get_transcript(vid):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        try:
            t = YouTubeTranscriptApi().fetch(vid, languages=["hi", "en"])
            return " ".join(x.text for x in t)[:6000]
        except AttributeError:
            t = YouTubeTranscriptApi.get_transcript(vid, languages=["hi", "en"])
            return " ".join(x["text"] for x in t)[:6000]
    except Exception:
        return ""


# ================= YOUTUBE =================
def youtube_video_data(url, key):
    vid = yt_id(url)
    if not vid:
        raise ValueError("Invalid YouTube video link.")
    yt = build("youtube", "v3", developerKey=key)
    res = yt.videos().list(part="snippet,statistics,contentDetails", id=vid).execute()
    if not res.get("items"):
        raise ValueError("Video not found (private, deleted or wrong link).")
    v = res["items"][0]
    s = v["snippet"]
    desc = s.get("description", "")

    rows = []
    try:
        uploads = "UU" + s["channelId"][2:]
        items = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=30).execute()["items"]
        ids = ",".join(i["contentDetails"]["videoId"] for i in items)
        for x in yt.videos().list(part="snippet,statistics", id=ids).execute()["items"]:
            rows.append((to_ist(x["snippet"]["publishedAt"]), int(x["statistics"].get("viewCount", 0))))
    except Exception:
        pass
    by_hour, by_day = timing_maps(rows)

    return {
        "kind": "video", "platform": "YouTube",
        "channel": s["channelTitle"], "title": s["title"], "description": desc,
        "tags": s.get("tags", []),
        "hashtags": re.findall(r"#\w+", s["title"] + " " + desc),
        "published_ist": to_ist(s["publishedAt"]).strftime("%d %b %Y, %I:%M %p"),
        "duration": fmt_secs(dur_secs(v["contentDetails"]["duration"])),
        "views": v["statistics"].get("viewCount"),
        "likes": v["statistics"].get("likeCount"),
        "comments": v["statistics"].get("commentCount"),
        "best_hours_avg_views": by_hour, "best_days_avg_views": by_day,
        "transcript": get_transcript(vid),
    }


def resolve_channel(yt, url):
    part = "snippet,statistics,brandingSettings,contentDetails"
    r = {}
    m = re.search(r"youtube\.com/(@[^/?#]+)", url)
    if m:
        r = yt.channels().list(part=part, forHandle=m.group(1)).execute()
    else:
        m = re.search(r"youtube\.com/channel/(UC[\w-]{22})", url)
        if m:
            r = yt.channels().list(part=part, id=m.group(1)).execute()
        else:
            m = re.search(r"youtube\.com/(?:c|user)/([^/?#]+)", url)
            if m:
                name = m.group(1)
                r = yt.channels().list(part=part, forUsername=name).execute()
                if not r.get("items"):
                    sr = yt.search().list(part="snippet", q=name, type="channel", maxResults=1).execute()
                    if sr.get("items"):
                        r = yt.channels().list(part=part, id=sr["items"][0]["snippet"]["channelId"]).execute()
    if not r.get("items"):
        raise ValueError("Channel not found. Please check the link.")
    return r["items"][0]


def channel_data(url, key):
    yt = build("youtube", "v3", developerKey=key)
    ch = resolve_channel(yt, unquote(url))
    sn, stt, cd = ch["snippet"], ch.get("statistics", {}), ch["contentDetails"]
    br = ch.get("brandingSettings", {}).get("channel", {})
    uploads = cd["relatedPlaylists"]["uploads"]

    ids = []
    try:
        pl = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50).execute()
        ids = [i["contentDetails"]["videoId"] for i in pl.get("items", [])]
    except Exception:
        pass
    vids = []
    if ids:
        vids = yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids)).execute().get("items", [])

    rows = []
    for v in vids:
        s2, st2 = v["snippet"], v.get("statistics", {})
        rows.append({
            "id": v["id"], "title": s2["title"], "desc": s2.get("description", ""), "tags": s2.get("tags", []),
            "views": int(st2.get("viewCount", 0)), "likes": int(st2.get("likeCount", 0)),
            "comments": int(st2.get("commentCount", 0)),
            "published": to_ist(s2["publishedAt"]), "secs": dur_secs(v["contentDetails"]["duration"]),
        })

    n = len(rows)
    views = [r["views"] for r in rows]
    total_views = sum(views)
    total_eng = sum(r["likes"] + r["comments"] for r in rows)
    times = sorted(r["published"] for r in rows)
    gaps = [(b - a).total_seconds() / 86400 for a, b in zip(times, times[1:])]
    by_hour, by_day = timing_maps([(r["published"], r["views"]) for r in rows])
    tags = Counter(t.lower() for r in rows for t in r["tags"])
    hashtags = Counter(h.lower() for r in rows for h in re.findall(r"#\w+", r["title"] + " " + r["desc"]))

    recent = [{
        "title": r["title"], "views": r["views"], "likes": r["likes"], "comments": r["comments"],
        "published": r["published"].strftime("%d %b %Y"), "duration": fmt_secs(r["secs"]),
        "url": f"https://www.youtube.com/watch?v={r['id']}",
    } for r in rows]

    return {
        "kind": "channel", "platform": "YouTube",
        "channel": sn["title"], "handle": sn.get("customUrl"), "country": sn.get("country"),
        "thumbnail": sn.get("thumbnails", {}).get("medium", {}).get("url"),
        "created": to_ist(sn["publishedAt"]).strftime("%d %b %Y"),
        "description": sn.get("description", ""), "channel_keywords": br.get("keywords", ""),
        "subscribers": None if stt.get("hiddenSubscriberCount") else stt.get("subscriberCount"),
        "total_views": stt.get("viewCount"), "video_count": stt.get("videoCount"),
        "videos_analyzed": n,
        "avg_views": round(total_views / n) if n else 0,
        "median_views": round(median(views)) if n else 0,
        "engagement_rate_pct": round(total_eng / total_views * 100, 2) if total_views else 0,
        "avg_days_between_uploads": round(sum(gaps) / len(gaps), 1) if gaps else None,
        "avg_duration": fmt_secs(sum(r["secs"] for r in rows) / n) if n else "-",
        "shorts_share_pct": round(sum(1 for r in rows if r["secs"] <= 60) / n * 100) if n else 0,
        "avg_title_length": round(sum(len(r["title"]) for r in rows) / n) if n else 0,
        "top_videos": sorted(recent, key=lambda x: -x["views"])[:5],
        "top_tags": tags.most_common(25), "top_hashtags": hashtags.most_common(15),
        "best_hours_avg_views": by_hour, "best_days_avg_views": by_day,
        "recent_videos": recent,
    }


# ================= OTHER PLATFORMS =================
def clean_platform(key):
    p = re.sub(r"(User|Playlist|Channel|Profile|Tab|Feed|Story|Stories)$", "", key or "")
    return "Web" if p in ("", "Generic") else p


def video_from_info(i):
    desc = i.get("description") or ""
    ts = i.get("timestamp")
    pub = datetime.fromtimestamp(ts, IST).strftime("%d %b %Y, %I:%M %p") if ts else i.get("upload_date")
    return {
        "kind": "video", "platform": clean_platform(i.get("extractor_key")),
        "account": i.get("uploader") or i.get("channel"),
        "title": i.get("title"), "description": desc, "tags": i.get("tags") or [],
        "hashtags": re.findall(r"#\w+", desc + " " + (i.get("title") or "")),
        "published_ist": pub,
        "duration": fmt_secs(i["duration"]) if i.get("duration") else None,
        "views": i.get("view_count"), "likes": i.get("like_count"), "comments": i.get("comment_count"),
    }


def profile_from_info(i, url):
    posts = []
    for e in list(i.get("entries") or [])[:30]:
        if not e:
            continue
        posts.append({
            "title": (e.get("title") or e.get("description") or "")[:150],
            "views": e.get("view_count"), "likes": e.get("like_count"),
            "date": e.get("upload_date"), "url": e.get("url") or e.get("webpage_url"),
        })
    return {
        "kind": "profile", "platform": clean_platform(i.get("extractor_key")),
        "account": i.get("uploader") or i.get("title") or i.get("id"),
        "description": i.get("description") or "", "followers": i.get("channel_follower_count"),
        "url": url, "posts": posts,
    }


def page_data(url):
    import requests
    from bs4 import BeautifulSoup
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    def meta(name=None, prop=None):
        tag = soup.find("meta", attrs={"name": name}) if name else soup.find("meta", attrs={"property": prop})
        return (tag.get("content") or "").strip() if tag else ""

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    canon = soup.find("link", rel="canonical")
    domain = urlparse(url).netloc
    links = [a.get("href") for a in soup.find_all("a", href=True)]
    imgs = soup.find_all("img")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return {
        "kind": "page", "platform": "Web Page", "url": url, "title": title,
        "meta_description": meta(name="description"), "meta_keywords": meta(name="keywords"),
        "canonical": canon.get("href") if canon else "",
        "og_title": meta(prop="og:title"), "og_description": meta(prop="og:description"),
        "og_image": meta(prop="og:image"),
        "h1": [h.get_text(" ", strip=True) for h in soup.find_all("h1")][:5],
        "h2": [h.get_text(" ", strip=True) for h in soup.find_all("h2")][:12],
        "word_count": len(soup.get_text(" ", strip=True).split()),
        "images_total": len(imgs), "images_missing_alt": sum(1 for i in imgs if not (i.get("alt") or "").strip()),
        "internal_links": sum(1 for h in links if h.startswith("/") or domain in h),
        "external_links": sum(1 for h in links if h.startswith("http") and domain not in h),
    }


def other_data(url):
    host = urlparse(url).netloc.lower()
    try:
        opts = {"quiet": True, "skip_download": True, "extract_flat": "in_playlist",
                "playlistend": 30, "socket_timeout": 20}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if info.get("_type") == "playlist" and info.get("entries"):
            return profile_from_info(info, url)
        return video_from_info(info)
    except Exception as e:
        if any(h in host for h in SOCIAL_HOSTS):
            raise ValueError("This platform blocked the request or needs login. Public links work best. "
                             "Please try again later or use another link.") from e
    return page_data(url)


def run_analysis(url, gkey):
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        if re.search(r"youtube\.com/(@|channel/|c/|user/)", u):
            return channel_data(url, gkey)
        if yt_id(url):
            return youtube_video_data(url, gkey)
        raise ValueError("Unsupported YouTube link. Use a video, Short or channel link.")
    return other_data(url)


# ================= GEMINI =================
def build_prompt(d, topic):
    kind = d.get("kind", "video")
    ai_d = dict(d)
    ai_d.pop("thumbnail", None)
    if "recent_videos" in ai_d:
        ai_d["recent_videos"] = [{k: v for k, v in x.items() if k != "url"} for x in ai_d["recent_videos"]]
    niche = f'My own topic/niche: "{topic}"' if topic else "My own topic/niche: same niche as the analyzed content"
    head = (f"You are a senior social media and SEO strategist. Analyze the {kind} data below "
            f"(platform: {d.get('platform')}). All times are IST. Reply in clear, practical English "
            f"using markdown headings. Be specific and avoid filler.\n\n{niche}\n\n"
            f"DATA:\n{json.dumps(ai_d, ensure_ascii=False, indent=1)}\n\n")

    if kind == "channel":
        body = """Give these sections:
## 1. Channel snapshot
Niche, target audience, positioning, and overall health.
## 2. What is working
Patterns in the top videos (topics, formats, length, title style).
## 3. Title and thumbnail patterns
## 4. Keywords and hashtags to target
Top 20 keywords and 15 hashtags.
## 5. Upload schedule and best posting time
## 6. Weaknesses and opportunities
## 7. 30-day growth plan
Week by week, concrete actions.
## 8. 10 video ideas for my niche
Each with a click-worthy title.
"""
    elif kind == "profile":
        body = """Give these sections:
## 1. Account snapshot
## 2. What content performs best
## 3. Hashtags and keywords to use (15 hashtags)
## 4. Posting strategy
## 5. 10 content ideas with captions for my niche
"""
    elif kind == "page":
        body = """Give these sections:
## 1. SEO score out of 100 (with a short reason)
## 2. Problems found (title, meta description, headings, images, links, content length)
## 3. Fix list, ordered by impact
## 4. Keyword suggestions (primary and secondary)
## 5. Rewritten title (under 60 chars) and meta description (under 155 chars)
## 6. Suggested heading structure (H1 and H2s)
"""
    else:
        body = """Give these sections:
## 1. Why this content works
Hook, keywords, emotion, format.
## 2. Top 10 keywords
For each, say where to use it (title / description / tags).
## 3. Best 15 hashtags
## 4. Best posting time
Use the timing data if present, otherwise give general advice for this platform.
## 5. Ready-to-use content for my topic
- 5 viral title options
- 1 full description (hook and keywords in the first 2 lines)
- 20 tags (comma separated, one line)
- 15 hashtags (one line)
- 3 thumbnail text ideas
"""
    return head + body


@st.cache_data(ttl=1800, show_spinner=False)
def list_gemini_models(api_key):
    client = genai.Client(api_key=api_key)
    return [m.name.replace("models/", "") for m in client.models.list()
            if "generateContent" in (m.supported_actions or [])]


def pick_models(api_key):
    """Auto-detect which Gemini models this key can use, best first."""
    try:
        names = list_gemini_models(api_key)
    except Exception:
        names = []
    if not names:
        return list(PREFERRED_MODELS)
    ordered = [m for m in PREFERRED_MODELS if m in names]
    extra = [n for n in names if "flash" in n and n not in ordered
             and not any(b in n for b in BAD_MODEL_WORDS)]
    return (ordered + extra) or list(PREFERRED_MODELS)


def ai_analysis(data, topic, key):
    gem_key = secret("GEMINI_API_KEY") or key
    client = genai.Client(api_key=gem_key)
    prompt = build_prompt(data, topic)
    models = pick_models(gem_key)
    last_err = None
    for attempt in range(3):
        for m in models:
            try:
                return client.models.generate_content(model=m, contents=prompt).text
            except Exception as e:
                last_err = e
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Gemini is busy or unavailable right now. Please try again in a minute. Details: {last_err}")


# ================= RENDERING =================
def render_times(d):
    bh, bd = d.get("best_hours_avg_views") or {}, d.get("best_days_avg_views") or {}
    if not (bh or bd):
        return
    st.markdown("##### Best posting time")
    if bh and bd:
        st.success(f"Best slot by average views: **{next(iter(bd))}**, around **{next(iter(bh))} IST**")
    a, b = st.columns(2)
    if bh:
        a.caption("Average views by upload hour (IST)")
        a.bar_chart(pd.Series(bh).sort_index())
    if bd:
        b.caption("Average views by weekday")
        b.bar_chart(pd.Series(bd).reindex([x for x in DAYS if x in bd]))


def render_video(d):
    c = st.columns(4)
    c[0].metric("Views", fmt_num(d.get("views")))
    c[1].metric("Likes", fmt_num(d.get("likes")))
    c[2].metric("Comments", fmt_num(d.get("comments")))
    c[3].metric("Duration", d.get("duration") or "-")
    who = d.get("channel") or d.get("account") or "-"
    st.write(f"**Platform:** {d.get('platform')}  |  **Account:** {who}  |  **Published (IST):** {d.get('published_ist') or '-'}")
    if d.get("title"):
        st.markdown("##### Title")
        st.code(d["title"], language=None)
    if d.get("description"):
        st.markdown("##### Description / Caption")
        st.code(d["description"], language=None)
    if d.get("tags"):
        st.markdown("##### Hidden keywords (tags)")
        st.code(", ".join(d["tags"]), language=None)
    st.markdown("##### Hashtags")
    st.code(" ".join(d.get("hashtags", [])) or "No hashtags found", language=None)
    render_times(d)


def render_channel(d):
    c0, c1 = st.columns([1, 6])
    if d.get("thumbnail"):
        c0.image(d["thumbnail"], width=90)
    c1.markdown(f"### {d['channel']}")
    c1.caption(" · ".join(x for x in [d.get("handle"), d.get("country"), f"Created {d.get('created')}"] if x))

    m = st.columns(4)
    m[0].metric("Subscribers", fmt_num(d.get("subscribers")) if d.get("subscribers") is not None else "Hidden")
    m[1].metric("Total views", fmt_num(d.get("total_views")))
    m[2].metric("Videos", fmt_num(d.get("video_count")))
    m[3].metric("Avg duration", d.get("avg_duration") or "-")
    n = d.get("videos_analyzed", 0)
    m2 = st.columns(4)
    m2[0].metric(f"Avg views (last {n})", fmt_num(d.get("avg_views")))
    m2[1].metric("Median views", fmt_num(d.get("median_views")))
    m2[2].metric("Engagement rate", f"{d.get('engagement_rate_pct', 0)}%")
    gap = d.get("avg_days_between_uploads")
    m2[3].metric("Upload every", f"{gap} days" if gap is not None else "-")

    if d.get("description"):
        st.markdown("##### Channel description")
        st.code(d["description"], language=None)
    if d.get("channel_keywords"):
        st.markdown("##### Channel keywords")
        st.code(d["channel_keywords"], language=None)
    if d.get("top_videos"):
        st.markdown("##### Top videos (last 50 uploads)")
        st.dataframe(pd.DataFrame(d["top_videos"])[["title", "views", "likes", "published", "duration"]], hide_index=True)
    if d.get("top_tags"):
        st.markdown("##### Most used tags")
        st.code(", ".join(t for t, _ in d["top_tags"]), language=None)
    if d.get("top_hashtags"):
        st.markdown("##### Most used hashtags")
        st.code(" ".join(t for t, _ in d["top_hashtags"]), language=None)
    render_times(d)
    if d.get("recent_videos"):
        with st.expander("All analyzed videos"):
            st.dataframe(pd.DataFrame(d["recent_videos"]), hide_index=True)


def render_profile(d):
    c = st.columns(3)
    c[0].metric("Followers", fmt_num(d.get("followers")))
    c[1].metric("Posts analyzed", len(d.get("posts", [])))
    c[2].metric("Platform", d.get("platform"))
    if d.get("description"):
        st.markdown("##### Bio / Description")
        st.code(d["description"], language=None)
    if d.get("posts"):
        st.markdown("##### Recent posts")
        st.dataframe(pd.DataFrame(d["posts"]), hide_index=True)


def render_page(d):
    c = st.columns(4)
    c[0].metric("Title length", len(d.get("title", "")), help="Ideal: 50-60 characters")
    c[1].metric("Meta description", len(d.get("meta_description", "")), help="Ideal: 120-155 characters")
    c[2].metric("Word count", fmt_num(d.get("word_count")))
    c[3].metric("Images missing alt", f"{d.get('images_missing_alt', 0)} / {d.get('images_total', 0)}")
    for label, val in [("Title", d.get("title")), ("Meta description", d.get("meta_description")),
                       ("Meta keywords", d.get("meta_keywords")), ("Canonical URL", d.get("canonical")),
                       ("Open Graph title", d.get("og_title")), ("Open Graph description", d.get("og_description"))]:
        if val:
            st.markdown(f"##### {label}")
            st.code(val, language=None)
    if d.get("h1"):
        st.markdown("##### H1 headings")
        st.code("\n".join(d["h1"]), language=None)
    if d.get("h2"):
        st.markdown("##### H2 headings")
        st.code("\n".join(d["h2"]), language=None)
    st.write(f"**Internal links:** {d.get('internal_links', 0)}  |  **External links:** {d.get('external_links', 0)}")


def render_result(data, ai_text, key):
    tab1, tab2 = st.tabs(["Data", "AI Analysis"])
    kind = data.get("kind", "video")
    with tab1:
        {"channel": render_channel, "profile": render_profile, "page": render_page}.get(kind, render_video)(data)
        with st.expander("Raw JSON"):
            st.json(data)
    with tab2:
        st.markdown(ai_text)
        st.download_button("Download report (.txt)", f"{display_title(data)}\n\n{ai_text}",
                           file_name="seo_report.txt", key=f"dl_{key}")


def show_detail(rid, email, key):
    row = db_get(rid, email)
    if not row:
        st.info("This item no longer exists.")
        return
    c1, c2 = st.columns([1.3, 6])
    if c1.button("★ Saved" if row["saved"] else "☆ Save", key=f"save_{key}"):
        db_set_saved(rid, email, not row["saved"])
        st.rerun()
    c2.caption(f"{row['url']}  ·  Analyzed {ist_label(row['created_at'])} IST")
    render_result(json.loads(row["data_json"]), row["ai_text"], key=key)


# ================= PAGES =================
def login_screen():
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    st.markdown('<div class="orb o1"></div><div class="orb o2"></div><div class="orb o3"></div>', unsafe_allow_html=True)
    with st.container(key="login_box"):
        st.markdown(
            '<div class="logo">🔍</div>'
            f'<div class="login-title">Welcome to {APP_NAME}</div>'
            '<div class="login-sub">Sign in to analyze videos, channels and web pages</div>'
            '<div class="rotator">'
            '<span>Decode any YouTube channel in seconds</span>'
            '<span>Find winning keywords and hashtags</span>'
            '<span>Get your best time to post</span>'
            '<span>Works with Instagram, TikTok and more</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.button(LOGIN_BUTTON_TEXT, on_click=st.login)
        st.markdown('<div class="fine">Secure sign-in. We never see your password.</div>', unsafe_allow_html=True)


def page_analyze(email, gkey):
    hero("Analyze any link", "Videos, Shorts, Reels, channels, profiles and web pages: full SEO and strategy breakdown")
    blocked = False
    if DAILY_LIMIT:
        left = max(DAILY_LIMIT - db_today_count(email), 0)
        blocked = left <= 0
        st.caption(f"Analyses left today: {left} / {DAILY_LIMIT}")

    with st.container(border=True):
        url = st.text_input("Link", label_visibility="collapsed",
                            placeholder="Paste a YouTube video / channel, Instagram, TikTok, Facebook, X link or any web page")
        topic = st.text_input("Your topic or niche (optional)", placeholder="e.g. Hindi vegetable moral stories")
        go = st.button("Analyze", type="primary", disabled=blocked)
    st.caption("Works with: YouTube (video, Shorts, channel) · Instagram · TikTok · Facebook · X/Twitter · other video sites · any web page")

    if go:
        link = normalize_url(url)
        if not link:
            st.warning("Please paste a valid link first.")
        else:
            try:
                with st.spinner("Fetching data..."):
                    data = run_analysis(link, gkey)
                with st.spinner("Generating AI analysis..."):
                    ai_text = ai_analysis(data, topic, gkey)
                st.session_state["current_id"] = db_add(email, data, link, topic, ai_text)
            except Exception as e:
                st.error(f"Something went wrong: {e}")

    rid = st.session_state.get("current_id")
    if rid:
        st.divider()
        show_detail(rid, email, key=f"cur{rid}")


def page_list(email, only_saved):
    tag = "saved" if only_saved else "history"
    oid = st.session_state.get("open_id")
    if oid:
        if st.button("← Back to list", key=f"back_{tag}"):
            st.session_state.pop("open_id", None)
            st.rerun()
        show_detail(oid, email, key=f"{tag}_open{oid}")
        return

    hero("Saved" if only_saved else "History",
         "Your favorite analyses" if only_saved else "Your recent analyses (latest 30)")
    search = st.text_input("Search", placeholder="Search by title...", label_visibility="collapsed")
    rows = db_list(email, only_saved, search.strip())
    if not rows:
        st.info("Nothing here yet.")
        return
    for r in rows:
        d = json.loads(r["data_json"])
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([6, 1.2, 1, 1])
            star = "⭐ " if r["saved"] else ""
            c1.markdown(f"**{star}{(r['title'] or 'Untitled')[:90]}**")
            c1.caption(f"{kind_label(d)} · {ist_label(r['created_at'])}")
            if c2.button("Open", key=f"o_{tag}_{r['id']}"):
                st.session_state["open_id"] = r["id"]
                st.rerun()
            if c3.button("★" if r["saved"] else "☆", key=f"s_{tag}_{r['id']}", help="Save / Unsave"):
                db_set_saved(r["id"], email, not r["saved"])
                st.rerun()
            if c4.button("🗑", key=f"d_{tag}_{r['id']}", help="Delete"):
                db_delete(r["id"], email)
                st.rerun()


def page_profile(email):
    hero("Profile", "Your account and activity")
    with st.container(border=True):
        c1, c2 = st.columns([1, 6])
        pic = st.user.get("picture")
        if pic:
            c1.image(pic, width=90)
        c2.markdown(f"### {st.user.get('name') or 'User'}")
        c2.caption(email)

    total, saved, first, last, by_platform = db_stats(email)
    m = st.columns(4)
    m[0].metric("Total analyses", total)
    m[1].metric("Saved", saved)
    m[2].metric("First activity", ist_label(first).split(",")[0] if first else "-")
    m[3].metric("Last activity", ist_label(last).split(",")[0] if last else "-")
    if by_platform:
        st.markdown("##### Analyses by platform")
        st.bar_chart(pd.Series(by_platform))

    st.markdown("##### Your data")
    rows = db_list(email, limit=None)
    export = json.dumps([{
        "title": r["title"], "platform": r["platform"], "url": r["url"], "saved": bool(r["saved"]),
        "created_at": str(r["created_at"]), "data": json.loads(r["data_json"]), "ai_analysis": r["ai_text"],
    } for r in rows], ensure_ascii=False, indent=1)
    st.download_button("Download all my data (JSON)", export, file_name="vidseo_export.json", mime="application/json")

    with st.expander("Danger zone"):
        sure = st.checkbox("I understand this permanently deletes all my history")
        if st.button("Delete all history", disabled=not sure):
            db_clear(email)
            st.session_state.pop("current_id", None)
            st.session_state.pop("open_id", None)
            st.success("History deleted.")

    st.divider()
    st.button("Log out", on_click=st.logout, key="logout_profile")


# ================= APP =================
try:
    logged_in = st.user.is_logged_in
except Exception:
    st.error("Login is not configured. Check the [auth] section in .streamlit/secrets.toml and restart the app.")
    st.stop()

if not logged_in:
    login_screen()
    st.stop()

st.markdown(APP_CSS, unsafe_allow_html=True)

gkey = secret("GOOGLE_API_KEY")
if not gkey:
    st.error("GOOGLE_API_KEY is missing in secrets.")
    st.stop()

email = st.user.get("email") or st.user.get("name") or "unknown"

with st.sidebar:
    st.markdown(f"### 🔍 {APP_NAME}")
    c1, c2 = st.columns([1, 3])
    pic = st.user.get("picture")
    if pic:
        c1.image(pic, width=40)
    c2.markdown(f"**{st.user.get('name') or 'User'}**")
    st.divider()
    page = st.radio("Menu", ["🔍 Analyze", "🕘 History", "⭐ Saved", "👤 Profile"], label_visibility="collapsed")
    st.divider()
    st.button("Log out", on_click=st.logout, key="logout_side")

if st.session_state.get("_page") != page:
    st.session_state.pop("open_id", None)
    st.session_state["_page"] = page

if page == "🔍 Analyze":
    page_analyze(email, gkey)
elif page == "🕘 History":
    page_list(email, only_saved=False)
elif page == "⭐ Saved":
    page_list(email, only_saved=True)
else:
    page_profile(email)