# -*- coding: utf-8 -*-
"""genchi.html 生成スクリプト — 現地で大谷さんを撮って届けてくれる個人チャンネル集
genchi_channels.json を読み、各チャンネルのRSSから最新動画を取得してページを作る。
gen_ohtani.py とは独立(こちらは手動 or 週1程度の実行でOK)。
使い方: python update_genchi.py
"""
import io, sys, json, re, time, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
JST = timezone(timedelta(hours=9))
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def subs_to_num(s):
    m = re.match(r"([\d.]+)万人", s)
    if m:
        return float(m.group(1)) * 10000
    m = re.match(r"([\d.]+)人", s)
    return float(m.group(1)) if m else 0

data = json.load(open("genchi_channels.json", encoding="utf-8"))
channels = data["channels"]

# ---- 各チャンネルの最新動画をRSSで取得 ----
for c in channels:
    c["latest"] = None
    try:
        root = ET.fromstring(get(f"https://www.youtube.com/feeds/videos.xml?channel_id={c['cid']}"))
        e = root.find("a:entry", NS)
        if e is not None:
            pub = datetime.fromisoformat(e.find("a:published", NS).text).astimezone(JST)
            c["latest"] = {
                "title": e.find("a:title", NS).text or "",
                "vid": e.find("yt:videoId", NS).text,
                "date": f"{pub.month}月{pub.day}日",
            }
        print("ok", c["name"], c["latest"]["date"] if c["latest"] else "-")
    except Exception as ex:
        print("skip", c["name"], ex)
    time.sleep(0.3)

# ---- イチ推し: featured のチャンネルから日付シードで日替わり ----
featured_pool = [c for c in channels if c.get("featured") and c.get("latest")]
today = datetime.now(JST)
seed = today.year * 10000 + today.month * 100 + today.day
pick = featured_pool[seed % len(featured_pool)] if featured_pool else channels[0]

def channel_url(c):
    return f"https://www.youtube.com/channel/{c['cid']}"

def video_url(v):
    return f"https://www.youtube.com/watch?v={v['vid']}"

def thumb(v, q="hqdefault"):
    return f"https://i.ytimg.com/vi/{v['vid']}/{q}.jpg"

# ---- イチ推しカード ----
pv = pick["latest"]
pick_html = f"""
  <div class="card pickcard">
    <div class="label" style="color:#c62828; font-weight:bold">🌟 今日のイチ推し現地チャンネル</div>
    <div class="pickname">{esc(pick['name'])}</div>
    <div class="picksubs">チャンネル登録 {esc(pick['subs'])}</div>
    <div class="pickcomment">{esc(pick['comment'])}</div>
    <a class="pickvid" href="{video_url(pv)}" target="_blank" rel="noopener">
      <img src="{thumb(pv, 'sddefault')}" alt="最新動画のサムネイル" loading="lazy">
      <span class="pickvt">▶ 最新動画({pv['date']}): {esc(pv['title'])}</span>
    </a>
    <a class="btn red" href="{channel_url(pick)}" target="_blank" rel="noopener">📺 このチャンネルを見に行く</a>
    <div class="note" style="text-align:center">イチ推しは毎日入れかわります(このページの更新時点)</div>
  </div>
"""

# ---- 一覧: 登録者規模別 ----
def card(c):
    v = c.get("latest")
    if v:
        vhtml = f"""<a class="chvid" href="{video_url(v)}" target="_blank" rel="noopener">
        <img src="{thumb(v)}" alt="" loading="lazy"><span class="chvt">▶ {pv_date(v)}: {esc(v['title'][:60])}{'…' if len(v['title']) > 60 else ''}</span></a>"""
    else:
        vhtml = ""
    return f"""
    <div class="chcard">
      <a class="chname" href="{channel_url(c)}" target="_blank" rel="noopener">{esc(c['name'])}</a>
      <div class="chsubs">チャンネル登録 {esc(c['subs'])}</div>
      <div class="chcomment">{esc(c['comment'])}</div>
      {vhtml}
    </div>"""

def pv_date(v):
    return f"最新 {v['date']}"

