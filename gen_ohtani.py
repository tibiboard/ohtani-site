# -*- coding: utf-8 -*-
"""「今日の大谷さん」v2 — シニア向けデカ文字1ページ(全部入り)
MLB公式スタッツAPI+Google News RSSから自動生成。毎日の定時実行で自動更新。
"""
import io, sys, json, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
JST = timezone(timedelta(hours=9))
OHTANI = 660271

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
        news_html += f'<a class="news" href="{link}" target="_blank">・{title}</a>\n'
except Exception as e:
    news_html = "<div>ニュースを取得できませんでした</div>"

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
        sd = get_json(f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=season&group={grp}")
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
  .date {{ text-align: center; color: #777; font-size: 18px; margin-bottom: 16px; }}
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
  .foot {{ text-align: center; color: #999; font-size: 15px; }}
</style></head><body><div class="wrap">
  <h1>⚾ 今日の大谷さん</h1>
  <div class="date">{updated} 更新</div>

  <div class="card">
    <div class="label">{gdate}の試合</div>
    <div class="big" style="color:{color}">{headline}</div>
    <div class="mid">{line}</div>
  </div>

  <div class="card">
    <div class="label">今シーズンの成績</div>
    <div class="stats">
      <div>ホームラン<b>{season_hr}本</b></div>
      <div>打率<b>{season_avg}</b></div>
      <div>打点<b>{season_rbi}</b></div>
    </div>
  </div>

  <div class="card">
    <div class="label">これからの試合(日本時間)</div>
    <table>{week_html}</table>
  </div>

  <div class="card">
    <div class="label">試合はどこで見られる?</div>
    <p style="font-size:18px; text-align:center; margin:6px 0 10px">
      ドジャースの試合は、だいたい<b>NHK BS</b>か<b>ネット配信</b>で見られます
    </p>
    <a class="btn" href="{nhk}" target="_blank">📺 NHKの番組表を確認する</a>
    <a class="btn" href="https://abema.tv/now-on-air/mlb" target="_blank">📱 ABEMAで見る(ネット)</a>
    <a class="btn" href="https://www.spotvnow.jp/" target="_blank">🖥 SPOTV NOWで見る(ネット)</a>
  </div>{genki_html}

  <div class="card">
    <div class="label">大谷さんのニュース</div>
    {news_html}
  </div>

  <div class="card">
    <div class="label">動画・話題</div>
    <a class="btn red" href="{yt}" target="_blank">▶ YouTubeでハイライトを見る</a>
    <a class="btn" href="{xs}" target="_blank">💬 Xでみんなの反応を見る</a>
  </div>

  <div class="card">
    <div class="label">日本人メジャーリーガーの成績</div>
    <table>{others_html}</table>
  </div>

  <div class="foot">非公式のファン情報ページです / 成績: MLB公式データより自動取得</div>
</div></body></html>"""

open("index.html", "w", encoding="utf-8").write(html)
print(f"生成OK: {gdate} {headline} / 予定{len(week_rows)}試合 / 他選手{len(others_rows)}人 / ニュース{'OK' if 'news' in news_html else '取得済'}")
