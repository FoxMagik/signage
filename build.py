import urllib.request
import re
from datetime import datetime, date

ICS_URL = "https://www.ascensionschools.org/fs/calendar-manager/events.ics?feed_id=c20467f1-be50-44e0-be8b-9ab7b494654c"

def parse_ics_date(val):
    clean = re.sub(r'[^0-9T]', '', val)
    if 'T' in clean:
        return datetime.strptime(clean[:15], "%Y%m%dT%H%M%S").date()
    return datetime.strptime(clean[:8], "%Y%m%d").date()

def fetch_events():
    req = urllib.request.Request(ICS_URL, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode('utf-8', errors='ignore')

    # Unfold lines
    raw = re.sub(r'\r\n[ \t]', '', raw)
    lines = raw.splitlines()

    events = []
    current = {}
    for line in lines:
        if line.startswith("BEGIN:VEVENT"):
            current = {}
        elif line.startswith("END:VEVENT"):
            if "DTSTART" in current and "SUMMARY" in current:
                try:
                    d = parse_ics_date(current["DTSTART"])
                    events.append({
                        "date": d,
                        "title": current["SUMMARY"],
                        "desc": current.get("DESCRIPTION", "")
                    })
                except Exception:
                    pass
            current = {}
        elif ":" in line:
            parts = line.split(":", 1)
            key = parts[0].split(";")[0].strip()
            val = parts[1].replace("\\,", ",").replace("\\n", " ").strip()
            current[key] = val

    today = date.today()
    upcoming = [e for e in events if e["date"] >= today]
    upcoming.sort(key=lambda x: x["date"])
    return upcoming[:6]

def main():
    events = fetch_events()
    cards = []
    for ev in events:
        formatted_date = ev["date"].strftime("%a, %b %d")
        desc = (ev["desc"][:120] + "...") if len(ev["desc"]) > 120 else ev["desc"]
        card = f"""
        <div class="event-card">
          <div class="meta">{formatted_date}</div>
          <h2>{ev['title']}</h2>
          {'<div class="desc">' + desc + '</div>' if desc else ''}
        </div>
        """
        cards.append(card)

    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    now_str = datetime.now().strftime("%b %d, %I:%M %p")
    html = html.replace("BUILD_TIMESTAMP", f"Last updated: {now_str}")
    html = html.replace("<!-- EVENTS_PLACEHOLDER -->", "\n".join(cards) if cards else "<p>No upcoming events.</p>")

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    main()
