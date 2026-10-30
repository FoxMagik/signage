import urllib.request
import json
import re
import os
import xml.etree.ElementTree as ET
from datetime import datetime, date

ICS_URL = "https://www.ascensionschools.org/fs/calendar-manager/events.ics?feed_id=c20467f1-be50-44e0-be8b-9ab7b494654c"
ANNOUNCEMENTS_FILE = "announcements.json"

# Ascension Parish / Gonzales, LA coordinates for NWS weather
NWS_POINTS_URL = "https://api.weather.gov/points/30.2388,-90.9201"

def http_get(url):
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (District Signage Player; contact: it@ascensionschools.org)'}
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode('utf-8', errors='ignore')

# ----------------- 1. WEATHER SLIDE (NWS) -----------------

def parse_weather_slide():
    try:
        point_data = json.loads(http_get(NWS_POINTS_URL))
        forecast_url = point_data["properties"]["forecast"]

        forecast_data = json.loads(http_get(forecast_url))
        periods = forecast_data["properties"]["periods"][:3]

        cards = []
        for p in periods:
            cards.append(f"""
            <div class="card" style="border-left-color: #38bdf8;">
              <div class="meta">{p['name']}</div>
              <h2 style="font-size: 2.4rem; margin: 0.3rem 0;">{p['temperature']}&deg;{p['temperatureUnit']}</h2>
              <div style="font-size: 1.25rem; color: #fff; font-weight: 600; margin-bottom: 0.4rem;">{p['shortForecast']}</div>
              <p style="color: #94a3b8; font-size: 1.05rem; line-height: 1.5;">{p['detailedForecast'][:150]}...</p>
            </div>
            """)

        return f"""
        <div class="slide" data-title="Local Weather & Forecast" data-duration="18">
          <div class="grid-container">
            {"".join(cards)}
          </div>
        </div>
        """
    except Exception as e:
        print(f"Weather fetch notice: {e}")
        return ""

