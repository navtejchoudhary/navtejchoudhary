"""Draws black-and-white GitHub stat cards for the profile README.

Runs inside GitHub Actions (see .github/workflows/profile.yml).
Uses only the Python standard library and the built-in GITHUB_TOKEN,
so there is no outside server that can go down or get rate-limited.

Outputs (written to ./dist):
  stats.svg      - headline numbers
  languages.svg  - top languages by code size
  activity.svg   - daily contributions for the last 60 days
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
BG, LINE, DIM, MID, FG = "#000000", "#2e2e2e", "#6e6e6e", "#a3a3a3", "#ffffff"

QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""


def fetch(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GitHub API error: {data['errors']}")
    return data["data"]["user"]


def shape(user):
    repos = user["repositories"]["nodes"]
    langs = {}
    for repo in repos:
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    cc = user["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    return {
        "stats": [
            ("Contributions · last year", cc["contributionCalendar"]["totalContributions"]),
            ("Commits", cc["totalCommitContributions"]),
            ("Pull requests", cc["totalPullRequestContributions"]),
            ("Public repos", user["repositories"]["totalCount"]),
            ("Stars earned", sum(r["stargazerCount"] for r in repos)),
            ("Followers", user["followers"]["totalCount"]),
        ],
        "langs": sorted(langs.items(), key=lambda kv: -kv[1])[:6],
        "days": [(d["date"], d["contributionCount"]) for d in days][-60:],
    }


def frame(w, h, title, inner):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="10" fill="{BG}" stroke="{LINE}"/>'
        f'<text x="24" y="36" fill="{FG}" font-family="{MONO}" font-size="14" font-weight="700" '
        f'letter-spacing="1">{escape(title)}</text>{inner}</svg>'
    )


def stats_svg(stats):
    w, h, rows = 420, 230, []
    for i, (label, value) in enumerate(stats):
        y = 72 + i * 26
        rows.append(
            f'<text x="24" y="{y}" fill="{MID}" font-family="{FONT}" font-size="13.5">{escape(label)}</text>'
            f'<text x="{w-24}" y="{y}" fill="{FG}" font-family="{MONO}" font-size="14" '
            f'font-weight="700" text-anchor="end">{value:,}</text>'
        )
    return frame(w, h, "> navtej.stats()", "".join(rows))


def langs_svg(langs):
    w, h = 420, 230
    total = sum(s for _, s in langs) or 1
    shades = [FG, "#d4d4d4", MID, "#858585", DIM, "#4d4d4d"]
    x, bar, rows = 24, [], []
    for i, (name, size) in enumerate(langs):
        bw = (w - 48) * size / total
        bar.append(f'<rect x="{x:.1f}" y="56" width="{bw:.1f}" height="8" fill="{shades[i]}"/>')
        x += bw
        col, row = i % 2, i // 2
        cx, cy = 24 + col * 196, 98 + row * 30
        rows.append(
            f'<circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{shades[i]}"/>'
            f'<text x="{cx+18}" y="{cy}" fill="{MID}" font-family="{FONT}" font-size="13.5">{escape(name)}</text>'
            f'<text x="{cx+176}" y="{cy}" fill="{FG}" font-family="{MONO}" font-size="13" '
            f'text-anchor="end">{100*size/total:.1f}%</text>'
        )
    if not langs:
        rows.append(f'<text x="24" y="100" fill="{DIM}" font-family="{FONT}" font-size="13">No code pushed yet.</text>')
    clip = f'<clipPath id="c"><rect x="24" y="56" width="{w-48}" height="8" rx="4"/></clipPath>'
    return frame(w, h, "> top_languages", clip + f'<g clip-path="url(#c)">{"".join(bar)}</g>' + "".join(rows))


def activity_svg(days):
    w, h = 860, 260
    left, right, top, bottom = 48, 24, 60, 210
    peak = max([c for _, c in days] + [1])
    n = max(len(days) - 1, 1)
    px = lambda i: left + (w - left - right) * i / n
    py = lambda c: bottom - (bottom - top) * c / peak
    pts = [(px(i), py(c)) for i, (_, c) in enumerate(days)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{left},{bottom} {line} {px(n):.1f},{bottom}"
    grid = "".join(
        f'<line x1="{left}" x2="{w-right}" y1="{py(peak*k/4):.1f}" y2="{py(peak*k/4):.1f}" stroke="{LINE}"/>'
        f'<text x="{left-10}" y="{py(peak*k/4)+4:.1f}" fill="{DIM}" font-family="{MONO}" font-size="11" '
        f'text-anchor="end">{round(peak*k/4)}</text>'
        for k in range(5)
    )
    labels = "".join(
        f'<text x="{px(i):.1f}" y="{bottom+22}" fill="{DIM}" font-family="{MONO}" font-size="11" '
        f'text-anchor="middle">{dt.date.fromisoformat(days[i][0]).strftime("%d %b")}</text>'
        for i in range(0, len(days), 10)
    )
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="{FG}"/>' for x, y in pts)
    inner = (
        f'<defs><linearGradient id="a" x1="0" x2="0" y1="0" y2="1">'
        f'<stop offset="0" stop-color="{FG}" stop-opacity=".25"/><stop offset="1" stop-color="{FG}" stop-opacity="0"/>'
        f"</linearGradient></defs>{grid}"
        f'<polygon points="{area}" fill="url(#a)"/>'
        f'<polyline points="{line}" fill="none" stroke="{FG}" stroke-width="2" stroke-linejoin="round"/>'
        f"{dots}{labels}"
    )
    return frame(w, h, "> contributions · last 60 days", inner)


def write(data, out="dist"):
    os.makedirs(out, exist_ok=True)
    files = {
        "stats.svg": stats_svg(data["stats"]),
        "languages.svg": langs_svg(data["langs"]),
        "activity.svg": activity_svg(data["days"]),
    }
    for name, svg in files.items():
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", name)


if __name__ == "__main__":
    login = os.environ.get("GH_USER") or sys.argv[1]
    write(shape(fetch(login, os.environ["GITHUB_TOKEN"])))
