#!/usr/bin/env python3
"""
Dodaje wpis do news.json (meetup, kurs, projekt, inne) — albo archiwizuje wpis po id.

Używane przez GitHub Action "Add entry" (Actions → Add entry → Run workflow),
działa też lokalnie:

  python3 scripts/add_entry.py --json '{"type": "meetup", "title": "...", ...}'
  python3 scripts/add_entry.py --archive 2026-058
  python3 scripts/add_entry.py --check          # tylko walidacja news.json

id nadawane automatycznie (ROK-NNN), "added" = dziś.
"""
import argparse, json, re, sys
from datetime import date
from pathlib import Path

NEWS = Path(__file__).parent.parent / "news.json"
TYPES = {"meetup", "course-dated", "course-free", "project", "other"}
DATE_FIELDS = ("date_start", "date_end", "deadline", "added")
FIELDS = ("type", "title", "org", "description", "url", "free", "lang", "location",
          "date_start", "date_end", "deadline")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load():
    return json.loads(NEWS.read_text(encoding="utf-8"))


def save(d):
    NEWS.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def problems(e):
    p = []
    if e.get("type") not in TYPES:
        p.append(f"type musi być jednym z: {', '.join(sorted(TYPES))}")
    if not (e.get("title") or "").strip():
        p.append("brak tytułu")
    if not (e.get("description") or "").strip():
        p.append("brak opisu")
    for k in DATE_FIELDS:
        if e.get(k) and not DAY.match(e[k]):
            p.append(f"{k} ma zły format (YYYY-MM-DD): {e[k]}")
    if e.get("date_start") and e.get("date_end") and e["date_end"] < e["date_start"]:
        p.append("date_end jest przed date_start")
    if e.get("url") and not re.match(r"^https?://\S+$", e["url"]):
        p.append(f"url musi zaczynać się od http(s)://: {e['url']}")
    if e.get("type") in ("meetup", "course-dated") and not (e.get("date_start") or e.get("date_end")):
        p.append("wydarzenie bez daty — nigdy nie trafi do archiwum samo (ustaw date_end)")
    return p


def next_id(entries):
    y = date.today().year
    nums = [int(m.group(1)) for e in entries if (m := re.match(rf"^{y}-(\d+)$", e.get("id", "")))]
    return f"{y}-{(max(nums) + 1 if nums else 1):03d}"


def clean(v):
    return re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--archive", help="id wpisu do przeniesienia do archiwum")
    ap.add_argument("--check", action="store_true", help="sprawdź cały news.json")
    a = ap.parse_args()
    d = load()
    entries = d["entries"]

    if a.check:
        bad = 0
        ids = [e.get("id") for e in entries]
        for dup in {i for i in ids if ids.count(i) > 1}:
            print(f"❌ zdublowane id: {dup}"); bad += 1
        for e in entries:
            for msg in problems(e):
                print(f"⚠ {e.get('id')} {e.get('title', '')[:50]!r}: {msg}"); bad += 1
        print("✅ news.json OK" if not bad else f"{bad} uwag")
        sys.exit(1 if any(ids.count(i) > 1 for i in ids) else 0)

    if a.archive:
        hit = [e for e in entries if e["id"] == a.archive]
        if not hit:
            sys.exit(f"❌ Nie ma wpisu o id {a.archive}")
        hit[0]["archived"] = True
        save(d)
        print(f"📦 Zarchiwizowano: {hit[0]['title']}")
        return

    raw = json.loads(a.json or "{}")
    e = {k: clean(raw[k]) for k in FIELDS if raw.get(k) not in (None, "", False)}
    if str(raw.get("free", "")).lower() in ("true", "on", "1", "tak"):
        e["free"] = True
    else:
        e.pop("free", None)
    errs = [m for m in problems(e) if not m.startswith("wydarzenie bez daty")]
    if errs:
        sys.exit("❌ " + "\n❌ ".join(errs))
    if e.get("date_end") and e["date_end"] < date.today().isoformat():
        sys.exit(f"❌ date_end {e['date_end']} już minął — nie dodaję")
    if any(x["title"].strip().lower() == e["title"].lower() and x.get("date_start") == e.get("date_start")
           for x in entries):
        sys.exit("ℹ Taki wpis już jest w news.json")

    entry = {"id": next_id(entries), **e, "archived": False, "added": date.today().isoformat()}
    entries.append(entry)
    save(d)
    print(f"✅ Dodano {entry['id']} [{entry['type']}] {entry['title']}")
    for m in problems(entry):
        print(f"⚠ {m}")


if __name__ == "__main__":
    main()