# ----------------- 2. DISTRICT CALENDAR / MENU -----------------

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

    for ev in upcoming[:6]:
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
              <p style="margin-top:0.6rem; color:#e2e8f0; font-size:1.2rem; line-height:1.5;">{notice_text}</p>
            </div>
            """)

    return menu_cards[:6], holiday_cards[:6]

# ----------------- 3. RSS PARSER (HERO IMAGES & SCALED TEXT) -----------------

def parse_generic_rss_slide(title, rss_url, duration, theme):
    try:
        raw = http_get(rss_url)
        root = ET.fromstring(raw)
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")

        if not items:
            return ""

        latest = items[0]
        i_title = latest.find("title").text if latest.find("title") is not None else title
        i_desc = latest.find("description").text if latest.find("description") is not None else ""
        
        # Enclosure, media:content, or raw HTML image extraction
        img_url = ""
        enclosure = latest.find("enclosure")
        if enclosure is not None and "image" in enclosure.attrib.get("type", ""):
            img_url = enclosure.attrib.get("url", "")
            
        if not img_url:
            for elem in latest:
                if elem.tag.endswith("content") and "image" in elem.attrib.get("type", ""):
                    img_url = elem.attrib.get("url", "")
                    break

        if not img_url:
            match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', i_desc)
            if match:
                img_url = match.group(1)

        clean_desc = re.sub(r'<[^>]+>', ' ', i_desc)
        clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()

        # Image Layout (e.g. NASA APOD)
        if img_url:
            if len(clean_desc) > 340:
                clean_desc = clean_desc[:340] + "..."

            return f"""
            <div class="slide {theme}" data-title="{title}" data-duration="{duration}">
              <div class="hero-layout">
                <div class="hero-media-layout">
                  <img src="{img_url}" alt="{i_title}">
                  <div class="hero-media-content">
                    <span class="hero-tag">{title}</span>
                    <h2 style="font-size: 2.8rem; line-height: 1.2; margin-bottom: 1.2rem;">{i_title}</h2>
                    <p style="font-size: 1.5rem; line-height: 1.6; color: #cbd5e1;">{clean_desc}</p>
                  </div>
                </div>
              </div>
            </div>
            """

        # Text-only Layout (e.g. Word of the Day)
        if len(clean_desc) > 520:
            clean_desc = clean_desc[:520] + "..."

        return f"""
        <div class="slide {theme}" data-title="{title}" data-duration="{duration}">
          <div class="hero-layout">
            <div class="hero-content" style="max-width: 100%;">
              <span class="hero-tag">{title}</span>
              <h2 style="font-size: 4rem; line-height: 1.15; margin-bottom: 1.5rem; color: var(--accent);">{i_title}</h2>
              <p style="font-size: 1.85rem; line-height: 1.65; color: #f1f5f9;">{clean_desc}</p>
            </div>
          </div>
        </div>
        """

    except Exception as e:
        print(f"Warning: Failed custom RSS ({rss_url}): {e}")
        return ""

# ----------------- 4. CUSTOM ANNOUNCEMENTS -----------------

def load_user_announcements_and_feeds():
    slides = []
    if not os.path.exists(ANNOUNCEMENTS_FILE):
        print(f"CRITICAL: {ANNOUNCEMENTS_FILE} does not exist in root!")
        return slides

    try:
        with open(ANNOUNCEMENTS_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except Exception as e:
        print(f"CRITICAL: Error reading {ANNOUNCEMENTS_FILE}: {e}")
        return slides

    today_str = date.today().strftime("%Y-%m-%d")
    print(f"Loaded {len(entries)} items from {ANNOUNCEMENTS_FILE}. Today: {today_str}")

    for idx, item in enumerate(entries):
        headline = item.get("headline", "Untitled")
        start_date = item.get("startDate")
        end_date = item.get("endDate")
        theme = item.get("theme", "theme-navy")
        duration = item.get("duration", 15)
        entry_type = item.get("type", "announcement")
        image_url = item.get("imageUrl", "").strip()

        # Date validity checks
        if start_date and start_date > today_str:
            print(f"  [Item {idx}] Skipped '{headline}': Starts {start_date}")
            continue
        if end_date and end_date < today_str:
            print(f"  [Item {idx}] Skipped '{headline}': Expired {end_date}")
            continue

        if entry_type == "announcement":
            details = item.get("details", "")
            badge = "Staff Celebration" if theme == "theme-gold" else "Announcement"

            if image_url:
                slides.append(f"""
                <div class="slide {theme}" data-title="Special Announcement" data-duration="{duration}">
                  <div class="hero-layout">
                    <div class="hero-media-layout">
                      <img src="{image_url}" alt="{headline}">
                      <div class="hero-media-content">
                        <span class="hero-tag">{badge}</span>
                        <h2 style="font-size: 3rem; line-height: 1.2; margin-bottom: 1.2rem;">{headline}</h2>
                        <p style="font-size: 1.6rem; line-height: 1.6; color: #cbd5e1;">{details}</p>
                      </div>
                    </div>
                  </div>
                </div>
                """)
            else:
                slides.append(f"""
                <div class="slide {theme}" data-title="Special Announcement" data-duration="{duration}">
                  <div class="hero-layout">
                    <div class="hero-content" style="max-width: 100%;">
                      <span class="hero-tag">{badge}</span>
                      <h2 style="font-size: 3.8rem; line-height: 1.2; margin-bottom: 1.5rem;">{headline}</h2>
                      <p style="font-size: 1.85rem; line-height: 1.6; color: #e2e8f0;">{details}</p>
                    </div>
                  </div>
                </div>
                """)
            print(f"  [Item {idx}] Added Announcement slide: '{headline}'")

        elif entry_type == "rss":
            rss_url = item.get("rssUrl")
            print(f"  [Item {idx}] Parsing RSS: '{headline}' -> {rss_url}")
            if rss_url:
                slide = parse_generic_rss_slide(headline, rss_url, duration, theme)
                if slide:
                    slides.append(slide)
                    print(f"  [Item {idx}] Added RSS slide: '{headline}'")
                else:
                    print(f"  [Item {idx}] Failed to parse RSS items.")

    return slides

# ----------------- MAIN COMPILER -----------------

def main():
    slides_html = []

    # 1. Weather Slide
    weather_slide = parse_weather_slide()
    if weather_slide:
        slides_html.append(weather_slide)

    # 2. Custom Announcements & Feeds from announcements.json
    user_slides = load_user_announcements_and_feeds()
    slides_html.extend(user_slides)

    # 3. District Lunch Menu
    menus, holidays = parse_ics_menu_and_notices(ICS_URL)
    if menus:
        slides_html.append(f"""
        <div class="slide" data-title="District Dining" data-duration="25">
          <div class="grid-container">
            {"".join(menus)}
          </div>
        </div>
        """)

    # 4. District Holidays / Closures
    if holidays:
        slides_html.append(f"""
        <div class="slide" data-title="Upcoming District Notices" data-duration="20">
          <div class="grid-container">
            {"".join(holidays)}
          </div>
        </div>
        """)

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

    # Guarantee ONLY slide 0 starts active
    cleaned_slides = [s.replace('class="slide active', 'class="slide') for s in slides_html]
    cleaned_slides[0] = cleaned_slides[0].replace('class="slide', 'class="slide active', 1)
    slides_html = cleaned_slides

    with open("template_display.html", "r", encoding="utf-8") as f:
        template = f.read()

    now_str = datetime.now().strftime("%b %d, %I:%M %p")
    output = template.replace("{{BUILD_TIMESTAMP}}", f"Sync: {now_str}")
    output = output.replace("{{SLIDES_HTML}}", "\n".join(slides_html))

    with open("display.html", "w", encoding="utf-8") as f:
        f.write(output)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(output)

    print(f"\nSUCCESS: Total slides compiled: {len(slides_html)}")

if __name__ == "__main__":
    main()
