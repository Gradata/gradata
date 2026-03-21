"""
LinkedIn Profile Sweep - Adriaan $2B Perf Mktg Post Commenters
Visits profiles, extracts data via JS, applies ICP/geo filters, updates CSV.
Usage: python linkedin-sweep.py
  - First run: logs you into LinkedIn (manual), then sweeps automatically.
  - Subsequent runs: reuses saved session.
"""
import csv
import json
import time
import os
import sys
import random
from pathlib import Path
from playwright.sync_api import sync_playwright

# --- Config ---
CSV_PATH = r"C:\Users\olive\OneDrive\Desktop\Sprites Work\leads\wip\adriaan-2b-perf-mktg-2026-03-13\katya-post-enriched-2026-03-13.csv"
BROWSER_PROFILE = r"C:\Users\olive\.linkedin-browser"
DELAY_MIN = 30
DELAY_MAX = 60
PAGE_LOAD_WAIT = 5

# JS extractor (confirmed working from previous session)
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
  let title = '', company = '', companyLiUrl = '';
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
  const companyLinks = Array.from(document.querySelectorAll('a[href*="linkedin.com/company/"]'));
  if (companyLinks.length > 0) companyLiUrl = companyLinks[0].href.split('?')[0];
  return {name, fullLocation, state, country, title, company, companyLiUrl};
})()
"""

# --- ICP Filters ---
GEO_PRIMARY = {"united states", "united kingdom", "australia", "new zealand", "canada"}
GEO_SECONDARY = {"germany", "france", "netherlands", "belgium", "sweden", "denmark",
                  "norway", "finland", "austria", "switzerland", "spain", "portugal", "italy"}
GEO_SKIP = {"india", "pakistan", "bangladesh", "united arab emirates", "uae", "saudi arabia",
            "egypt", "algeria", "poland", "romania", "ukraine", "russia", "bulgaria", "croatia",
            "serbia", "hungary", "czech republic", "czechia", "greece", "turkey", "vietnam",
            "indonesia", "philippines", "thailand", "malaysia", "singapore", "south africa",
            "brazil", "mexico", "colombia", "argentina", "chile", "peru", "belarus", "china"}

TITLE_INCLUDE = [
    "performance marketing", "paid media", "ppc", "sem", "sea", "google ads", "meta ads",
    "head of marketing", "vp of marketing", "vice president of marketing", "vp marketing",
    "director of marketing", "director marketing", "head of growth", "growth marketing",
    "cmo", "chief marketing", "fractional cmo", "demand gen", "ecommerce", "e-commerce",
    "dtc", "agency principal", "managing director", "founder", "owner", "digital marketing",
    "marketing director", "marketing manager", "marketing consultant", "head of digital",
    "performance manager", "paid search", "paid social", "media buyer", "ad operations",
    "marketing lead", "growth lead", "caio", "cmo"
]

TITLE_SKIP = [
    "seo specialist", "seo manager", "seo analyst", "social media manager",
    "social media specialist", "content writer", "content manager", "content strategist",
    "bizdev", "business development", "data scientist", "data analyst", "data engineer",
    "product manager", "product owner", "software engineer", "developer", "programmer",
    "hr ", "human resources", "talent", "recruiter", "finance", "accounting", "accountant",
    "legal", "procurement", "sales development", "sdr", "bdr", "venture capital", "investor",
    "it manager", "it director", "devops", "receptionist", "administrative", "professor",
    "teacher", "lecturer", "student", "intern"
]


def classify_geo(country_str):
    c = country_str.lower().strip()
    if not c or c == "unknown":
        return "unknown"
    for g in GEO_PRIMARY:
        if g in c:
            return "primary"
    for g in GEO_SECONDARY:
        if g in c:
            return "secondary"
    for g in GEO_SKIP:
        if g in c:
            return "skip"
    return "unknown"


def classify_title(title_str):
    t = title_str.lower().strip()
    if not t or t == "unknown":
        return "unknown"
    for skip in TITLE_SKIP:
        if skip in t:
            return "skip"
    for inc in TITLE_INCLUDE:
        if inc in t:
            return "include"
    return "unclear"


def determine_icp(title, company, country, state):
    geo = classify_geo(country)
    title_class = classify_title(title)

    if geo == "skip":
        region = country.lower().strip()
        for g in GEO_SKIP:
            if g in region:
                return f"SKIP:geo-{g.replace(' ', '-')}"
        return f"SKIP:geo-{region}"

    if title_class == "skip":
        return "SKIP:not-marketing"

    if title == "Unknown" or not title:
        return "SKIP:no-data"

    if geo in ("primary", "secondary") and title_class == "include":
        return "ICP"

    if geo == "unknown" and title_class == "include":
        return "ICP"  # benefit of the doubt if title matches

    if title_class == "unclear":
        return f"SKIP:unclear-title"

    return "SKIP:unclear-fit"


def read_csv():
    rows = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def write_csv(rows):
    if not rows:
        return
    fieldnames = rows[0].keys()
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows = read_csv()
    # Find rows that need visiting
    to_visit = []
    for i, row in enumerate(rows):
        status = row.get("ICP Status", "")
        if status == "SKIP:no-data-yet" or (status == "SKIP:no-data-yet" and "Unknown" in row.get("Title", "")):
            to_visit.append(i)

    if not to_visit:
        print("No profiles left to visit!")
        return

    print(f"Found {len(to_visit)} profiles to visit.")
    print(f"Starting from row {to_visit[0] + 2} (CSV line)...")

    with sync_playwright() as p:
        # Launch with persistent context for LinkedIn login
        os.makedirs(BROWSER_PROFILE, exist_ok=True)
        context = p.chromium.launch_persistent_context(
            BROWSER_PROFILE,
            headless=False,
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        page = context.pages[0] if context.pages else context.new_page()

        # Check if already logged in
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        if "login" in page.url or "signin" in page.url:
            print("\n" + "=" * 60)
            print("  LinkedIn login required!")
            print("  Log in to LinkedIn in the browser window.")
            print("  Press ENTER here when you see the LinkedIn feed.")
            print("=" * 60)
            input("\n  Press ENTER to continue after logging in... ")

            # Verify login worked — wait for any redirect to finish first
            time.sleep(5)
            try:
                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            except Exception:
                # If navigation interrupted by redirect, wait and try once more
                time.sleep(5)
                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)
            if "login" in page.url or "signin" in page.url or "checkpoint" in page.url:
                print("ERROR: Still not logged in. Exiting.")
                context.close()
                return

        print("\nLinkedIn login confirmed. Starting sweep...\n")

        visited = 0
        for idx in to_visit:
            row = rows[idx]
            name = row["Full Name"]
            url = row["LinkedIn URL"]
            csv_line = idx + 2

            print(f"[{csv_line}/113] Visiting: {name}")
            print(f"  URL: {url}")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(PAGE_LOAD_WAIT)

                # Check for auth wall or "page not found"
                current_url = page.url
                if "login" in current_url or "signin" in current_url:
                    print("  WARNING: Hit login wall. Session may have expired.")
                    print("  Log back in and press ENTER to continue...")
                    input()
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(PAGE_LOAD_WAIT)

                # Scroll down to load experience section
                page.evaluate("window.scrollTo(0, 800)")
                time.sleep(2)

                # Run JS extractor
                data = page.evaluate(JS_EXTRACTOR)
                print(f"  Extracted: {data.get('title', 'N/A')} at {data.get('company', 'N/A')}, {data.get('country', 'N/A')}")

                # Update row
                extracted_name = data.get("name", "").strip()
                if extracted_name and extracted_name != name:
                    # Update name fields if JS got a better one
                    parts = extracted_name.split(" ", 1)
                    row["Full Name"] = extracted_name
                    row["First Name"] = parts[0] if parts else extracted_name
                    row["Last Name"] = parts[1] if len(parts) > 1 else ""

                title = data.get("title", "").strip() or "Unknown"
                company = data.get("company", "").strip() or "Unknown"
                state = data.get("state", "").strip()
                country = data.get("country", "").strip() or "Unknown"
                company_li = data.get("companyLiUrl", "").strip()

                row["Title"] = title
                row["Company"] = company
                row["State/Province"] = state
                row["Country"] = country
                if company_li:
                    row["Company LinkedIn URL"] = company_li

                # Determine ICP status
                icp_status = determine_icp(title, company, country, state)
                row["ICP Status"] = icp_status

                icon = "v" if icp_status == "ICP" else "x"
                print(f"  [{icon}] {icp_status}")

            except Exception as e:
                print(f"  ERROR: {e}")
                row["ICP Status"] = "SKIP:error"

            # Save after every profile
            write_csv(rows)
            visited += 1

            # Rate limiting - randomized 30-60s to avoid detection
            if idx != to_visit[-1]:
                wait = random.randint(DELAY_MIN, DELAY_MAX)
                print(f"  Waiting {wait}s before next profile...")
                time.sleep(wait)

        context.close()

    # Summary
    icp_count = sum(1 for r in rows if r.get("ICP Status") == "ICP")
    skip_count = sum(1 for r in rows if r.get("ICP Status", "").startswith("SKIP"))
    remaining = sum(1 for r in rows if r.get("ICP Status") == "SKIP:no-data-yet")

    print(f"\n{'=' * 60}")
    print(f"  Sweep complete!")
    print(f"  Visited: {visited}")
    print(f"  Total ICP: {icp_count}")
    print(f"  Total SKIP: {skip_count}")
    print(f"  Still remaining: {remaining}")
    print(f"  CSV saved: {CSV_PATH}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
