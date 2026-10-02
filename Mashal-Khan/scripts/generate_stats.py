"""Generates live GitHub stat cards (SVG) + 'Latest Updates' table for the profile README.
All numbers come from the GitHub API at run time. Nothing is hard-coded or dummy."""
import os, re, html, pathlib, datetime as dt
import requests

USER = os.environ.get("GH_USER", "mashal21442")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
HDR = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
OUT = pathlib.Path(os.environ.get("OUT_DIR", "dist")); OUT.mkdir(exist_ok=True)

# Teal / cyan theme (deliberately different from the reference profile)
BG, BORDER, TXT, MUTED = "#0B1215", "#16343A", "#E6FFFB", "#7FA9A6"
A1, A2 = "#14B8A6", "#22D3EE"

QUERY = """
query($login:String!){ user(login:$login){
  name bio createdAt
  followers{totalCount} following{totalCount}
  pullRequests{totalCount} issues{totalCount}
  repositories(ownerAffiliations:OWNER,isFork:false,first:100,privacy:PUBLIC){
    totalCount
    nodes{ name stargazerCount forkCount pushedAt
      languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}} } }
  contributionsCollection{
    totalCommitContributions restrictedContributionsCount
    contributionCalendar{ totalContributions weeks{contributionDays{date contributionCount}} } }
}}"""

