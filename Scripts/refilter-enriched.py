"""
Full refilter of 6,333 enriched profiles using REAL title + company data.
Split by campaign source (Luna Chen Growth vs Daniel Paul Team).
"""
import json, re, csv, os

ENRICHED = 'c:/Users/olive/Downloads/dataset_linkedin-profile-scraper_2026-03-24_02-43-11-653.json'
LUNA_RAW = 'c:/Users/olive/Downloads/dataset_linkedin-post-comments_2026-03-24_00-56-50-577.json'
DANIEL_RAW = 'c:/Users/olive/Downloads/dataset_linkedin-post-comments_2026-03-24_00-33-37-176.json'
LUNA_DIR = 'c:/Users/olive/OneDrive/Desktop/Sprites Work/Leads/wip/luna-chen-growth-enriched'
DANIEL_DIR = 'c:/Users/olive/OneDrive/Desktop/Sprites Work/Leads/wip/daniel-paul-team-enriched'

# ============================================================
# STEP 1: Load enriched profiles
# ============================================================
print("Loading enriched profiles...")
with open(ENRICHED, 'r', encoding='utf-8') as f:
    enriched_raw = json.load(f)

profiles = {}
for e in enriched_raw:
    url = (e.get('linkedinUrl') or '').rstrip('/').lower()
    if not url or '/company/' in url:
        continue

    # Extract current position
    title = ''
    company = ''
    company_url = ''
    cp = e.get('currentPosition', [])
    if cp and isinstance(cp, list) and len(cp) > 0:
        company = cp[0].get('companyName', '') or ''
        title = cp[0].get('position', '') or ''
        company_url = cp[0].get('companyLinkedinUrl', '') or ''

    # Fallback to headline if no current position
    if not title:
        title = e.get('headline', '') or ''

    headline = e.get('headline', '') or ''

    # Company size
    emp = e.get('employeeCountRange', {})
    emp_start = emp.get('start', 0) if emp else 0
    emp_end = emp.get('end', 0) if emp else 0
    company_size = f"{emp_start}-{emp_end}" if emp_start else ''

    # Location
    loc = e.get('location', {}) or {}
    location_text = ''
    country_code = ''
    if isinstance(loc, dict):
        location_text = loc.get('linkedinText', '') or ''
        parsed = loc.get('parsed', {}) or {}
        country_code = parsed.get('countryCode', '') or ''

    # Experience for richer filtering
    experience = e.get('experience', []) or []
    all_companies = []
    for exp in experience[:3]:  # Last 3 roles
        if isinstance(exp, dict):
            all_companies.append(exp.get('companyName', '') or '')

    profiles[url] = {
        'first_name': e.get('firstName', '') or '',
        'last_name': e.get('lastName', '') or '',
        'title': title,
        'company': company,
        'company_size': company_size,
        'company_size_start': emp_start,
        'company_size_end': emp_end,
        'headline': headline,
        'linkedin_url': url,
        'location': location_text,
        'country_code': country_code,
        'open_to_work': e.get('openToWork', False),
        'premium': e.get('premium', False),
        'hiring': e.get('hiring', False),
        'top_skills': e.get('topSkills', '') or '',
        'about': (e.get('about', '') or '')[:200],
        'all_companies': ' | '.join(all_companies),
        'company_url': company_url,
    }

print(f"Loaded {len(profiles)} person profiles")

# ============================================================
# STEP 2: Map URLs to campaigns
# ============================================================
print("\nMapping URLs to campaigns...")
luna_urls = set()
daniel_urls = set()

with open(LUNA_RAW, 'r', encoding='utf-8') as f:
    luna_data = json.load(f)
growth_re = re.compile(r'\bgrowth\b|\bgrow\b|\bgrowing\b', re.IGNORECASE)
for d in luna_data:
    if growth_re.search(str(d.get('commentary', ''))):
        url = (d.get('actor', {}).get('linkedinUrl', '') or '').rstrip('/').lower()
        if url and url in profiles:
            luna_urls.add(url)

with open(DANIEL_RAW, 'r', encoding='utf-8') as f:
    daniel_data = json.load(f)
team_re = re.compile(r'\bteam\b', re.IGNORECASE)
for d in daniel_data:
    if team_re.search(str(d.get('commentary', ''))):
        url = (d.get('actor', {}).get('linkedinUrl', '') or '').rstrip('/').lower()
        if url and url in profiles:
            daniel_urls.add(url)

print(f"Luna: {len(luna_urls)} | Daniel: {len(daniel_urls)} | Overlap: {len(luna_urls & daniel_urls)}")

# ============================================================
# STEP 3: Filter using REAL title + company + headline
# ============================================================

# Junk
junk_re = re.compile(r'\bstudent\b|\bintern\b|seeking opportunities|job seeker|looking for.*role|\bfresher\b|\btrainee\b|\bapprentice\b', re.IGNORECASE)

# Dev titles - use TITLE not headline (headline can say "full stack marketer")
dev_re = re.compile(r'full.?stack dev|front.?end dev|back.?end dev|software eng|software dev|\bweb dev|mobile dev|\bdevops\b|data eng|machine learning eng|\bml eng|blockchain dev|cloud eng|site reliability|java dev|python dev|\.net dev|react dev|node dev|ios dev|android dev|\bqa eng|test eng|\bembedded\b|firmware|hardware eng|network eng|security eng|infra eng|platform eng|systems eng', re.IGNORECASE)

# Non-marketing
nonmktg_re = re.compile(r'\brecruiter\b|talent acq|human resource|\bhr manager\b|\bhr director\b|\blawyer\b|\battorney\b|\blegal counsel\b|\bteacher\b|\bprofessor\b|\btherapist\b|\bnurse\b|\bdoctor\b|\bphysician\b|\bdentist\b|\bpharmacist\b|\baccountant\b|\bauditor\b|\bbookkeeper\b|real estate agent|\brealtor\b|civil eng|mechanical eng|electrical eng|chemical eng', re.IGNORECASE)

