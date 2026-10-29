import os
import json
from datetime import datetime, date

def load_custom_entries():
    slides = []
    if not os.path.exists("announcements.json"):
        return slides

    try:
        with open("announcements.json", "r", encoding="utf-8") as f:
            entries = json.load(f)
    except Exception:
        return slides

    today = date.today()

    for item in entries:
        # Check start and end dates for scheduling
        start_str = item.get("startDate")
        end_str = item.get("endDate")

        if start_str:
            s_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            if today < s_date:
                continue # Event hasn't started yet

        if end_str:
            e_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            if today > e_date:
                continue # Event expired

        theme = item.get("theme", "theme-navy")
        duration = item.get("duration", 15)

        # Handle Announcement
        if item.get("type") == "announcement":
            slides.append(f"""
            <div class="slide {theme}" data-title="Announcement" data-duration="{duration}">
              <div class="hero-layout">
                <div class="hero-content">
                  <span class="hero-tag">Special Notice</span>
                  <h2 style="font-size: 3.2rem;">{item.get('headline')}</h2>
                  <p style="font-size: 1.5rem;">{item.get('details')}</p>
                </div>
              </div>
            </div>
            """)

        # Handle Custom RSS Feed added from the form
        elif item.get("type") == "rss" and item.get("rssUrl"):
            # Call your RSS parsing logic here
            pass

    return slides
