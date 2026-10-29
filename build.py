import urllib.request
import json
import re
import os
import xml.etree.ElementTree as ET
from datetime import datetime, date

ICS_URL = "https://www.ascensionschools.org/fs/calendar-manager/events.ics?feed_id=c20467f1-be50-44e0-be8b-9ab7b494654c"
NASA_APOD_URL = "https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY"
WOTD_URL = "https://www.merriam-webster.com/wotd/feed/rss2"
ANNOUNCEMENTS_FILE = "announcements.json"

def http_get(url):
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SignageBot/1.0'}
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode('utf-8', errors='ignore')

# ----------------- FEED PARSERS -----------------

def parse_ics_menu_and_notices(url):
    try:
        raw = http_get(url)
    except Exception as e:
        print(f"Warning: Could not fetch district ICS ({e})")
        return [], []

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
        if data.get("media_type") != "image":
            return ""

        title = data.get("title", "NASA Astronomy Picture of the Day")
        img_url = data.get("url", "")
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
        print(f"Warning: NASA APOD skipped ({e})")
        return ""

def parse_word_of_the_day(url):
    try:
        raw = http_get(url)
        root = ET.fromstring(raw)
        channel = root.find("channel")
        item = channel.find("item")

        word = item.find("title").text
        desc = item.find("description").text
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
        print(f"Warning: WOTD skipped ({e})")
        return ""

def parse_generic_rss_slide(title, rss_url, duration, theme):
    try:
        raw = http_get(rss_url)
        root = ET.fromstring(raw)
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")

        cards = []
        for item in items[:4]:
            i_title = item.find("title").text if item.find("title") is not None else "Update"
            i_desc = item.find("description").text if item.find("description") is not None else ""
            clean_desc = re.sub(r'<[^>]+>', '', i_desc).strip()
            if len(clean_desc) > 140:
                clean_desc = clean_desc[:140] + "..."

            cards.append(f"""
            <div class="card">
              <h2>{i_title}</h2>
              <p style="margin-top:0.4rem; color:#cbd5e1; font-size:1rem;">{clean_desc}</p>
            </div>
            """)

        if not cards:
            return ""

        return f"""
        <div class="slide {theme}" data-title="{title}" data-duration="{duration}">
          <div class="grid-container">
            {"".join(cards)}
          </div>
        </div>
        """
    except Exception as e:
        print(f"Warning: Failed to fetch custom RSS {rss_url}: {e}")
        return ""

# ----------------- ANNOUNCEMENTS LOADER -----------------

def load_user_announcements_and_feeds():
    slides = []
    if not os.path.exists(ANNOUNCEMENTS_FILE):
        return slides

    try:
        with open(ANNOUNCEMENTS_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except Exception as e:
        print(f"Warning: Could not read {ANNOUNCEMENTS_FILE} ({e})")
        return slides

    today_str = date.today().strftime("%Y-%m-%d")

    for item in entries:
        start_date = item.get("startDate")
        end_date = item.get("endDate")

        # Scheduling checks
        if start_date and start_date > today_str:
            continue
        if end_date and end_date < today_str:
            continue

        theme = item.get("theme", "theme-navy")
        duration = item.get("duration", 15)
        headline = item.get("headline", "Special Announcement")
        entry_type = item.get("type", "announcement")

        if entry_type == "announcement":
            details = item.get("details", "")
            badge = "Birthday Celebration" if theme == "theme-gold" else "Special Notice"

            slides.append(f"""
            <div class="slide {theme}" data-title="District Announcement" data-duration="{duration}">
              <div class="hero-layout">
                <div class="hero-content">
                  <span class="hero-tag">{badge}</span>
                  <h2 style="font-size: 3.2rem;">{headline}</h2>
                  <p style="font-size: 1.5rem; line-height: 1.6;">{details}</p>
                </div>
              </div>
            </div>
            """)

        elif entry_type == "rss":
            rss_url = item.get("rssUrl")
            if rss_url:
                slide = parse_generic_rss_slide(headline, rss_url, duration, theme)
                if slide:
                    slides.append(slide)

    return slides

# ----------------- MAIN COMPILER -----------------

def main():
    slides_html = []

    # 1. Custom Announcements & Feeds from admin.html
    user_slides = load_user_announcements_and_feeds()
    slides_html.extend(user_slides)

    # 2. District Lunch & Breakfast Menu
    menus, holidays = parse_ics_menu_and_notices(ICS_URL)
    if menus:
        slides_html.append(f"""
        <div class="slide" data-title="District Dining" data-duration="25">
          <div class="grid-container">
            {"".join(menus)}
          </div>
        </div>
        """)

    # 3. District Holidays & School Closures
    if holidays:
        slides_html.append(f"""
        <div class="slide" data-title="Upcoming District Notices" data-duration="20">
          <div class="grid-container">
            {"".join(holidays)}
          </div>
        </div>
        """)

    # 4. NASA APOD
    nasa_slide = parse_nasa_apod(NASA_APOD_URL)
    if nasa_slide:
        slides_html.append(nasa_slide)

    # 5. Merriam-Webster Word of the Day
    wotd_slide = parse_word_of_the_day(WOTD_URL)
    if wotd_slide:
        slides_html.append(wotd_slide)

    # Fallback if everything failed
    if not slides_html:
        slides_html.append("""
        <div class="slide" data-title="Ascension Signage" data-duration="15">
          <div class="hero-layout">
            <div class="hero-content">
              <h2>Ascension Public Schools</h2>
              <p>Signage network online. Awaiting scheduled announcements.</p>
            </div>
          </div>
        </div>
        """)

    # Read template and inject slides
    with open("template_display.html", "r", encoding="utf-8") as f:
        template = f.read()

    now_str = datetime.now().strftime("%b %d, %I:%M %p")
    output = template.replace("{{BUILD_TIMESTAMP}}", f"Sync: {now_str}")
    output = output.replace("{{SLIDES_HTML}}", "\n".join(slides_html))

    # Write both display.html and index.html
    with open("display.html", "w", encoding="utf-8") as f:
        f.write(output)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(output)

if __name__ == "__main__":
    main()
