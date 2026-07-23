# -*- coding: utf-8 -*-
"""「今日の大谷さん」v2 — シニア向けデカ文字1ページ(全部入り)
MLB公式スタッツAPI+Google News RSSから自動生成。毎日の定時実行で自動更新。
"""
import io, sys, json, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
JST = timezone(timedelta(hours=9))
OHTANI = 660271

# ---- 米国東部時間(ET) ----
# MLBの「1日」は米東部時間で区切られる。日本の朝に実行すると米国では前日の試合が
# 終わった直後なので、ETの日付を基準に「どの日の成績まで反映済みか」を判定する。
def us_eastern_now():
    utc = datetime.now(timezone.utc)
    y = utc.year
    # 夏時間: 3月第2日曜 2:00 〜 11月第1日曜 2:00(現地時間)
    mar1 = datetime(y, 3, 1, tzinfo=timezone.utc)
    dst_start = mar1 + timedelta(days=(6 - mar1.weekday()) % 7 + 7, hours=7)   # 2:00 EST = 7:00 UTC
    nov1 = datetime(y, 11, 1, tzinfo=timezone.utc)
    dst_end = nov1 + timedelta(days=(6 - nov1.weekday()) % 7, hours=6)         # 2:00 EDT = 6:00 UTC
    offset = -4 if dst_start <= utc < dst_end else -5
    return utc.astimezone(timezone(timedelta(hours=offset)))

ET_NOW = us_eastern_now()
# ETでまだ試合中の時間帯(〜翌3時)は「前日分まで確定」とみなす
STATS_DATE_ET = (ET_NOW - timedelta(hours=3)).date()
SEASON = STATS_DATE_ET.year

# ポンポコ系列サイト相互リンク(URLは決まり次第ここに入れるだけ。空のものはフッターから自動で省かれる)
SISTER_SITES = [
    ("青春プレイバック", ""),
    ("ライフハック検証ラボ", ""),
    ("人生年表", ""),
    ("知ったかぶり知識人入門", ""),
    ("ことばの音ラボ", ""),
    ("スポーツ創設委員会", ""),
]

def sister_footer_html():
    links = [(n, u) for n, u in SISTER_SITES if u]
    if not links:
        return ""
    items = "".join(f'<a href="{u}">{n}</a>' for n, u in links)
    return f'<div class="sister-footer"><span class="sister-label">ポンポコ系列のサイト</span>{items}</div>'

# シニアも見るサイトなので他系列サイトより一回り大きめの文字サイズ
SISTER_CSS = """
  .sister-footer { max-width:560px; margin:24px auto 0; padding:18px 14px 0; border-top:1px solid #e0e0e0;
    text-align:center; font-size:16px; color:#5c5c5c; }
  .sister-footer .sister-label { display:block; margin-bottom:10px; font-weight:bold; font-size:17px; }
  .sister-footer a { color:#1565c0; margin:0 10px; text-decoration:underline; line-height:2.2; }
"""

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def get_json(url):
    return json.loads(get(url).decode())

