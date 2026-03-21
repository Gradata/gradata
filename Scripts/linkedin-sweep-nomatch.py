"""
LinkedIn Profile Sweep
Visits profiles from a CSV, pulls actual current title + location from LinkedIn.
100 profiles per run (daily safe limit). Saves progress after every profile.

Anti-detection features:
- Feed warm-up before sweeping (30-60s browsing feed)
- Random scroll patterns (not instant jumps)
- Variable page dwell time (8-20s per profile)
- Coffee breaks every 15-20 profiles (3-5 min pause)
- Random between-profile delays (45-90s)
- Human-like scroll depths and speeds

Usage:
  python linkedin-sweep-nomatch.py                     (defaults to NO-MATCH list)
  python linkedin-sweep-nomatch.py batch-02             (sweeps batch-02.csv)
  python linkedin-sweep-nomatch.py path/to/file.csv     (sweeps any CSV)
"""
import csv
import re
import sys
import time
import os
import random
from pathlib import Path
from playwright.sync_api import sync_playwright

# --- Config ---
BASE_DIR = r"C:\Users\olive\OneDrive\Desktop\Sprites Work\leads\wip\claude-code-80hrs-2026-03-16"

# Determine input/output from command line arg
if len(sys.argv) > 1:
    arg = sys.argv[1]
    # If just a batch name like "batch-02", look in batches folder
    if not arg.endswith(".csv"):
        arg = arg + ".csv"
    if os.path.sep not in arg and "/" not in arg:
        # Check batches folder first
        batches_path = os.path.join(BASE_DIR, "batches", arg)
        if os.path.exists(batches_path):
            INPUT_CSV = batches_path
        else:
            INPUT_CSV = os.path.join(BASE_DIR, arg)
    else:
        INPUT_CSV = arg
    # Output goes next to input with -SWEPT suffix
    stem = Path(INPUT_CSV).stem
    OUTPUT_CSV = os.path.join(os.path.dirname(INPUT_CSV), stem + "-SWEPT.csv")
else:
    INPUT_CSV = os.path.join(BASE_DIR, "claude-code-80hrs-NO-MATCH.csv")
    OUTPUT_CSV = os.path.join(BASE_DIR, "claude-code-80hrs-NO-MATCH-SWEPT.csv")

BROWSER_PROFILE = r"C:\Users\olive\.linkedin-browser"
DAILY_LIMIT = 100
DELAY_MIN = 45
DELAY_MAX = 90

# Anti-detection settings
DWELL_MIN = 8           # Min seconds on each profile
DWELL_MAX = 20          # Max seconds on each profile
WARMUP_MIN = 30         # Min seconds browsing feed before sweep
WARMUP_MAX = 60         # Max seconds browsing feed before sweep
BREAK_EVERY_MIN = 15    # Take a break every 15-20 profiles
BREAK_EVERY_MAX = 20
BREAK_MIN = 180         # Break duration: 3-5 minutes
BREAK_MAX = 300

# JS extractor — pulls current role from Experience section + location
JS_EXTRACTOR = """
(() => {
  const name = document.querySelector('h1')?.innerText?.trim().replace(/\\s*(She\\/Her|He\\/Him|They\\/Them)\\s*/i,'').replace(/·.*/,'').trim() || '';
  const locEl = document.querySelector('.text-body-small.inline.t-black--light.break-words');
  const fullLocation = locEl?.innerText?.trim() || '';
  const locParts = fullLocation.split(',').map(s => s.trim());
  let country = '', state = '';
  if (locParts.length >= 3) { state = locParts[1]; country = locParts[2]; }
  else if (locParts.length === 2) { state = locParts[0]; country = locParts[1]; }
  else { country = locParts[0] || ''; }
  let title = '', company = '';
  const sections = Array.from(document.querySelectorAll('section'));
  let expSection = sections.find(s => s.querySelector('h2')?.innerText?.trim().toLowerCase().includes('experience'));
  if (expSection) {
    const firstLi = expSection.querySelector('li');
    if (firstLi) {
      title = firstLi.querySelector('.t-bold span[aria-hidden="true"]')?.innerText?.trim() || '';
      const normalSpans = Array.from(firstLi.querySelectorAll('.t-normal span[aria-hidden="true"]'));
      if (normalSpans.length > 0) company = normalSpans[0].innerText.trim().replace(/\\s*[·•]\\s*(Full-time|Part-time|Contract|Freelance|Self-employed|Internship).*/i,'').trim();
    }
  }
  return {name, fullLocation, state, country, title, company};
})()
"""