groups = [
    ("たくさんの人が見ている大チャンネル(登録10万人以上)", lambda n: n >= 100000),
    ("人気上昇中のチャンネル(登録1万〜10万人)", lambda n: 10000 <= n < 100000),
    ("これから楽しみな応援チャンネル(登録1万人未満)", lambda n: n < 10000),
]
list_html = ""
for title, cond in groups:
    members = [c for c in channels if cond(subs_to_num(c["subs"]))]
    members.sort(key=lambda c: -subs_to_num(c["subs"]))
    if not members:
        continue
    list_html += f'<h2 class="sec">{title}</h2>\n' + "\n".join(card(c) for c in members)

updated = datetime.now(JST).strftime("%Y年%m月%d日")

html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>現地で大谷さんを撮っている人たち | 今日の大谷さん</title>
<style>
  body {{ font-family: "Hiragino Sans", "Yu Gothic", Meiryo, sans-serif; margin: 0;
         background: #fffdf7; color: #222; line-height: 1.7; }}
  .wrap {{ max-width: 560px; margin: 0 auto; padding: 20px 14px 60px; }}
  h1 {{ font-size: 30px; text-align: center; margin: 8px 0 2px; }}
  .date {{ text-align: center; color: #5c5c5c; font-size: 18px; margin-bottom: 6px; }}
  .lead {{ font-size: 19px; text-align: center; color: #444; margin: 0 0 16px; }}
  .card {{ background: #fff; border: 3px solid #e0e0e0; border-radius: 18px;
           padding: 20px; margin-bottom: 16px; }}
  .pickcard {{ border-color: #c62828; }}
  .label {{ font-size: 21px; color: #666; text-align: center; }}
  .pickname {{ font-size: 30px; font-weight: bold; text-align: center; margin: 8px 0 2px; }}
  .picksubs {{ font-size: 18px; color: #5c5c5c; text-align: center; }}
  .pickcomment {{ font-size: 20px; text-align: center; margin: 8px 0 12px; }}
  .pickvid {{ display: block; text-decoration: none; color: #222; }}
  .pickvid img {{ width: 100%; border-radius: 12px; display: block; }}
  .pickvt {{ display: block; font-size: 18px; margin: 6px 0 10px; }}
  .btn {{ display: block; text-align: center; font-size: 22px; background: #1565c0;
          color: #fff; text-decoration: none; border-radius: 14px; padding: 14px;
          margin: 8px 0; }}
  .btn.red {{ background: #c62828; }}
  h2.sec {{ font-size: 24px; text-align: center; margin: 30px 0 10px; }}
  .chcard {{ background: #fff; border: 3px solid #e0e0e0; border-radius: 18px;
             padding: 16px; margin-bottom: 14px; }}
  .chname {{ font-size: 23px; font-weight: bold; color: #1565c0; text-decoration: underline; }}
  .chsubs {{ font-size: 16px; color: #5c5c5c; margin: 2px 0; }}
  .chcomment {{ font-size: 18px; margin: 4px 0 8px; }}
  .chvid {{ display: flex; gap: 10px; align-items: center; text-decoration: none; color: #222; }}
  .chvid img {{ width: 148px; border-radius: 10px; flex-shrink: 0; }}
  .chvt {{ font-size: 15px; line-height: 1.4; }}
  .note {{ font-size: 13px; color: #707070; }}
  .foot {{ text-align: center; color: #707070; font-size: 15px; margin-top: 24px; }}
</style></head><body><div class="wrap">
  <h1>📹 現地で大谷さんを<br>撮っている人たち</h1>
  <div class="date">{updated} 更新</div>
  <p class="lead">アメリカの球場まで足を運んで、大谷さんの姿を動画で届けてくれている個人のYouTubeチャンネル集です。みんなで応援しましょう。</p>

  {pick_html}

  <h2 class="sec">🔎 もっと探す(全{len(channels)}チャンネル)</h2>
  {list_html}

  <a class="btn" href="index.html">⚾ 「今日の大谷さん」トップへもどる</a>

  <div class="foot">非公式のファン情報ページです / 登録者数はおおよその数(更新日時点) / 掲載はすべて公開情報です。<br>掲載チャンネルはどれも応援の気持ちで紹介しています。</div>
</div><script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{{"token": "be81dd55e4c042b09b9763edd4863484"}}'></script></body></html>"""

open("genchi.html", "w", encoding="utf-8").write(html)
print("genchi.html written:", len(channels), "channels / pick =", pick["name"])