def jst(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(JST)

def jdate(t):
    w = "月火水木金土日"[t.weekday()]
    return f"{t.month}月{t.day}日({w})"

# ---- 大谷: シーズン成績・直近試合 ----
d = get_json(f"https://statsapi.mlb.com/api/v1/people/{OHTANI}/stats?stats=season&group=hitting")
hit = d["stats"][0]["splits"][0]["stat"] if d["stats"] and d["stats"][0]["splits"] else {}
d = get_json(f"https://statsapi.mlb.com/api/v1/people/{OHTANI}/stats?stats=gameLog&group=hitting")
games = d["stats"][0]["splits"] if d["stats"] else []
last = games[-1] if games else None

if last:
    s = last["stat"]
    t = datetime.fromisoformat(last["date"])
    gdate = f"{t.month}月{t.day}日"
    ab, h, hr, rbi = int(s.get("atBats", 0)), int(s.get("hits", 0)), int(s.get("homeRuns", 0)), int(s.get("rbi", 0))
    if hr > 0:
        headline, color = f"ホームラン {hr}本!🎉", "#d32f2f"
    elif h > 0:
        headline, color = f"ヒット {h}本", "#1565c0"
    else:
        headline, color = "ヒットなし", "#555"
    line = f"{ab}打数{h}安打" + (f" {rbi}打点" if rbi else "")
else:
    gdate, headline, line, color = "-", "データ取得中", "", "#555"

# ---- 1週間の試合予定(日本時間) ----
p = get_json(f"https://statsapi.mlb.com/api/v1/people/{OHTANI}?hydrate=currentTeam")
team_id = p["people"][0].get("currentTeam", {}).get("id", 119)
today = datetime.now(JST).strftime("%Y-%m-%d")
end = (datetime.now(JST) + timedelta(days=8)).strftime("%Y-%m-%d")
sch = get_json(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&startDate={today}&endDate={end}&hydrate=team")
week_rows = []
for day in sch.get("dates", []):
    for g in day.get("games", []):
        t = jst(g["gameDate"])
        home = g["teams"]["home"]["team"].get("name", "")
        away = g["teams"]["away"]["team"].get("name", "")
        opp = away if "Dodgers" in home else home
        state = g.get("status", {}).get("abstractGameState", "")
        mark = "🔴試合中" if state == "Live" else ""
        week_rows.append(f"<tr><td>{jdate(t)}</td><td>{t.hour}時{t.minute:02d}分</td><td>{opp} 戦 {mark}</td></tr>")
week_html = "\n".join(week_rows) if week_rows else "<tr><td colspan=3>予定を取得中</td></tr>"

# ---- ニュース(Google News RSS) ----
news_html = ""
try:
    q = urllib.parse.quote("大谷翔平")
    rss = get(f"https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja")
    root = ET.fromstring(rss)
    items = root.findall(".//item")[:6]
    for it in items:
        title = it.findtext("title", "")
        link = it.findtext("link", "")
        when = ""
        try:
            pt = parsedate_to_datetime(it.findtext("pubDate", "")).astimezone(JST)
            when = f'<span class="ntime">{pt.month}月{pt.day}日 {pt.hour}時{pt.minute:02d}分 配信</span>'
        except Exception:
            pass
        news_html += f'<a class="news" href="{link}" target="_blank">・{title}{when}</a>\n'
except Exception as e:
    news_html = "<div>ニュースを取得できませんでした</div>"

# ---- YouTube動画サムネイル(チャンネルRSS・APIキー不要) ----
YT_CHANNELS = [
    ("MLB公式", "UCoLrcjPV5PbUrUyXq5mjc_A"),
    ("ドジャース公式", "UC05cNJvMKzDLRPo59X2Xx7g"),
    ("MLB Japan", "UCJrBiHVYO_jiFU1avGUCm3w"),
    ("SPOTV NOW", "UCJ-l-sMQFHogSy8KXRyMIRA"),
    ("MLB Network", "UCnfdlSStduhKXE9Qp9-edsA"),
    # 現地ファンのチャンネルを足すときはここに ("表示名", "チャンネルID") を追記
]
OHTANI_WORDS = ("ohtani", "shohei", "大谷")
vids = []
for chname, cid in YT_CHANNELS:
    try:
        rss = get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
        r = ET.fromstring(rss)
        ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
        for e in r.findall("a:entry", ns):
            title = e.findtext("a:title", "", ns)
            vid = e.findtext("yt:videoId", "", ns)
            pub = e.findtext("a:published", "", ns)
            if not vid:
                continue
            tl = title.lower()
            if any(w in tl for w in OHTANI_WORDS):
                vids.append((pub, title, vid, chname, 0))
            elif ("highlight" in tl and "dodgers" in tl) or "日本人" in tl:
                vids.append((pub, title, vid, chname, 1))  # 大谷が少ない日の補欠(試合ハイライト・日本人特集)
    except Exception:
        continue
# 新しい順に並べ、大谷本人の動画(優先度0)を先頭グループに
vids.sort(key=lambda v: v[0], reverse=True)
vids.sort(key=lambda v: v[4])
vids_html = ""
for pub, title, vid, chname, _p in vids[:12]:
    ptxt = ""
    try:
        pd = datetime.fromisoformat(pub).astimezone(JST)
        ptxt = f"{pd.month}/{pd.day}"
    except Exception:
        pass
    vids_html += f'''<a class="gvid" href="https://www.youtube.com/watch?v={vid}" target="_blank">
      <img src="https://i.ytimg.com/vi/{vid}/mqdefault.jpg" alt="" loading="lazy">
      <span class="vt">{title}</span><span class="vc">{chname}{" ・ " + ptxt if ptxt else ""}</span></a>\n'''

# ---- Xのみんなの反応(公式oEmbed埋め込み・APIキー不要) ----
# X公式の検索取得は有料APIのみのため、載せたいポストのURLを x_posts.json に手で追記する方式。
# 例: {"posts": ["https://x.com/MLB/status/123456789"]}
# oEmbed(publish.twitter.com)は規約内の公式埋め込み手段。転載ではなくX公式の埋め込みコードを使う。
x_embeds_html = ""
x_embed_count = 0
try:
    xp = json.load(open("x_posts.json", encoding="utf-8"))
    for post_url in xp.get("posts", [])[:8]:
        try:
            oe = get_json("https://publish.twitter.com/oembed?omit_script=true&lang=ja&url="
                          + urllib.parse.quote(post_url, safe=""))
            x_embeds_html += oe.get("html", "")
            x_embed_count += 1
        except Exception:
            continue
except FileNotFoundError:
    pass
if x_embeds_html:
    x_embeds_html += '<script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>'

# ---- 他の日本人メジャーリーガー ----
PLAYERS = ["Yoshinobu Yamamoto", "Roki Sasaki", "Shota Imanaga", "Seiya Suzuki",
           "Yu Darvish", "Kodai Senga", "Masataka Yoshida"]
JP_NAMES = {"Yoshinobu Yamamoto": "山本由伸", "Roki Sasaki": "佐々木朗希", "Shota Imanaga": "今永昇太",
            "Seiya Suzuki": "鈴木誠也", "Yu Darvish": "ダルビッシュ有", "Kodai Senga": "千賀滉大",
            "Masataka Yoshida": "吉田正尚"}
others_rows = []
for name in PLAYERS:
    try:
        r = get_json(f"https://statsapi.mlb.com/api/v1/people/search?names={urllib.parse.quote(name)}")
        people = r.get("people", [])
        if not people:
            continue
        pid = people[0]["id"]
        is_pitcher = people[0].get("primaryPosition", {}).get("abbreviation") == "P"
        grp = "pitching" if is_pitcher else "hitting"
        sd = get_json(f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=season&group={grp}&season={SEASON}")
        splits = sd["stats"][0]["splits"] if sd["stats"] else []
        if not splits:
            continue
        st = splits[0]["stat"]
        if is_pitcher:
            info = f"防御率 {st.get('era','-')} / {st.get('wins','-')}勝{st.get('losses','-')}敗 / 奪三振 {st.get('strikeOuts','-')}"
        else:
            info = f"打率 {st.get('avg','-')} / HR {st.get('homeRuns','-')}本 / 打点 {st.get('rbi','-')}"
        others_rows.append(f"<tr><td><b>{JP_NAMES.get(name, name)}</b></td><td>{info}</td></tr>")
    except Exception:
        continue
others_html = "\n".join(others_rows) if others_rows else "<tr><td>取得中</td></tr>"
# アメリカの「1日」が終わったタイミング(米東部時間)を基準に、いつ時点の成績かを明記
others_note = f"米国時間 {STATS_DATE_ET.month}月{STATS_DATE_ET.day}日 の試合終了分まで反映(日本の朝に更新すると前夜の米国の試合結果が入ります)"

# ---- 元気なお年寄りコーナー(手動更新: genki.json があれば表示) ----
genki_html = ""
try:
    g = json.load(open("genki.json", encoding="utf-8"))
    items = "".join(
        f'<p style="font-size:19px; margin:8px 0"><b>{e["title"]}</b><br>{e["body"]}'
        + (f'<br><a href="{e["url"]}" target="_blank" style="color:#1565c0">くわしく見る</a>' if e.get("url") else "")
        + "</p>"
        for e in g.get("items", [])[:3]
    )
    if items:
        genki_html = f"""
  <div class="card">
    <div class="label">💪 今週の元気なお年寄り</div>
    {items}
  </div>"""
except FileNotFoundError:
    pass

season_hr, season_avg, season_rbi = hit.get("homeRuns", "-"), hit.get("avg", "-"), hit.get("rbi", "-")
updated = datetime.now(JST).strftime("%m月%d日 %H:%M")
yt = "https://www.youtube.com/results?search_query=" + urllib.parse.quote("大谷翔平 ハイライト")
xs = "https://x.com/search?q=" + urllib.parse.quote("大谷翔平") + "&f=live"
nhk = "https://www.nhk.jp/timetable/"

html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>今日の大谷さん</title>
<style>
  body {{ font-family: "Hiragino Sans", "Yu Gothic", Meiryo, sans-serif; margin: 0;
         background: #fffdf7; color: #222; line-height: 1.7; }}
  .wrap {{ max-width: 560px; margin: 0 auto; padding: 20px 14px 60px; }}
  h1 {{ font-size: 34px; text-align: center; margin: 8px 0 2px; }}
  .date {{ text-align: center; color: #5c5c5c; font-size: 18px; margin-bottom: 16px; }}
  .card {{ background: #fff; border: 3px solid #e0e0e0; border-radius: 18px;
           padding: 20px; margin-bottom: 16px; }}
  .center {{ text-align: center; }}
  .label {{ font-size: 21px; color: #666; text-align: center; }}
  .big {{ font-size: 42px; font-weight: bold; margin: 6px 0; text-align: center; }}
  .mid {{ font-size: 26px; text-align: center; }}
  .stats {{ display: flex; justify-content: space-around; }}
  .stats div {{ font-size: 18px; color: #666; text-align: center; }}
  .stats b {{ display: block; font-size: 30px; color: #222; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 19px; }}
  td {{ padding: 8px 4px; border-bottom: 1px solid #eee; }}
  .news {{ display: block; font-size: 19px; padding: 7px 0; color: #1565c0;
           text-decoration: none; border-bottom: 1px solid #eee; }}
  .btn {{ display: block; text-align: center; font-size: 22px; background: #1565c0;
          color: #fff; text-decoration: none; border-radius: 14px; padding: 14px;
          margin: 8px 0; }}
  .btn.red {{ background: #c62828; }}
  .btn.green {{ background: #2e7d32; }}
  .foot {{ text-align: center; color: #707070; font-size: 15px; }}
  .vid {{ display: flex; gap: 10px; align-items: center; text-decoration: none;
          color: #222; padding: 8px 0; border-bottom: 1px solid #eee; }}
  .vid img {{ width: 148px; border-radius: 10px; flex-shrink: 0; }}
  .vt {{ font-size: 17px; line-height: 1.4; display: block; }}
  .vc {{ font-size: 14px; color: #707070; display: block; margin-top: 2px; }}
  .ntime {{ display: block; font-size: 14px; color: #707070; margin-left: 1em; }}
  .vgrid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .gvid {{ text-decoration: none; color: #222; display: block; }}
  .gvid img {{ width: 100%; border-radius: 10px; display: block; }}
  .gvid .vt {{ font-size: 15px; margin-top: 4px; }}
  .xembeds {{ margin-top: 10px; }}
  th {{ text-align: left; font-size: 14px; color: #707070; padding: 4px; border-bottom: 2px solid #ddd; }}
  .note {{ font-size: 13px; color: #707070; }}
  .tblnote {{ margin-top: 8px; text-align: center; }}
  .mininote {{ font-size: 14px; color: #5c5c5c; text-align: center; margin: 4px 0 2px; }}
  h2.sec {{ font-size: 26px; text-align: center; margin: 26px 0 10px; }}
{SISTER_CSS}
</style></head><body><div class="wrap">
  <h1>⚾ 今日の大谷さん</h1>
  <div class="date">{updated} 更新</div>

  <div class="card">
    <div class="label">{gdate}の試合</div>
    <div class="big" style="color:{color}">{headline}</div>
    <div class="mid">{line}</div>
  </div>

  <div class="card" style="border-color:#1565c0">
    <div class="label" style="color:#1565c0; font-weight:bold">📅 これからの試合(日本時間)</div>
    <table>{week_html}</table>
  </div>

  <div class="card">
    <div class="label">今シーズンの成績</div>
    <div class="stats">
      <div>ホームラン<b>{season_hr}本</b></div>
      <div>打率<b>{season_avg}</b></div>
      <div>打点<b>{season_rbi}</b></div>
    </div>
    <a class="btn green" href="#zenseiseki">📊 くわしい全成績はこのページの下へ</a>
  </div>

  <div class="card" style="border-color:#c62828">
    <div class="label" style="color:#c62828; font-weight:bold">🔥 大谷さんの動画とみんなの反応</div>
    <div class="vgrid">
    {vids_html if vids_html else '<p style="font-size:18px;text-align:center">新しい動画を探しています</p>'}
    </div>
    <a class="btn red" href="{yt}" target="_blank">▶ もっとYouTubeで見る</a>
    <div class="xembeds">
    {x_embeds_html}
    </div>
    <a class="btn" href="{xs}" target="_blank">💬 Xでみんなの反応をもっと見る</a>
  </div>

  <div class="card">
    <div class="label">大谷さんのニュース</div>
    {news_html}
  </div>{genki_html}

<!--ZENSEISEKI-->

  <div class="card">
    <div class="label">日本人メジャーリーガーの成績</div>
    <table>{others_html}</table>
    <div class="note tblnote">{others_note}</div>
  </div>

  <div class="foot">非公式のファン情報ページです / 成績: MLB公式データより自動取得</div>
  {sister_footer_html()}
</div></body></html>"""
# ※ index.html はこの後、全成績カードを差し込んでから書き出す(ファイル末尾参照)

# ---- お父さん用スワイプ版 app.html(大谷+相撲+天気)2026-07-19 ----
# 天気の地点: 東京(変更はWX_LAT/WX_LONを書き換え)
WX_LAT, WX_LON, WX_NAME = 35.68, 139.76, "東京"
wx_html = ""
try:
    w = get_json(f"https://api.open-meteo.com/v1/forecast?latitude={WX_LAT}&longitude={WX_LON}&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code&timezone=Asia%2FTokyo&forecast_days=1")
    dd = w["daily"]
    code_map = {0:"晴れ☀",1:"だいたい晴れ☀",2:"ときどき曇り⛅",3:"曇り☁",45:"霧",48:"霧",51:"小雨🌂",53:"小雨🌂",55:"雨☔",61:"雨☔",63:"雨☔",65:"大雨☔",80:"にわか雨🌂",81:"にわか雨☔",82:"大雨☔",95:"雷雨⚡"}
    wmark = code_map.get(dd["weather_code"][0], "")
    hi, lo, pp = dd["temperature_2m_max"][0], dd["temperature_2m_min"][0], dd["precipitation_probability_max"][0]
    advice = "暑いので水分を🍵" if hi >= 30 else ("上着があると安心です" if hi < 18 else "すごしやすい一日です")
    wx_html = f'<div class="hbig">{wmark}</div><div class="hmid">最高 {hi:.0f}度 / 最低 {lo:.0f}度</div><div class="hmid">雨のかくりつ {pp}%</div><div class="hmid" style="color:#1565c0;margin-top:10px">{advice}</div>'
except Exception:
    wx_html = '<div class="hmid">天気を取得できませんでした</div>'

# 相撲: 場所中なら前日(または当日)の幕内上位の結果
sumo_html = ""
try:
    now = datetime.now(JST)
    basho_id = None
    for bid, start in (("202607", "2026-07-12"), ("202609", "2026-09-13")):
        s = datetime.fromisoformat(start).replace(tzinfo=JST)
        if s <= now <= s + timedelta(days=15):
            basho_id, day = bid, min(15, (now - s).days + 1)
    if basho_id:
        tk = get_json(f"https://www.sumo-api.com/api/basho/{basho_id}/torikumi/Makuuchi/{day}")
        rows = []
        for m in (tk.get("torikumi") or [])[-6:]:
            e, w2 = m.get("eastShikona",""), m.get("westShikona","")
            win = m.get("winnerEn") or ""
            if win:
                wj = e if win == m.get("eastShikona") else w2
                rows.append(f"<tr><td>{e} × {w2}</td><td><b>○{wj}</b></td></tr>")
            else:
                rows.append(f"<tr><td>{e} × {w2}</td><td>これから</td></tr>")
        sumo_html = f'<div class="hmid">名古屋場所 {day}日目</div><table>{"".join(rows)}</table>'
    else:
        sumo_html = '<div class="hmid">いまは場所と場所のあいだです<br>次の場所をおたのしみに</div>'
except Exception:
    sumo_html = '<div class="hmid">相撲の情報を取得できませんでした</div>'

now_m = datetime.now(JST).month
now_wd = datetime.now(JST).weekday()

# 家庭菜園: 月別作業ヒント(自作データ・毎月自動で切替)
SAIEN = {
 1:"寒おこし(畑を掘って寒さに当てる)/植える: 絹さやの支柱直し",
 2:"じゃがいもの種いも準備/土づくりに石灰をまく",
 3:"じゃがいも植え付け/レタス・小松菜の種まき",
 4:"夏野菜(トマト・なす・きゅうり)の苗を植える/霜に注意",
 5:"支柱立てと誘引/わき芽かき開始/水やりは朝",
 6:"梅雨の病気予防(風通しをよく)/追肥を忘れずに",
 7:"トマトのわき芽かき/水やりは朝夕の涼しい時間に/雑草取りは涼しい日に",
 8:"秋野菜の準備(にんじん種まき)/朝の水やりが大事/台風対策",
 9:"大根・かぶ・ほうれん草の種まき/白菜の苗植え",
 10:"玉ねぎの植え付け準備/さつまいも収穫",
 11:"玉ねぎ苗の植え付け/えんどうの種まき",
 12:"畑の片づけと土づくり/絹さやの防寒",
}
saien_html = f'<div class="hmid">{now_m}月の畑しごと</div><div class="hmid" style="margin-top:10px;text-align:left;font-size:26px">' + "<br>・".join(["・"+SAIEN[now_m]] if False else ("・"+SAIEN[now_m]).split("/")) + "</div>"

# 健康ひとこと: 気温連動+曜日の一般アドバイス(医療アドバイスはしない)
try:
    _hi = hi
except NameError:
    _hi = 25
if _hi >= 33: kenko = "きけんな暑さです。外の仕事はやめて、エアコンと水分を。"
elif _hi >= 30: kenko = "暑い日です。畑や散歩は朝のうちに。こまめに水分を。"
elif _hi < 10: kenko = "冷えこみます。あたたかくして、お風呂の温度差に気をつけて。"
else: kenko = "すごしやすい気温です。散歩びよりです。"
weekly = {0:"週のはじまり。ラジオ体操からどうぞ",1:"ストレッチで肩と腰をのばす日",2:"きょうは歩数を気にしてみる日",3:"ゆっくりお風呂の日",4:"好きなものを食べていい日",5:"家族に電話してみる日",6:"ゆっくり休む日"}
kenko_html = f'<div class="hmid">{kenko}</div><div class="hmid" style="color:#1565c0;margin-top:14px">{weekly[now_wd]}</div>'


# ---- 日めくり動画(偶然の法則: たまたまの出会いを毎日製造。寅さんの法則: 今日の分だけ) ----
MEGURI_CH = {
  "いぬ": ["UC93O_mvkSvPHQDqPMJbl9Aw", "UCGr2Xt-YPhJ0HcHt6oJvyLg", "UCMMhK-o0Txrl_a7ta4YvuQQ", "UCgjULi89KwwEFcYHvsDRyXw"],
  "はたけの動画": ["UCCnJI0bngVas3kDgC-um6og"],
  "おすもうの動画": ["UC80hf_CYCu3mm841BibQQTQ"],
}
try:
    seen = set(json.load(open("seen_videos.json", encoding="utf-8")))
except Exception:
    seen = set()
import random as _rnd
_rnd.seed(datetime.now(JST).strftime("%Y%m%d"))
meguri_cards = []
new_seen = set(seen)
for theme, cids in MEGURI_CH.items():
    pool = []
    for cid in cids:
        try:
            rss = get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
            r = ET.fromstring(rss)
            ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
            for e in r.findall("a:entry", ns):
                vid = e.findtext("yt:videoId", "", ns)
                title = e.findtext("a:title", "", ns)
                if vid and vid not in seen:
                    pool.append((vid, title))
        except Exception:
            continue
    if pool:
        vid, title = _rnd.choice(pool)
        new_seen.add(vid)
        label = "きょうの" + ("わんちゃん" if theme == "いぬ" else theme)
        meguri_cards.append((label,
            f'''<a class="vidbig" href="https://www.youtube.com/watch?v={vid}" target="_blank">
            <img src="https://i.ytimg.com/vi/{vid}/hqdefault.jpg" alt="">
            <span class="vt2">{title}</span>
            <span class="tap">▶ 押すと見られます</span></a>
            <div class="once">きょうだけの1本です(あしたは別の動画)</div>'''))
json.dump(sorted(new_seen), open("seen_videos.json", "w", encoding="utf-8"))

def _card(label, body):
    return f'<section class="cardp"><div class="lab">{label}</div>{body}</section>'

vids_app = ""
for pub, title, vid, chname, _p in vids[:3]:
    vids_app += (f'<a class="vid" href="https://www.youtube.com/watch?v={vid}" target="_blank">'
                 f'<img src="https://i.ytimg.com/vi/{vid}/mqdefault.jpg" alt="" loading="lazy">'
                 f'<span class="vt">{title}</span></a>')
cards = [
    _card("きょうの天気(" + WX_NAME + ")", wx_html),
    _card(f"{gdate}の大谷さん", f'<div class="hbig" style="color:{color}">{headline}</div><div class="hmid">{line}</div>'),
    _card("大谷さんの今シーズン", f'<div class="hmid">ホームラン</div><div class="hbig">{season_hr}本</div><div class="hmid">打率 {season_avg} / 打点 {season_rbi}</div><a class="golink" href="index.html#zenseiseki">📊 全成績を見る</a>'),
    _card("おすもう", sumo_html),
    _card("はたけ・家庭菜園", saien_html),
    _card("きょうの健康ひとこと", kenko_html),
] + [_card(lb, bd) for lb, bd in meguri_cards] + [
    _card("これからの試合(日本時間)", f"<table>{week_html}</table>"),
    _card("さいしんの動画(押すと再生)", vids_app or '<div class="hmid">探しています</div>'),
    _card("きょうのニュース", news_html),
]
app_html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>大谷さんと天気</title>
<style>
  body {{ margin:0; font-family:"Hiragino Sans","Yu Gothic",Meiryo,sans-serif; color:#222; }}
  .snap {{ height:100dvh; overflow-y:scroll; scroll-snap-type:y mandatory; }}
  .cardp {{ height:100dvh; scroll-snap-align:start; display:flex; flex-direction:column;
           justify-content:center; padding:22px; box-sizing:border-box; border-bottom:4px solid #eee; background:#fffdf7; }}
  .lab {{ font-size:26px; color:#5c5c5c; text-align:center; margin-bottom:12px; }}
  .hbig {{ font-size:56px; font-weight:bold; text-align:center; margin:6px 0; }}
  .hmid {{ font-size:30px; text-align:center; line-height:1.6; }}
  table {{ width:100%; border-collapse:collapse; font-size:23px; }}
  td {{ padding:9px 4px; border-bottom:1px solid #eee; }}
  .news {{ display:block; font-size:23px; padding:11px 0; color:#1565c0; text-decoration:none; border-bottom:1px solid #eee; }}
  .vid {{ display:flex; gap:12px; align-items:center; text-decoration:none; color:#222; padding:10px 0; border-bottom:1px solid #eee; }}
  .vid img {{ width:150px; border-radius:10px; }}
  .vt {{ font-size:20px; line-height:1.4; }}
  .vidbig {{ display:block; text-decoration:none; color:#222; text-align:center; }}
  .vidbig img {{ width:100%; border-radius:14px; }}
  .vt2 {{ display:block; font-size:24px; line-height:1.5; margin-top:8px; }}
  .tap {{ display:block; font-size:26px; color:#fff; background:#c62828; border-radius:14px; padding:12px; margin-top:10px; }}
  .once {{ text-align:center; color:#5c5c5c; font-size:19px; margin-top:10px; }}
  .golink {{ display:block; text-align:center; font-size:24px; color:#fff; background:#2e7d32; border-radius:14px; padding:12px; margin-top:16px; text-decoration:none; }}
  .hint {{ position:fixed; bottom:8px; left:0; right:0; text-align:center; color:#bbb; font-size:17px; pointer-events:none; }}
{SISTER_CSS}
</style></head><body>
<div class="snap">
{"".join(cards)}
<section class="cardp"><div class="lab">おしまい</div><div class="hmid">下へスライドすると<br>もどれます</div><div class="hmid" style="color:#5c5c5c;margin-top:18px;font-size:20px">{updated} こうしん</div>{sister_footer_html()}</section>
</div>
<div class="hint">⬆ 上にスライドすると次のページ</div>
</body></html>"""
open("app.html", "w", encoding="utf-8").write(app_html)
print("app.html 出力OK(カード", len(cards)+1, "枚)")


# ================================================================
# ==== 全成績(2026-07-24からトップページに統合) ====
# MLB公式StatsAPIから状況別打率(statSplits)/月別(byMonth)/直近試合(gameLog)/
# 投手成績(登板があれば)を取得。取得できなかった項目はページに載せない(捏造しない)。
# ================================================================
SEISEKI_SEASON = SEASON

def _sd(st, key):
    v = st.get(key)
    return str(v) if v not in (None, "", "-") else "-"

# ---- 状況別打率 ----
SIT_CODES = [
    ("h",    "ホーム(本拠地)", "自分のチームの球場での成績"),
    ("a",    "ビジター(遠征)", "相手チームの球場での成績"),
    ("vl",   "対左投手", "左投げの投手と対戦した時の成績"),
    ("vr",   "対右投手", "右投げの投手と対戦した時の成績"),
    ("risp", "得点圏", "ランナーが2塁か3塁にいる場面。チャンスに強いかが分かる"),
    ("r123", "満塁", "ランナーが1・2・3塁すべてにいる場面。一番のチャンス"),
    ("lc",   "終盤の接戦", "試合終盤で点差が少ない、緊迫した場面"),
]
sit_rows = []
try:
    codes_param = ",".join(c for c, _, _ in SIT_CODES)
    d = get_json(f"https://statsapi.mlb.com/api/v1/people/{OHTANI}/stats?stats=statSplits&sitCodes={codes_param}&group=hitting&season={SEISEKI_SEASON}")
    by_code = {}
    for s in (d["stats"][0]["splits"] if d["stats"] else []):
        by_code[s.get("split", {}).get("code")] = s["stat"]
    for code, label, desc in SIT_CODES:
        st = by_code.get(code)
        if not st:
            continue
        sit_rows.append(
            f"<tr><td><b>{label}</b><br><span class='note'>{desc}</span></td>"
            f"<td>{_sd(st,'avg')}</td><td>{_sd(st,'atBats')}</td>"
            f"<td>{_sd(st,'homeRuns')}</td><td>{_sd(st,'rbi')}</td></tr>"
        )
except Exception:
    pass
sit_html = "\n".join(sit_rows) if sit_rows else "<tr><td colspan=5>状況別データを取得できませんでした</td></tr>"

# ---- 月別成績 ----
MONTH_NAMES = {2:"2月",3:"3月",4:"4月",5:"5月",6:"6月",7:"7月",8:"8月",9:"9月",10:"10月",11:"11月"}
month_rows = []
try:
    d = get_json(f"https://statsapi.mlb.com/api/v1/people/{OHTANI}/stats?stats=byMonth&group=hitting&season={SEISEKI_SEASON}")
    splits = d["stats"][0]["splits"] if d["stats"] else []
    splits.sort(key=lambda s: s.get("month", 0))
    for s in splits:
        st = s["stat"]
        m = MONTH_NAMES.get(s.get("month"), str(s.get("month")))
        month_rows.append(f"<tr><td><b>{m}</b></td><td>{_sd(st,'avg')}</td><td>{_sd(st,'homeRuns')}</td><td>{_sd(st,'rbi')}</td><td>{_sd(st,'ops')}</td></tr>")
except Exception:
    pass
month_html = "\n".join(month_rows) if month_rows else "<tr><td colspan=5>月別データを取得できませんでした</td></tr>"

# ---- 直近10試合ログ(打撃) ----
gamelog_rows = []
try:
    d = get_json(f"https://statsapi.mlb.com/api/v1/people/{OHTANI}/stats?stats=gameLog&group=hitting&season={SEISEKI_SEASON}")
    splits = d["stats"][0]["splits"] if d["stats"] else []
    for s in splits[-10:][::-1]:
        st = s["stat"]
        t = datetime.fromisoformat(s["date"])
        opp = s.get("opponent", {}).get("name", "")
        summary = st.get("summary", "")
        gamelog_rows.append(f"<tr><td>{t.month}/{t.day}</td><td>{opp}</td><td>{summary}</td></tr>")
except Exception:
    pass
gamelog_html = "\n".join(gamelog_rows) if gamelog_rows else "<tr><td colspan=3>試合ログを取得できませんでした</td></tr>"

# ---- 投手成績(登板があれば) ----
pitch_card_html = ""
pitch_rows = []
try:
    d = get_json(f"https://statsapi.mlb.com/api/v1/people/{OHTANI}/stats?stats=season&group=pitching&season={SEISEKI_SEASON}")
    psplits = d["stats"][0]["splits"] if d["stats"] else []
    if psplits:
        pst = psplits[0]["stat"]
        era, wl = _sd(pst, "era"), f"{_sd(pst,'wins')}勝{_sd(pst,'losses')}敗"
        so, whip = _sd(pst, "strikeOuts"), _sd(pst, "whip")
        ip, starts = _sd(pst, "inningsPitched"), _sd(pst, "gamesStarted")

        try:
            dg = get_json(f"https://statsapi.mlb.com/api/v1/people/{OHTANI}/stats?stats=gameLog&group=pitching&season={SEISEKI_SEASON}")
            gsplits = dg["stats"][0]["splits"] if dg["stats"] else []
            for s in gsplits[-5:][::-1]:
                st2 = s["stat"]
                t = datetime.fromisoformat(s["date"])
                opp = s.get("opponent", {}).get("name", "")
                summary = st2.get("summary", "")
                pitch_rows.append(f"<tr><td>{t.month}/{t.day}</td><td>{opp}</td><td>{summary}</td></tr>")
        except Exception:
            pass
        pitch_log_html = "\n".join(pitch_rows) if pitch_rows else "<tr><td colspan=3>登板ログを取得できませんでした</td></tr>"

        pitch_card_html = f"""
  <div class="card">
    <div class="label">投手成績(今シーズン{starts}登板)</div>
    <div class="stats">
      <div>防御率<b>{era}</b></div>
      <div>勝敗<b>{wl}</b></div>
      <div>奪三振<b>{so}</b></div>
    </div>
    <div class="mininote">投球回 {ip} / WHIP {whip}(1イニングあたりの走者数、低いほど良い)</div>
    <div class="note tblnote">防御率(ERA)=9イニングあたりの平均失点。数字が低いほど好投しているということです</div>
    <table class="mt">
      <tr><th>日付</th><th>対戦相手</th><th>結果</th></tr>
      {pitch_log_html}
    </table>
    <div class="note tblnote">直近の登板結果です。IP=投球回、ER=自責点、K=奪三振、BB=四球</div>
  </div>"""
except Exception:
    pitch_card_html = ""

season_avg2, season_hr2, season_rbi2 = hit.get("avg", "-"), hit.get("homeRuns", "-"), hit.get("rbi", "-")
season_ops2, season_sb2 = hit.get("ops", "-"), hit.get("stolenBases", "-")
seiseki_updated = datetime.now(JST).strftime("%Y年%m月%d日 %H:%M")

zenseiseki_cards = f"""
  <h2 class="sec" id="zenseiseki">📊 大谷さんの全成績</h2>
  <div class="date">{seiseki_updated} 時点(MLB公式StatsAPIより取得)</div>

  <div class="card">
    <div class="label">今シーズンの基本成績</div>
    <div class="stats" style="flex-wrap:wrap">
      <div>打率<b>{season_avg2}</b></div>
      <div>本塁打<b>{season_hr2}本</b></div>
      <div>打点<b>{season_rbi2}</b></div>
      <div>OPS<b>{season_ops2}</b></div>
      <div>盗塁<b>{season_sb2}</b></div>
    </div>
    <div class="note tblnote">OPS=出塁率+長打率。打者の総合力を表す指標で、.900あれば一流の目安です</div>
  </div>

  <div class="card">
    <div class="label">状況別の打率</div>
    <table>
      <tr><th>場面</th><th>打率</th><th>打数</th><th>本塁打</th><th>打点</th></tr>
      {sit_html}
    </table>
  </div>

  <div class="card">
    <div class="label">月別成績</div>
    <table>
      <tr><th>月</th><th>打率</th><th>本塁打</th><th>打点</th><th>OPS</th></tr>
      {month_html}
    </table>
    <div class="note tblnote">月ごとの成績です。調子の波や好不調が分かります</div>
  </div>

  <div class="card">
    <div class="label">直近10試合の結果</div>
    <table>
      <tr><th>日付</th><th>対戦相手</th><th>結果</th></tr>
      {gamelog_html}
    </table>
    <div class="note tblnote">最新の試合が一番上です。数字は「打数-安打」、Kは三振</div>
  </div>{pitch_card_html}
"""

# 全成績カードをトップページに差し込んで書き出す
html = html.replace("<!--ZENSEISEKI-->", zenseiseki_cards)
open("index.html", "w", encoding="utf-8").write(html)

# 旧URL(seiseki.html)へのブックマーク対策: トップの全成績セクションへ転送
open("seiseki.html", "w", encoding="utf-8").write(
    '<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">'
    '<meta http-equiv="refresh" content="0; url=index.html#zenseiseki">'
    '<title>移動しました</title></head><body>'
    '<p style="font-family:sans-serif;font-size:20px;text-align:center;margin-top:40px">'
    '全成績はトップページに引っ越しました。<a href="index.html#zenseiseki">こちらへどうぞ</a></p>'
    "</body></html>"
)
print(f"index.html 出力OK(全成績統合: 状況別{len(sit_rows)}件 / 月別{len(month_rows)}件 / 試合ログ{len(gamelog_rows)}件 / 投手成績{'あり(' + str(len(pitch_rows)) + '登板)' if pitch_card_html else 'なし'} / 動画{len(vids[:12])}本 / X埋め込み{x_embed_count}件)")

print(f"生成OK: {gdate} {headline} / 予定{len(week_rows)}試合 / 他選手{len(others_rows)}人 / ニュース{'OK' if 'news' in news_html else '取得済'}")