# --- Expanded Geo (skip only countries that can't afford $500-1k/mo) ---
GEO_SKIP = {
    "india", "pakistan", "bangladesh", "nepal", "sri lanka",
    "egypt", "nigeria", "kenya", "ghana", "ethiopia", "tanzania", "uganda",
    "philippines", "indonesia", "vietnam", "thailand", "cambodia", "myanmar", "laos",
    "venezuela", "cuba", "bolivia", "nicaragua", "honduras", "el salvador",
    "iran", "syria", "iraq", "afghanistan",
    "uzbekistan", "tajikistan", "turkmenistan", "kyrgyzstan",
}

# --- ICP Title Filters ---
TITLE_INCLUDE = [
    "performance marketing", "paid media", "ppc", "sem", "sea", "google ads", "meta ads",
    "facebook ads", "head of marketing", "vp of marketing", "vp marketing", "vp, marketing",
    "director of marketing", "director marketing", "head of growth", "growth marketing",
    "growth lead", "growth strategist", "cmo", "chief marketing", "fractional cmo",
    "demand gen", "ecommerce", "e-commerce", "dtc", "agency principal",
    "founder", "co-founder", "cofounder", "owner",
    "digital marketing", "marketing director", "marketing manager", "marketing lead",
    "marketing consultant", "head of digital", "paid search", "paid social",
    "media buyer", "media buying", "ad operations", "acquisition marketing",
    "retention marketing", "lifecycle marketing", "brand marketing",
    "creative director", "creative strategist", "marketing executive",
    "marketing operations", "marketing strategy", "senior marketing",
    "marketing coordinator", "digital strategist", "media strategist",
]

TITLE_SKIP = [
    "student", "intern", "teacher", "professor", "lecturer",
    "nurse", "doctor", "therapist", "physician",
    "lawyer", "attorney", "paralegal",
    "accountant", "accounting",
    "recruiter", "recruiting", "talent acquisition", "human resources",
    "data scientist", "data analyst", "data engineer",
    "software engineer", "developer", "devops",
    "executive assistant", "receptionist", "administrative",
]

OUTPUT_COLS = [
    "Full Name", "First Name", "Last Name", "Title", "Company",
    "LinkedIn URL", "State/Province", "Country", "Company Domain",
    "Company LinkedIn URL", "Sweep Status"
]


def guess_domain(company):
    if not company or company == "Unknown":
        return ""
    clean = re.sub(r'[^a-z0-9\s]', '', company.lower()).strip()
    clean = re.sub(r'\s+', '', clean)
    return clean + ".com" if clean else ""


def classify_title(title):
    t = title.lower().strip()
    if not t:
        return "unknown"
    for skip in TITLE_SKIP:
        if skip in t:
            return "skip"
    for inc in TITLE_INCLUDE:
        if inc in t:
            return "icp"
    return "no-match"


def classify_geo(country):
    c = country.lower().strip()
    if not c:
        return "unknown"
    for g in GEO_SKIP:
        if g in c:
            return "skip"
    return "ok"


def load_already_swept():
    """Load LinkedIn URLs already swept from output CSV."""
    swept = set()
    if os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = (row.get("LinkedIn URL") or "").strip().lower().rstrip("/")
                if url:
                    swept.add(url)
    return swept


def append_to_output(row_data):
    """Append a single row to the output CSV (creates file + header if needed)."""
    file_exists = os.path.exists(OUTPUT_CSV) and os.path.getsize(OUTPUT_CSV) > 0
    with open(OUTPUT_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row_data)


def human_scroll(page):
    """Scroll like a human — random depths, random speeds, sometimes scroll back up."""
    # Initial scroll down to about section
    scroll_y = random.randint(300, 500)
    page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
    time.sleep(random.uniform(1.0, 2.5))

    # Scroll further to experience section
    scroll_y = random.randint(600, 1000)
    page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
    time.sleep(random.uniform(1.5, 3.0))

    # Sometimes scroll back up a bit (like re-reading something)
    if random.random() < 0.3:
        scroll_back = scroll_y - random.randint(100, 300)
        page.evaluate(f"window.scrollTo({{top: {scroll_back}, behavior: 'smooth'}})")
        time.sleep(random.uniform(0.5, 1.5))
        # Then back down
        page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
        time.sleep(random.uniform(0.5, 1.0))


