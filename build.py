#!/usr/bin/env python3
"""Family Hub builder.

Pulls ICS calendar feeds, expands recurring events, tags them (practice, game,
working late, special event...), attaches packing lists, and writes a static
site to ./site (index.html with the data embedded, plus data.json).

Usage:
    python build.py                 # uses config.yml
    python build.py demo/config.yml # any other config
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events
import yaml

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site"


# ---------------------------------------------------------------- config ---
def load_config(path: Path) -> dict:
    """Read YAML config, substituting ${NAME} from env vars / GitHub secrets."""
    secrets: dict = {}
    if os.environ.get("CAL_SECRETS"):
        try:
            secrets = json.loads(os.environ["CAL_SECRETS"])
        except json.JSONDecodeError:
            pass

    def sub(m: re.Match) -> str:
        key = m.group(1)
        val = os.environ.get(key) or secrets.get(key)
        if not val:
            print(f"warning: ${{{key}}} is not set; that calendar will be skipped", file=sys.stderr)
            return ""
        return val

    text = re.sub(r"\$\{([A-Za-z0-9_]+)\}", sub, path.read_text())
    return yaml.safe_load(text)


# ----------------------------------------------------------------- utils ---
def compile_patterns(words):
    """Whole-word, case-insensitive match; allows plurals ('game' matches 'games')."""
    pats = []
    for w in words or []:
        pats.append(re.compile(r"(?<!\w)" + re.escape(str(w).lower()) + r"(?:s|es)?(?!\w)"))
    return pats


def matches(text: str, pats) -> bool:
    t = text.lower()
    return any(p.search(t) for p in pats)


def fetch(url: str, base: Path) -> bytes:
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    if not re.match(r"https?://", url):
        return (base / url).read_bytes()  # local file (demo / testing)
    req = urllib.request.Request(url, headers={"User-Agent": "family-hub/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def to_local(value, tz: ZoneInfo) -> dt.datetime:
    if value.tzinfo is None:  # "floating" time: treat as family-local
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


def fmt_time(t: dt.datetime) -> str:
    return t.strftime("%-I:%M %p").replace(":00 ", " ")


def time_label(s: dt.datetime, e: dt.datetime) -> str:
    a, b = fmt_time(s), fmt_time(e)
    if a[-2:] == b[-2:]:  # same AM/PM: "4:30 – 6 PM"
        a = a[:-3]
    return f"{a} – {b}"


DESC_PACK = re.compile(r"^\s*(?:pack|bring)\s*:\s*(.+)$", re.I | re.M)
DESC_TAG = re.compile(r"#([a-z0-9_-]+)", re.I)


# ----------------------------------------------------------------- build ---
def build(config_path: Path) -> dict:
    cfg = load_config(config_path)
    base = config_path.parent
    tz = ZoneInfo(cfg.get("timezone", "America/Detroit"))
    now = dt.datetime.now(tz)
    win_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    win_end = win_start + dt.timedelta(days=int(cfg.get("days_ahead", 60)))

    categories = cfg.get("categories", {}) or {}
    cat_pats = {k: compile_patterns(v.get("match")) for k, v in categories.items()}
    pack_rules = [(compile_patterns(r.get("match")), r.get("items", [])) for r in cfg.get("packing", []) or []]

    people: dict[str, str] = {}
    events: dict[tuple, dict] = {}
    problems: list[str] = []

    for cal_cfg in cfg.get("calendars", []):
        name = cal_cfg["name"]
        person = cal_cfg.get("person", name)
        color = cal_cfg.get("color", "#868e96")
        people.setdefault(person, color)
        only = set(cal_cfg.get("only", []) or [])
        url = (cal_cfg.get("url") or "").strip()
        if not url:
            continue
        try:
            cal = icalendar.Calendar.from_ical(fetch(url, base))
        except Exception as exc:  # one bad feed shouldn't kill the page
            problems.append(f"{name}: {exc.__class__.__name__}")
            print(f"error: could not load {name}: {exc}", file=sys.stderr)
            continue

        for comp in recurring_ical_events.of(cal).between(win_start, win_end):
            if comp.name != "VEVENT":
                continue
            if str(comp.get("STATUS", "")).upper() == "CANCELLED":
                continue
            title = str(comp.get("SUMMARY", "(No title)")).strip()
            desc = str(comp.get("DESCRIPTION", "") or "")
            loc = str(comp.get("LOCATION", "") or "").strip()

            ds = comp.get("DTSTART").dt
            de = comp.get("DTEND").dt if comp.get("DTEND") else None
            all_day = not isinstance(ds, dt.datetime)

            if all_day:
                e = de if isinstance(de, dt.date) and not isinstance(de, dt.datetime) else ds + dt.timedelta(days=1)
                if e <= ds:
                    e = ds + dt.timedelta(days=1)
                days = [(ds + dt.timedelta(days=i)).isoformat() for i in range((e - ds).days)]
                start_iso, end_iso, label = ds.isoformat(), e.isoformat(), "All day"
            else:
                s = to_local(ds, tz)
                if isinstance(de, dt.datetime):
                    e = to_local(de, tz)
                elif comp.get("DURATION"):
                    e = s + comp.get("DURATION").dt
                else:
                    e = s + dt.timedelta(hours=1)
                days, d = [], s.date()
                last = (e - dt.timedelta(seconds=1)).date() if e > s else s.date()
                while d <= last:
                    days.append(d.isoformat())
                    d += dt.timedelta(days=1)
                start_iso, end_iso, label = s.isoformat(), e.isoformat(), time_label(s, e)
            short = "All day" if all_day else fmt_time(s)

            # --- tag it
            tags = {t.lower() for t in DESC_TAG.findall(desc)}
            cats = [k for k, pats in cat_pats.items() if matches(title, pats) or k in tags]
            if only and not (only & set(cats)):
                continue  # e.g. a work calendar where we only want "working late"

            # --- packing list: rules + "Pack: a, b" lines in the description
            pack: list[str] = []
            hay = f"{title} {loc}"
            for pats, items in pack_rules:
                if matches(hay, pats):
                    pack += items
            for line in DESC_PACK.findall(desc):
                pack += [x.strip() for x in re.split(r"[,;]", line) if x.strip()]
            pack = list(dict.fromkeys(pack))  # dedupe, keep order

            uid = str(comp.get("UID", title))
            key = (uid, start_iso)
            if key in events:  # same event on two calendars (e.g. shared family event)
                if person not in events[key]["who"]:
                    events[key]["who"].append(person)
                continue
            events[key] = {
                "id": re.sub(r"[^A-Za-z0-9]", "", f"{uid}{start_iso}")[-48:],
                "title": title,
                "start": start_iso,
                "end": end_iso,
                "allDay": all_day,
                "days": days,
                "time": label,
                "short": short,
                "who": [person],
                "location": loc if cfg.get("show_locations", True) else "",
                "cats": cats,
                "pack": pack,
            }

    ordered = sorted(events.values(), key=lambda ev: (ev["days"][0], not ev["allDay"], ev["start"]))
    return {
        "title": cfg.get("title", "Family Hub"),
        "timezone": str(tz),
        "generated": now.isoformat(timespec="seconds"),
        "people": people,
        "categories": {
            k: {
                "label": v.get("label", k.title()),
                "icon": v.get("icon", ""),
                "banner": bool(v.get("banner")),
                "countdown": bool(v.get("countdown")),
            }
            for k, v in categories.items()
        },
        "packLeadHours": int(cfg.get("pack_lead_hours", 36)),
        "countdownDays": int(cfg.get("countdown_days", 60)),
        "problems": problems,
        "events": ordered,
    }


def main() -> None:
    config_path = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "config.yml").resolve()
    data = build(config_path)
    OUT.mkdir(exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False)
    (OUT / "data.json").write_text(payload)
    page = (ROOT / "template.html").read_text().replace(
        "/*__DATA__*/null", payload.replace("</", "<\\/")
    )
    (OUT / "index.html").write_text(page)
    print(f"Built {len(data['events'])} events from {config_path.name} -> {OUT}/index.html")
    if data["problems"]:
        print("Problems:", "; ".join(data["problems"]), file=sys.stderr)


if __name__ == "__main__":
    main()
