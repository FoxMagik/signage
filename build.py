import urllib.request
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, date

# --- OPTIONAL: Paste published Google Sheet CSV URLs here ---
# If left None, defaults to built-in feeds below
SHEET_FEEDS_CSV = https://docs.google.com/spreadsheets/d/e/2PACX-1vQUrHDlH1B7BQOYmItL2l_MUEpENhQsqcm_SbMf3PXzUUmwZOZS8DNxsw8TQEJVQmUkA7cSEHyGgdPr/pub?output=csv
# -------------------------------------------------------------

DEFAULT_FEEDS = [
    {
        "type": "menu",
        "title": "Cafeteria Lunch & Breakfast",
        "url": "https://www.ascensionschools.org/fs/calendar-manager/events.ics?feed_id=c20467f1-be50-44e0-be8b-9ab7b494654c",
        "duration": 25
    },
    {
        "type": "nasa",
        "title": "NASA Astronomy Picture of the Day",
        "url": "https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY",
        "duration": 20
    },
    {
        "type": "wotd",
        "title": "Merriam-Webster Word of the Day",
        "url": "https://www.merriam-webster.com/wotd/feed/rss2",
        "duration": 18
    }
]

def http_get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Signage Bot)'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode('utf-8', errors='ignore')

# ----------------- PARSERS -----------------

def parse_ics_menu_and_notices(url):
    raw = http_get(url)
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
                    clean_d = re.sub(r'[^0-9T]', '', current["DTSTART"])
                    dt = datetime.strptime(clean_d[:8], "%Y%m%d").date()
                    events.append({
                        "date": dt,
                        "title": current["SUMMARY"],
                        "desc": current.get("DESCRIPTION", "")
                    })
                except Exception:
                    pass
            current = {}
        elif ":" in line:
            parts = line.split(":", 1)
            key = parts[0].split(";")[0].strip()
            current[key] = parts[1].replace("\\,", ",").strip()

    today = date.today()
    upcoming = [e for e in events if e["date"] >= today]
    upcoming.sort(key=lambda x: x["date"])

    menu_cards = []
    holiday_cards = []

    for ev in upcoming[:8]:
        d_str = ev["date"].strftime("%a, %b %d")
        desc = ev["desc"]

        # Delimiter cleanup for collapsed district feeds
        is_menu = bool(desc) and any(k in desc.lower() for k in ["sandwich:", "breakfast:", "salad", "bun"])

        if is_menu:
            text = re.sub(r'(?i)\s*(sandwich\s*:|breakfast\s*:)', r'||\1', desc.strip())
            text = re.sub(r'([a-z])([A-Z])', r'\1||\2', text)
            items = [l.strip() for l in text.split('||') if l.strip()]

            lis = []
            for item in items:
                if item.lower().startswith(("breakfast:", "sandwich:")):
                    p = item.split(":", 1)
                    lis.append(f'<li class="special-item"><strong>{p[0].strip()}:</strong> {p[1].strip()}</li>')
                else:
                    lis.append(f'<li>{item}</li>')

            menu_cards.append(f"""
            <div class="card">
              <div class="meta">{d_str}</div>
              <h2>{ev['title']}</h2>
              <ul class="menu-items">{"".join(lis)}</ul>
            </div>
            """)
        else:
            notice_text = desc if desc else "School Holiday / District Closed"
            holiday_cards.append(f"""
            <div class="card notice">
              <div class="meta">{d_str}</div>
              <h2>{ev['title']}</h2>
              <p style="margin-top:0.5rem; color:#e2e8f0; font-size:1.1rem;">{notice_text}</p>
            </div>
            """)

    return menu_cards[:6], holiday_cards[:6]

def parse_nasa_apod(url):
    try:
        raw = http_get(url)
        data = json.loads(raw)
        img_url = data.get("url", "")
        # Only render if it's an image, not YouTube video
        if data.get("media_type") != "image":
            return ""

        title = data.get("title", "NASA Astronomy Picture of the Day")
        explanation = data.get("explanation", "")
        if len(explanation) > 350:
            explanation = explanation[:350] + "..."

        return f"""
        <div class="slide" data-title="NASA Discovery" data-duration="20">
          <div class="hero-layout">
            <img src="{img_url}" class="hero-img" alt="NASA APOD">
            <div class="hero-content">
              <span class="hero-tag">Astronomy Picture of the Day</span>
              <h2>{title}</h2>
              <p>{explanation}</p>
            </div>
          </div>
        </div>
        """
    except Exception as e:
        print(f"NASA Error: {e}")
        return ""

def parse_word_of_the_day(url):
    try:
        raw = http_get(url)
        root = ET.fromstring(raw)
        channel = root.find("channel")
        item = channel.find("item")

        word = item.find("title").text
        desc = item.find("description").text
        # Strip internal tags from dictionary feed
        clean_desc = re.sub(r'<[^>]+>', '', desc).strip()
        if len(clean_desc) > 350:
            clean_desc = clean_desc[:350] + "..."

        return f"""
        <div class="slide" data-title="Word of the Day" data-duration="18">
          <div class="hero-layout">
            <div class="hero-content">
              <span class="hero-tag">Merriam-Webster</span>
              <h2 style="font-size: 3.8rem; color: var(--accent);">{word}</h2>
              <p style="font-size: 1.4rem;">{clean_desc}</p>
            </div>
          </div>
        </div>
        """
    except Exception as e:
        print(f"WOTD Error: {e}")
        return ""

# ----------------- MAIN COMPILER -----------------

def main():
    slides_html = []

    # 1. Fetch District Menus & Holidays
    ics_url = DEFAULT_FEEDS[0]["url"]
    menus, holidays = parse_ics_menu_and_notices(ics_url)

    if menus:
        slides_html.append(f"""
        <div class="slide active" data-title="District Lunch & Breakfast" data-duration="25">
          <div class="grid-container">
            {"".join(menus)}
          </div>
        </div>
        """)

    if holidays:
        slides_html.append(f"""
        <div class="slide" data-title="Upcoming District Notices" data-duration="20">
          <div class="grid-container">
            {"".join(holidays)}
          </div>
        </div>
        """)

    # 2. NASA Picture of the Day
    nasa_slide = parse_nasa_apod(DEFAULT_FEEDS[1]["url"])
    if nasa_slide:
        slides_html.append(nasa_slide)

    # 3. Merriam-Webster Word of the Day
    wotd_slide = parse_word_of_the_day(DEFAULT_FEEDS[2]["url"])
    if wotd_slide:
        slides_html.append(wotd_slide)

    # Compile into template
    with open("template_display.html", "r", encoding="utf-8") as f:
        template = f.read()

    now_str = datetime.now().strftime("%b %d, %I:%M %p")
    output = template.replace("{{BUILD_TIMESTAMP}}", f"Sync: {now_str}")
    output = output.replace("{{SLIDES_HTML}}", "\n".join(slides_html))

    # Save to display.html
    with open("display.html", "w", encoding="utf-8") as f:
        f.write(output)

    # Also keep index.html pointing to display.html or mirrored
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(output)

if __name__ == "__main__":
    main()
