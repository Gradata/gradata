"""
STRICT refilter. T1 = people who ACTUALLY touch marketing/ads.
Founders/CEOs split into separate bucket for manual review.
"""
import json, re, csv, os

ENRICHED = 'c:/Users/olive/Downloads/dataset_linkedin-profile-scraper_2026-03-24_02-43-11-653.json'
LUNA_RAW = 'c:/Users/olive/Downloads/dataset_linkedin-post-comments_2026-03-24_00-56-50-577.json'
DANIEL_RAW = 'c:/Users/olive/Downloads/dataset_linkedin-post-comments_2026-03-24_00-33-37-176.json'
LUNA_DIR = 'c:/Users/olive/OneDrive/Desktop/Sprites Work/Leads/wip/luna-chen-growth-enriched'
DANIEL_DIR = 'c:/Users/olive/OneDrive/Desktop/Sprites Work/Leads/wip/daniel-paul-team-enriched'

# Load enriched
print("Loading...")
with open(ENRICHED, 'r', encoding='utf-8') as f:
    enriched_raw = json.load(f)

profiles = {}
for e in enriched_raw:
    url = (e.get('linkedinUrl') or '').rstrip('/').lower()
    if not url or '/company/' in url:
        continue
    cp = e.get('currentPosition', [])
    title = ''
    company = ''
    if cp and isinstance(cp, list) and len(cp) > 0:
        company = cp[0].get('companyName', '') or ''
        title = cp[0].get('position', '') or ''
    if not title:
        title = e.get('headline', '') or ''
    headline = e.get('headline', '') or ''
    emp = e.get('employeeCountRange', {}) or {}
    emp_start = emp.get('start', 0) or 0
    emp_end = emp.get('end', 0) or 0
    loc = e.get('location', {}) or {}
    location_text = ''
    country_code = ''
    if isinstance(loc, dict):
        location_text = loc.get('linkedinText', '') or ''
        parsed = loc.get('parsed', {}) or {}
        country_code = parsed.get('countryCode', '') or ''

    profiles[url] = {
        'first_name': e.get('firstName', '') or '',
        'last_name': e.get('lastName', '') or '',
        'title': title,
        'company': company,
        'company_size': f"{emp_start}-{emp_end}" if emp_start else '',
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
    }

print(f"Loaded {len(profiles)} profiles")

# Map to campaigns
luna_urls = set()
daniel_urls = set()
with open(LUNA_RAW, 'r', encoding='utf-8') as f:
    for d in json.load(f):
        if re.search(r'\bgrowth\b|\bgrow\b|\bgrowing\b', str(d.get('commentary', '')), re.IGNORECASE):
            url = (d.get('actor', {}).get('linkedinUrl', '') or '').rstrip('/').lower()
            if url and url in profiles:
                luna_urls.add(url)
with open(DANIEL_RAW, 'r', encoding='utf-8') as f:
    for d in json.load(f):
        if re.search(r'\bteam\b', str(d.get('commentary', '')), re.IGNORECASE):
            url = (d.get('actor', {}).get('linkedinUrl', '') or '').rstrip('/').lower()
            if url and url in profiles:
                daniel_urls.add(url)

print(f"Luna: {len(luna_urls)} | Daniel: {len(daniel_urls)}")

# ============================================================
# STRICT CLASSIFICATION
# ============================================================

# Junk - filter out completely
junk_re = re.compile(r'\bstudent\b|\bintern\b|seeking opportunities|job seeker|looking for.*role|\bfresher\b|\btrainee\b|\bapprentice\b', re.IGNORECASE)
dev_re = re.compile(r'full.?stack dev|front.?end dev|back.?end dev|software eng|software dev|\bweb dev|mobile dev|\bdevops\b|data eng|machine learning eng|\bml eng|blockchain dev|cloud eng|site reliability|java dev|python dev|\.net dev|react dev|node dev|ios dev|android dev|\bqa eng|test eng|\bembedded\b|firmware|hardware eng|network eng|security eng|infra eng|platform eng|systems eng', re.IGNORECASE)
nonmktg_re = re.compile(r'\brecruiter\b|talent acq|human resource|\bhr manager\b|\bhr director\b|\blawyer\b|\battorney\b|\blegal counsel\b|\bteacher\b|\bprofessor\b|\btherapist\b|\bnurse\b|\bdoctor\b|\bphysician\b|\bdentist\b|\bpharmacist\b|\baccountant\b|\bauditor\b|\bbookkeeper\b|real estate agent|\brealtor\b|civil eng|mechanical eng|electrical eng|chemical eng', re.IGNORECASE)

