import urllib.request
import re
from datetime import datetime, date
import html

ICS_URL = "https://www.ascensionschools.org/fs/calendar-manager/events.ics?feed_id=c20467f1-be50-44e0-be8b-9ab7b494654c"

def parse_ics_date(val):
    clean = re.sub(r'[^0-9T]', '', val)
    if 'T' in clean:
        return datetime.strptime(clean[:15], "%Y%m%dT%H%M%S").date()
    return datetime.strptime(clean[:8], "%Y%m%d").date()

def format_menu_description(raw_desc):
    if not raw_desc:
        return ""

    # Unescape HTML entities (&amp;, &nbsp;, etc.)
    text = html.unescape(raw_desc)
    
    # 1. Convert any HTML breaks or iCal escaped line breaks to a standard delimiter
    text = re.sub(r'<br\s*/?>|</p>|\\n|\n|\r', '###SPLIT###', text, flags=re.IGNORECASE)
    
    # 2. Insert delimiter before key prefixes like "Sandwich:" or "Breakfast:"
    text = re.sub(r'(?i)(sandwich\s*:|breakfast\s*:)', r'###SPLIT###\1', text)
    
    # 3. Insert delimiter between CamelCase boundaries where items collided (e.g. CornTossed -> Corn | Tossed)
    # Checks for lowercase letter followed directly by an uppercase letter
    text = re.sub(r'([a-z])([A-Z])', r'\1###SPLIT###\2', text)

    # 4. Strip out any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Split into clean, individual lines
    raw_lines = text.split('###SPLIT###')
    lines = [l.strip() for l in raw_lines if l.strip()]

    formatted_items = []
    for line in lines:
        lower = line.lower()
        if lower.startswith("breakfast:") or lower.startswith("sandwich:"):
            parts = line.split(":", 1)
            formatted_items.append(
                f'<li class="special-item"><strong>{parts[0].strip()}:</strong> {parts[1].strip()}</li>'
            )
        else:
            formatted_items.append(f'<li>{line}</li>')

    return f'<ul class="menu-items">{"".join(formatted_items)}</ul>'

def fetch_events():
    req = urllib.request.Request(ICS_URL, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode('utf-8', errors='ignore')

    # Unfold wrapped lines in iCal standard
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
            val = parts[1].replace("\\,", ",").strip()
            current[key] = val

    today = date.today()
    upcoming = [e for e in events if e["date"] >= today]
    upcoming.sort(key=lambda x: x["date"])

    # --- DEBUG PRINT ---
    print("\n" + "="*50)
    print("DEBUG: RAW EVENT DESCRIPTIONS FOUND:")
    for ev in upcoming[:3]:
        print(f"\n--- Event: {ev['title']} ({ev['date']}) ---")
        print(f"RAW REPR: {repr(ev['desc'])}")
    print("="*50 + "\n")
    # -------------------

    return upcoming[:6]

def main():
    events = fetch_events()
    cards = []
    for ev in events:
        formatted_date = ev["date"].strftime("%a, %b %d")
        menu_html = format_menu_description(ev["desc"])
        
        card = f"""
        <div class="event-card">
          <div class="meta">{formatted_date}</div>
          <h2>{ev['title']}</h2>
          {menu_html}
        </div>
        """
        cards.append(card)

    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    now_str = datetime.now().strftime("%b %d, %I:%M %p")
    html_content = html_content.replace("BUILD_TIMESTAMP", f"Last updated: {now_str}")
    html_content = html_content.replace("<!-- EVENTS_PLACEHOLDER -->", "\n".join(cards) if cards else "<p>No upcoming events.</p>")

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    main()