def fetch():
    r = requests.post("https://api.github.com/graphql", headers=HDR,
                      json={"query": QUERY, "variables": {"login": USER}}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "errors" in data: raise SystemExit(data["errors"])
    return data["data"]["user"]

def card(w, h, title, body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Segoe UI,Ubuntu,sans-serif">
<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="{A1}"/><stop offset="1" stop-color="{A2}"/></linearGradient></defs>
<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="12" fill="{BG}" stroke="{BORDER}"/>
<text x="24" y="36" font-size="17" font-weight="700" fill="url(#g)">{html.escape(title)}</text>{body}</svg>'''

def row(y, label, value):
    return (f'<text x="24" y="{y}" font-size="13" fill="{MUTED}">{html.escape(label)}</text>'
            f'<text x="290" y="{y}" font-size="14" font-weight="700" fill="{TXT}" text-anchor="end">{html.escape(str(value))}</text>')

def streaks(days):
    counts = [d["contributionCount"] for d in days]
    longest = cur_run = 0
    for c in counts:
        cur_run = cur_run + 1 if c else 0
        longest = max(longest, cur_run)
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0: i -= 1          # today may not be done yet
    cur = 0
    while i >= 0 and counts[i]: cur += 1; i -= 1
    return cur, longest

def main():
    u = fetch()
    repos = u["repositories"]["nodes"]
    cc = u["contributionsCollection"]; cal = cc["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    today = dt.date.today().isoformat()
    days = [d for d in days if d["date"] <= today]
    cur, longest = streaks(days)
    stars = sum(r["stargazerCount"] for r in repos)
    commits = cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
    updated = dt.datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")

    # 1) stats
    body = "".join(row(66 + i * 24, k, v) for i, (k, v) in enumerate([
        ("Public repositories", u["repositories"]["totalCount"]), ("Stars earned", stars),
        ("Commits (last year)", commits), ("Pull requests", u["pullRequests"]["totalCount"]),
        ("Issues", u["issues"]["totalCount"]), ("Followers", u["followers"]["totalCount"])]))
    body += f'<text x="24" y="228" font-size="10" fill="{MUTED}">updated {updated}</text>'
    (OUT / "stats.svg").write_text(card(320, 245, "GitHub Stats", body))

    # 2) streak
    body = (f'<text x="60" y="95" font-size="34" font-weight="800" fill="{TXT}" text-anchor="middle">{cur}</text>'
            f'<text x="60" y="118" font-size="12" fill="{MUTED}" text-anchor="middle">current streak</text>'
            f'<text x="160" y="95" font-size="34" font-weight="800" fill="{TXT}" text-anchor="middle">{cal["totalContributions"]}</text>'
            f'<text x="160" y="118" font-size="12" fill="{MUTED}" text-anchor="middle">contributions / yr</text>'
            f'<text x="260" y="95" font-size="34" font-weight="800" fill="{TXT}" text-anchor="middle">{longest}</text>'
            f'<text x="260" y="118" font-size="12" fill="{MUTED}" text-anchor="middle">longest streak</text>'
            f'<text x="24" y="150" font-size="10" fill="{MUTED}">updated {updated}</text>')
    (OUT / "streak.svg").write_text(card(320, 165, "Contribution Streak", body))

    # 3) top languages
    tot = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]; t = tot.setdefault(n["name"], [0, n["color"] or A1]); t[0] += e["size"]
    top = sorted(tot.items(), key=lambda kv: -kv[1][0])[:6]; s = sum(v[0] for _, v in top) or 1
    body = ""
    for i, (name, (size, color)) in enumerate(top):
        y = 62 + i * 28; pct = size / s * 100
        body += (f'<text x="24" y="{y}" font-size="12" fill="{TXT}">{html.escape(name)}</text>'
                 f'<text x="296" y="{y}" font-size="12" fill="{MUTED}" text-anchor="end">{pct:.1f}%</text>'
                 f'<rect x="24" y="{y+6}" width="272" height="6" rx="3" fill="{BORDER}"/>'
                 f'<rect x="24" y="{y+6}" width="{272*pct/100:.1f}" height="6" rx="3" fill="{color}"/>')
    if not top: body = f'<text x="24" y="70" font-size="13" fill="{MUTED}">Push some code to see languages here.</text>'
    (OUT / "top-langs.svg").write_text(card(320, 62 + max(len(top), 1) * 28 + 20, "Top Languages", body))

    # 4) activity graph (last 30 days)
    last = days[-30:]; w, h, px, py = 700, 220, 40, 50
    mx = max([d["contributionCount"] for d in last] + [1])
    pts = [(px + i * (w - 2 * px) / max(len(last) - 1, 1), h - 35 - d["contributionCount"] / mx * (h - py - 45)) for i, d in enumerate(last)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{px},{h-35} {line} {pts[-1][0]:.1f},{h-35}" if pts else ""
    body = (f'<defs><linearGradient id="a" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{A1}" stop-opacity=".45"/>'
            f'<stop offset="1" stop-color="{A1}" stop-opacity="0"/></linearGradient></defs>'
            f'<polygon points="{area}" fill="url(#a)"/><polyline points="{line}" fill="none" stroke="{A2}" stroke-width="2.5" stroke-linejoin="round"/>'
            + "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{A2}"/>' for x, y in pts)
            + f'<text x="{px}" y="{h-12}" font-size="11" fill="{MUTED}">{last[0]["date"] if last else ""}</text>'
            f'<text x="{w-px}" y="{h-12}" font-size="11" fill="{MUTED}" text-anchor="end">{last[-1]["date"] if last else ""}</text>'
            f'<text x="{w-px}" y="36" font-size="11" fill="{MUTED}" text-anchor="end">peak: {mx}/day</text>')
    (OUT / "activity-graph.svg").write_text(card(w, h, "Contributions · last 30 days", body))

    # 5) about card
    since = u["createdAt"][:4]
    body = "".join(row(66 + i * 26, k, v) for i, (k, v) in enumerate([
        ("GitHub", f"@{USER}"), ("Member since", since), ("Followers / Following", f'{u["followers"]["totalCount"]} / {u["following"]["totalCount"]}'),
        ("Most used language", top[0][0] if top else "-")]))
    body += f'<text x="24" y="185" font-size="10" fill="{MUTED}">auto-updated {updated}</text>'
    (OUT / "about-card.svg").write_text(card(320, 200, f'About {u["name"] or USER}', body))

    # 6) latest updates table -> README markers
    rows = []
    for r in sorted(repos, key=lambda r: r["pushedAt"], reverse=True)[:5]:
        c = requests.get(f"https://api.github.com/repos/{USER}/{r['name']}/commits?per_page=1", headers=HDR, timeout=30)
        if c.status_code != 200 or not c.json(): continue
        c = c.json()[0]; msg = c["commit"]["message"].splitlines()[0][:70].replace("|", "\\|")
        date = dt.datetime.strptime(c["commit"]["author"]["date"], "%Y-%m-%dT%H:%M:%SZ").strftime("%d %b %Y")
        lang = (r["languages"]["edges"][0]["node"]["name"] if r["languages"]["edges"] else "-")
        rows.append(f"| 📁 **[{r['name']}](https://github.com/{USER}/{r['name']})** | {lang} | [{msg}]({c['html_url']}) | {date} |")
    table = "| Project | Language | Latest change | Date |\n|---|---|---|---|\n" + "\n".join(rows)
    p = pathlib.Path("README.md"); txt = p.read_text(encoding="utf-8")
    new = re.sub(r"(<!--LATEST-START-->).*?(<!--LATEST-END-->)", lambda m: f"{m.group(1)}\n{table}\n{m.group(2)}", txt, flags=re.S)
    if new != txt: p.write_text(new, encoding="utf-8")
    print("done:", ", ".join(f.name for f in OUT.iterdir()))

if __name__ == "__main__":
    main()