# T1 CALL LIST: People whose JOB is marketing/ads/growth
# These people wake up and open ad platforms
t1_marketing_leader = re.compile(r'VP.{0,5}market|head of market|director.{0,5}market|\bCMO\b|chief market', re.IGNORECASE)
t1_growth_leader = re.compile(r'VP.{0,5}growth|head of growth|director.{0,5}growth|head of demand|director.{0,5}demand|VP.{0,5}demand|VP.{0,5}performance|head of performance|director.{0,5}performance|VP.{0,5}digital market|head of digital market|director.{0,5}digital market', re.IGNORECASE)
t1_paid_media = re.compile(r'paid media|paid search|paid social|\bppc\b|media buyer|performance market|head of paid|director.{0,5}paid|\bsem manager\b|paid acquisition', re.IGNORECASE)
t1_ecom_dtc = re.compile(r'VP.{0,5}ecomm|head of ecomm|director.{0,5}ecomm|VP.{0,5}digital.{0,5}ecomm|\bdtc\b.{0,5}director|\bd2c\b.{0,5}director|ecommerce director|ecommerce manager', re.IGNORECASE)
t1_agency = re.compile(r'agency owner|agency founder|agency principal|agency partner|managing director.{0,10}agency', re.IGNORECASE)

# T2 PRIORITY EMAIL: Marketing managers, growth managers - they use the tools but may not buy
t2_re = re.compile(r'market.*manager|growth.*manager|digital.*manager|performance.*manager|ecomm.*manager|brand.*manager|campaign.*manager|media buyer|senior market|senior growth|senior digital|market.*lead|growth.*lead|content director|head of content|revops|revenue operations|founding market|strategy director|demand gen.*manager|acquisition.*manager', re.IGNORECASE)

# T3 EMAIL: Anyone with marketing keywords in title
t3_re = re.compile(r'market|growth|brand|content|\bseo\b|social media|digital market|demand|acquisition|retention|lifecycle|product market|go.to.market|\bgtm\b|paid media|\bppc\b|performance market|advertising|\bads\b|ad ops|media plan', re.IGNORECASE)

# WL: Fractional/freelance marketing
wl_re = re.compile(r'fractional cmo|fractional chief market|fractional market|fractional growth|freelance market|freelance digital|freelance growth|freelance paid|freelance seo|freelance content|freelance ppc|marketing consultant|growth consultant|digital consultant', re.IGNORECASE)

# FOUNDER bucket: CEO/Founder/Owner at a company that MIGHT run ads
# These get separated, not auto-T1
founder_re = re.compile(r'\bCEO\b|\bfounder\b|co.?founder|\bowner\b|\bpresident\b', re.IGNORECASE)

# Marketing signal in headline (for founders - if they mention marketing, they might be ICP)
mktg_signal = re.compile(r'market|growth|demand|paid|ads|digital|seo|media buy|ecomm|dtc|d2c|agency|performance market|social ads|\bppc\b|\bsem\b|ad tech|advertising', re.IGNORECASE)

# Non-ICP verticals for founders (even if they're CEO, these don't buy ad tools)
non_icp_verticals = re.compile(r'cybersecurity|blockchain|crypto|fintech|healthcare|biotech|pharma|medical|legal tech|law firm|construction|real estate|insurance|banking|energy|oil|gas|mining|logistics|supply chain|manufacturing|defense|military|government|nonprofit|non-profit|education|university|church|ministry', re.IGNORECASE)

na_codes = {'US', 'CA'}

def classify_strict(p):
    t = p['title']
    h = p['headline']
    combined = t + ' ' + h
    company = p['company']

    # Geo (compute early so all paths have it)
    cc = p['country_code']
    loc = p['location']
    geo = 'NA' if (cc in na_codes or 'United States' in loc or 'Canada' in loc) else 'INT'

    # Filter — still keep them, just tag the reason
    if junk_re.search(combined):
        return 'JUNK', geo, None
    if dev_re.search(t):
        return 'DEV', geo, None
    if nonmktg_re.search(t):
        return 'NON-MKTG', geo, None

    # WL first
    if wl_re.search(combined):
        return 'WL', geo, None

    # T1 CALL: Must have explicit marketing/ads/growth TITLE
    if t1_marketing_leader.search(combined):
        return 'T1-CALL', geo, None
    if t1_growth_leader.search(combined):
        return 'T1-CALL', geo, None
    if t1_paid_media.search(combined):
        return 'T1-CALL', geo, None
    if t1_ecom_dtc.search(combined):
        return 'T1-CALL', geo, None
    if t1_agency.search(combined):
        return 'T1-CALL', geo, None

    # T2 marketing managers
    if t2_re.search(combined):
        return 'T2', geo, None

    # FOUNDER bucket: CEO/Founder with marketing signal → T1-FOUNDER-ICP
    # CEO/Founder without marketing signal → T3-FOUNDER (email only)
    if founder_re.search(t):
        if mktg_signal.search(combined) and not non_icp_verticals.search(combined + ' ' + company):
            return 'T1-FOUNDER-ICP', geo, None
        elif non_icp_verticals.search(combined + ' ' + company):
            return 'REMOVE', geo, None
        else:
            return 'T3-FOUNDER', geo, None

    # CRO/COO/Ops - not marketing buyers
    ops_re = re.compile(r'\bCOO\b|\bCRO\b|chief of staff|chief revenue|head of ops|operations director|managing director|\bCTO\b|chief technology|chief product|chief financial|\bCFO\b', re.IGNORECASE)
    if ops_re.search(t):
        return 'T3-EXEC', geo, None

    # T3: marketing keywords in title
    if t3_re.search(combined):
        return 'T3', geo, None

    # Everything else
    return 'REMOVE', geo, None