# Tier patterns - applied to TITLE + HEADLINE combined
t1_re = re.compile(r'CMO|chief market|chief growth|chief revenue|chief digital|VP.{0,5}market|VP.{0,5}growth|VP.{0,5}digital|VP.{0,5}demand|VP.{0,5}performance|head of market|head of growth|head of digital|head of demand|head of performance|head of paid|head of media|head of ecomm|head of acquisition|director.{0,5}market|director.{0,5}growth|director.{0,5}digital|director.{0,5}performance|director.{0,5}ecomm|director.{0,5}media|director.{0,5}demand|managing director|co.?founder|founder|\bCEO\b|\bowner\b|\bpresident\b|agency owner|demand gen|paid media|paid search|ecommerce|\bdtc\b|\bd2c\b|social ads|\bsem\b|\bcro\b|pmax|performance max', re.IGNORECASE)

t2_re = re.compile(r'market.*manager|growth.*manager|digital.*manager|performance.*manager|ecomm.*manager|brand.*manager|campaign.*manager|media buyer|ppc.*manager|sem.*manager|senior market|senior growth|senior digital|market.*lead|growth.*lead|content director|head of content|revops|revenue operations|founding market|strategy director', re.IGNORECASE)

t3_re = re.compile(r'market|growth|brand|content|\bseo\b|social media|digital|demand|acquisition|retention|lifecycle|product market|go.to.market|\bgtm\b|paid media|\bppc\b|performance|advertising|\bads\b|ad ops|media plan', re.IGNORECASE)

wl_re = re.compile(r'fractional cmo|fractional chief|fractional market|fractional growth|freelance market|freelance digital|freelance growth|freelance paid|freelance seo|freelance content|freelance ppc|independent consultant|solo consultant|marketing consultant|growth consultant|digital consultant|media consultant', re.IGNORECASE)

na_codes = {'US', 'CA'}

def classify(profile):
    """Returns (tier, geo, filter_reason) or None if junk"""
    t = profile['title']
    h = profile['headline']
    combined = t + ' ' + h

    # Filter on title primarily, headline as backup
    if junk_re.search(combined):
        return None, None, 'junk'
    if dev_re.search(t):  # Only check title for dev, not headline
        return None, None, 'dev'
    if nonmktg_re.search(t):  # Only check title
        return None, None, 'non_mktg'

    # Geo
    cc = profile['country_code']
    loc = profile['location']
    geo = 'NA' if (cc in na_codes or 'United States' in loc or 'Canada' in loc) else 'INT'

    # Tier on combined title + headline
    if wl_re.search(combined):
        tier = 'WL'
    elif t1_re.search(combined):
        tier = 'T1'
    elif t2_re.search(combined):
        tier = 'T2'
    elif t3_re.search(combined):
        tier = 'T3'
    else:
        tier = 'REMOVE'

    return tier, geo, None

def process_campaign(urls, output_dir, name):
    os.makedirs(output_dir, exist_ok=True)

    results = []
    stats = {'junk': 0, 'dev': 0, 'non_mktg': 0}

    for url in urls:
        p = profiles[url]
        tier, geo, reason = classify(p)
        if reason:
            stats[reason] = stats.get(reason, 0) + 1
            continue

        p['tier'] = tier
        p['geo'] = geo
        results.append(p)

    print(f"\n{name}:")
    print(f"  Input: {len(urls)}")
    print(f"  Filtered out: junk={stats['junk']}, dev={stats['dev']}, non_mktg={stats['non_mktg']}")
    print(f"  Remaining: {len(results)}")

    # Write CSVs
    fields = ['first_name', 'last_name', 'title', 'company', 'company_size', 'headline',
              'linkedin_url', 'location', 'country_code', 'tier', 'geo',
              'open_to_work', 'premium', 'hiring', 'top_skills', 'all_companies']

    totals = {}
    for tier in ['T1', 'T2', 'T3', 'WL', 'REMOVE']:
        for geo in ['NA', 'INT']:
            sub = [r for r in results if r['tier'] == tier and r['geo'] == geo]
            if sub:
                fname = f'{geo}-{tier}.csv'
                path = os.path.join(output_dir, fname)
                with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                    w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
                    w.writeheader()
                    w.writerows(sub)
                totals[f'{geo}-{tier}'] = len(sub)
                print(f"  {fname}: {len(sub)}")

    # Full list
    with open(os.path.join(output_dir, 'ALL.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(results)

    return totals

# ============================================================
# STEP 4: Process each campaign
# ============================================================
luna_totals = process_campaign(luna_urls, LUNA_DIR, "LUNA CHEN (Growth)")
daniel_totals = process_campaign(daniel_urls, DANIEL_DIR, "DANIEL PAUL (Team)")

# Summary
print("\n" + "=" * 50)
print("COMBINED NA SUMMARY")
print("=" * 50)
combined_na = {}
for tier in ['T1', 'T2', 'T3', 'WL', 'REMOVE']:
    key = f'NA-{tier}'
    luna_n = luna_totals.get(key, 0)
    daniel_n = daniel_totals.get(key, 0)
    combined_na[tier] = luna_n + daniel_n
    print(f"  {tier}: Luna={luna_n} + Daniel={daniel_n} = {luna_n + daniel_n}")

print(f"\n  TOTAL NA ACTIONABLE (T1+T2+T3+WL): {sum(combined_na[t] for t in ['T1','T2','T3','WL'])}")
print(f"  TOTAL NA T1 (call list): {combined_na['T1']}")