def warmup_feed(page):
    """Browse the LinkedIn feed for a while before starting sweeps. Looks natural."""
    warmup_time = random.randint(WARMUP_MIN, WARMUP_MAX)
    print(f"\n  Warming up on feed for {warmup_time}s (anti-detection)...")

    # Scroll through feed a few times
    elapsed = 0
    scroll_pos = 0
    while elapsed < warmup_time:
        scroll_pos += random.randint(300, 800)
        page.evaluate(f"window.scrollTo({{top: {scroll_pos}, behavior: 'smooth'}})")
        wait = random.uniform(3.0, 8.0)
        time.sleep(wait)
        elapsed += wait

        # Sometimes scroll back up (like re-reading a post)
        if random.random() < 0.2:
            scroll_back = max(0, scroll_pos - random.randint(200, 500))
            page.evaluate(f"window.scrollTo({{top: {scroll_back}, behavior: 'smooth'}})")
            time.sleep(random.uniform(2.0, 5.0))
            elapsed += 3

    print(f"  Warm-up complete. Starting sweep...\n")


def main():
    # Load input
    with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    # Find which ones still need sweeping
    already_swept = load_already_swept()
    to_visit = []
    for r in rows:
        url = (r.get("LinkedIn URL") or "").strip().lower().rstrip("/")
        if url and url not in already_swept:
            to_visit.append(r)

    total_remaining = len(to_visit)
    batch_size = min(DAILY_LIMIT, total_remaining)

    print(f"=" * 60)
    print(f"  LinkedIn Sweep")
    print(f"  Input: {os.path.basename(INPUT_CSV)}")
    print(f"  Total remaining: {total_remaining}")
    print(f"  Today's batch: {batch_size} profiles")
    print(f"  Already swept: {len(already_swept)}")
    print(f"  Est. time: ~{batch_size * 68 // 60} min (with breaks)")
    print(f"  Days left after today: {max(0, (total_remaining - batch_size) // DAILY_LIMIT + (1 if (total_remaining - batch_size) % DAILY_LIMIT else 0))}")
    print(f"=" * 60)

    if batch_size == 0:
        print("\nAll profiles already swept!")
        return

    # Decide when to take breaks (every 15-20 profiles)
    next_break = random.randint(BREAK_EVERY_MIN, BREAK_EVERY_MAX)

    with sync_playwright() as p:
        os.makedirs(BROWSER_PROFILE, exist_ok=True)
        context = p.chromium.launch_persistent_context(
            BROWSER_PROFILE,
            headless=False,
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        page = context.pages[0] if context.pages else context.new_page()

        # Login check
        try:
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        except Exception:
            time.sleep(5)
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        if "login" in page.url or "signin" in page.url or "checkpoint" in page.url:
            print("\n  LinkedIn login required!")
            print("  Log in in the browser window, then press ENTER here.")
            input("\n  Press ENTER to continue after logging in... ")
            time.sleep(5)
            try:
                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            except Exception:
                time.sleep(5)
                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)
            if "login" in page.url or "signin" in page.url or "checkpoint" in page.url:
                print("ERROR: Still not logged in. Exiting.")
                context.close()
                return

        print("\nLinkedIn login confirmed.")

        # Warm up on feed before starting
        warmup_feed(page)

        icp_found = 0
        skipped = 0
        errors = 0

        for i, row in enumerate(to_visit[:batch_size]):
            url = (row.get("LinkedIn URL") or "").strip()
            name = (row.get("Full Name") or "").strip()
            num = i + 1

            # Coffee break every 15-20 profiles
            if i > 0 and i % next_break == 0:
                break_duration = random.randint(BREAK_MIN, BREAK_MAX)
                print(f"\n  ☕ Coffee break ({break_duration}s / {break_duration // 60}min)...")
                print(f"     [{num - 1} done, {batch_size - num + 1} left]")

                # Go back to feed during break (looks natural)
                try:
                    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
                    # Scroll feed lazily during break
                    scroll_pos = 0
                    break_elapsed = 0
                    while break_elapsed < break_duration:
                        scroll_pos += random.randint(200, 600)
                        page.evaluate(f"window.scrollTo({{top: {scroll_pos}, behavior: 'smooth'}})")
                        chunk = random.uniform(8, 20)
                        time.sleep(chunk)
                        break_elapsed += chunk
                except Exception:
                    time.sleep(break_duration)

                # Pick next break interval
                next_break_at = i + random.randint(BREAK_EVERY_MIN, BREAK_EVERY_MAX)
                # Override the modulo check — use a counter instead
                next_break = random.randint(BREAK_EVERY_MIN, BREAK_EVERY_MAX)
                print(f"  Break over. Resuming...\n")

            print(f"[{num}/{batch_size}] {name}")
            print(f"  {url}")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Variable dwell time (8-20s) instead of flat 5s
                dwell = random.uniform(DWELL_MIN, DWELL_MAX)

                # Handle login wall
                if "login" in page.url or "signin" in page.url:
                    print("  WARNING: Hit login wall. Log back in and press ENTER...")
                    input()
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Wait a bit before scrolling (like reading the headline first)
                time.sleep(random.uniform(1.5, 3.0))

                # Human-like scrolling
                human_scroll(page)

                # Spend remaining dwell time on the page
                remaining_dwell = max(0, dwell - 5)
                if remaining_dwell > 0:
                    time.sleep(remaining_dwell)

                # Extract data
                data = page.evaluate(JS_EXTRACTOR)

                title = (data.get("title") or "").strip()
                company = (data.get("company") or "").strip()
                state = (data.get("state") or "").strip()
                country = (data.get("country") or "").strip()
                extracted_name = (data.get("name") or "").strip()

                # Use extracted name if better
                if extracted_name:
                    parts = extracted_name.split(" ", 1)
                    first = parts[0]
                    last = parts[1] if len(parts) > 1 else ""
                else:
                    first = (row.get("First Name") or "").strip()
                    last = (row.get("Last Name") or "").strip()
                    extracted_name = name

                # Classify
                title_class = classify_title(title)
                geo_class = classify_geo(country)

                if geo_class == "skip":
                    status = "SKIP:geo"
                    skipped += 1
                elif title_class == "skip":
                    status = "SKIP:title"
                    skipped += 1
                elif title_class == "icp":
                    status = "ICP"
                    icp_found += 1
                elif not title:
                    status = "SKIP:no-data"
                    skipped += 1
                else:
                    status = "NO-MATCH"
                    skipped += 1

                icon = "✓" if status == "ICP" else "✗"
                print(f"  {icon} {title or 'No title'} @ {company or 'No company'} | {state}, {country} | {status}")

                # Write to output
                append_to_output({
                    "Full Name": extracted_name,
                    "First Name": first,
                    "Last Name": last,
                    "Title": title,
                    "Company": company,
                    "LinkedIn URL": url,
                    "State/Province": state,
                    "Country": country,
                    "Company Domain": guess_domain(company),
                    "Company LinkedIn URL": "",
                    "Sweep Status": status,
                })

            except Exception as e:
                print(f"  ERROR: {e}")
                errors += 1
                append_to_output({
                    "Full Name": name,
                    "First Name": (row.get("First Name") or "").strip(),
                    "Last Name": (row.get("Last Name") or "").strip(),
                    "Title": "",
                    "Company": "",
                    "LinkedIn URL": url,
                    "State/Province": "",
                    "Country": "",
                    "Company Domain": "",
                    "Company LinkedIn URL": "",
                    "Sweep Status": "ERROR",
                })

            # Rate limiting — variable delay between profiles
            if i < batch_size - 1:
                wait = random.randint(DELAY_MIN, DELAY_MAX)
                print(f"  Waiting {wait}s...")
                time.sleep(wait)

        context.close()

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  Today's sweep complete!")
    print(f"  Visited: {batch_size}")
    print(f"  ICP found: {icp_found}")
    print(f"  Skipped/No-match: {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Remaining after today: {total_remaining - batch_size}")
    print(f"  Output: {OUTPUT_CSV}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