def process_campaign(urls, output_dir, name):
    os.makedirs(output_dir, exist_ok=True)

    results = []

    for url in urls:
        p = profiles[url]
        tier, geo, reason = classify_strict(p)
        if geo is None:
            cc = p['country_code']
            loc = p['location']
            geo = 'NA' if (cc in na_codes or 'United States' in loc or 'Canada' in loc) else 'INT'
        p['tier'] = tier
        p['geo'] = geo
        results.append(p)

    print(f"\n{name}:")
    print(f"  Input: {len(urls)}")
    print(f"  Output: {len(results)} (every lead accounted for)")

    fields = ['first_name', 'last_name', 'title', 'company', 'company_size', 'headline',
              'linkedin_url', 'location', 'country_code', 'tier', 'geo',
              'open_to_work', 'premium', 'hiring', 'top_skills']

    # Write by tier + geo
    all_tiers = ['T1-CALL', 'T1-FOUNDER-ICP', 'T2', 'T3', 'T3-FOUNDER', 'T3-EXEC', 'WL', 'REMOVE', 'JUNK', 'DEV', 'NON-MKTG']
    total_written = 0
    for tier in all_tiers:
        for geo in ['NA', 'INT']:
            sub = [r for r in results if r['tier'] == tier and r['geo'] == geo]
            if sub:
                fname = f'{geo}-{tier}.csv'
                path = os.path.join(output_dir, fname)
                with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                    w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
                    w.writeheader()
                    w.writerows(sub)
                total_written += len(sub)
                print(f"  {fname}: {len(sub)}")

    print(f"\n  TOTAL WRITTEN: {total_written} (should match input: {len(urls)})")
    if total_written != len(results):
        print(f"  WARNING: mismatch! results={len(results)}")

    # Summary
    na_results = [r for r in results if r['geo'] == 'NA']
    int_results = [r for r in results if r['geo'] == 'INT']
    print(f"\n  NA SUMMARY ({len(na_results)}):")
    for tier in all_tiers:
        count = len([r for r in na_results if r['tier'] == tier])
        if count:
            print(f"    {tier}: {count}")
    print(f"  INT SUMMARY ({len(int_results)}):")
    for tier in all_tiers:
        count = len([r for r in int_results if r['tier'] == tier])
        if count:
            print(f"    {tier}: {count}")

process_campaign(luna_urls, LUNA_DIR, "LUNA CHEN (Growth)")
process_campaign(daniel_urls, DANIEL_DIR, "DANIEL PAUL (Team)")

# Combined NA summary
print("\n" + "=" * 50)
print("COMBINED NA — STRICT TIERS")
print("=" * 50)
grand_total = [0]
for tier in ['T1-CALL', 'T1-FOUNDER-ICP', 'T2', 'T3', 'T3-FOUNDER', 'T3-EXEC', 'WL', 'REMOVE', 'JUNK', 'DEV', 'NON-MKTG']:
    luna_path = f'{LUNA_DIR}/NA-{tier}.csv'
    daniel_path = f'{DANIEL_DIR}/NA-{tier}.csv'
    luna_n = 0
    daniel_n = 0
    if os.path.exists(luna_path):
        with open(luna_path, 'r', encoding='utf-8-sig') as f:
            luna_n = sum(1 for _ in csv.DictReader(f))
    if os.path.exists(daniel_path):
        with open(daniel_path, 'r', encoding='utf-8-sig') as f:
            daniel_n = sum(1 for _ in csv.DictReader(f))
    if luna_n or daniel_n:
        label = {
            'T1-CALL': 'CALL LIST (actually touch ads)',
            'T1-FOUNDER-ICP': 'FOUNDERS w/ marketing signal (call)',
            'T2': 'PRIORITY EMAIL (marketing managers)',
            'T3': 'EMAIL (marketing keywords)',
            'T3-FOUNDER': 'FOUNDERS no mktg signal (email only)',
            'T3-EXEC': 'EXECS CRO/COO/etc (email only)',
            'WL': 'WHITE-LABEL (fractional/freelance)',
            'REMOVE': 'NO MATCH (email blast)',
            'JUNK': 'JUNK (students/seekers)',
            'DEV': 'DEV TITLES',
            'NON-MKTG': 'NON-MARKETING TITLES',
        }.get(tier, tier)
        total = luna_n + daniel_n
        print(f"  {tier}: Luna={luna_n} + Daniel={daniel_n} = {total}  <- {label}")
        grand_total[0] += total
