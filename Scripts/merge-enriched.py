"""
Merge Apify enriched profiles back to campaign-separated, tiered CSVs.
Splits by Luna Chen (Growth) vs Daniel Paul (Team) source.
"""
import json, re, csv, os

ENRICHED = 'c:/Users/olive/Downloads/dataset_linkedin-profile-scraper_2026-03-24_02-43-11-653.json'
LUNA_RAW = 'c:/Users/olive/Downloads/dataset_linkedin-post-comments_2026-03-24_00-56-50-577.json'
DANIEL_RAW = 'c:/Users/olive/Downloads/dataset_linkedin-post-comments_2026-03-24_00-33-37-176.json'
LUNA_DIR = 'c:/Users/olive/OneDrive/Desktop/Sprites Work/Leads/wip/luna-chen-growth-enriched'
DANIEL_DIR = 'c:/Users/olive/OneDrive/Desktop/Sprites Work/Leads/wip/daniel-paul-team-enriched'

# Load enriched profiles, index by LinkedIn URL
print("Loading enriched profiles...")
with open(ENRICHED, 'r', encoding='utf-8') as f:
    enriched = json.load(f)

enriched_map = {}
for e in enriched:
    url = (e.get('linkedinUrl') or '').rstrip('/').lower()
    if url:
        # Extract company from currentPosition
        company = ''
        company_size = ''
        title = ''
        cp = e.get('currentPosition', [])
        if cp and isinstance(cp, list) and len(cp) > 0:
            company = cp[0].get('companyName', '')
            title = cp[0].get('position', '') or e.get('headline', '')
        else:
            title = e.get('headline', '')

        emp = e.get('employeeCountRange', {})
        if emp:
            company_size = f"{emp.get('start', '')}-{emp.get('end', '')}"

        enriched_map[url] = {
            'enriched_title': title or '',
            'enriched_company': company or '',
            'enriched_company_size': company_size,
            'enriched_headline': e.get('headline', '') or '',
            'enriched_location': '',
            'enriched_country_code': '',
            'enriched_industry': '',
            'first_name': e.get('firstName', '') or '',
            'last_name': e.get('lastName', '') or '',
        }

        loc = e.get('location', {})
        if isinstance(loc, dict):
            enriched_map[url]['enriched_location'] = loc.get('linkedinText', '') or ''
            parsed = loc.get('parsed', {})
            if parsed:
                enriched_map[url]['enriched_country_code'] = parsed.get('countryCode', '') or ''

print(f"Indexed {len(enriched_map)} enriched profiles")

# Load raw comment files and map URLs to campaigns
print("Mapping URLs to campaigns...")
luna_urls = set()
daniel_urls = set()

with open(LUNA_RAW, 'r', encoding='utf-8') as f:
    luna_data = json.load(f)
growth_re = re.compile(r'\bgrowth\b|\bgrow\b|\bgrowing\b', re.IGNORECASE)
for d in luna_data:
    if growth_re.search(str(d.get('commentary', ''))):
        url = d.get('actor', {}).get('linkedinUrl', '')
        if url:
            luna_urls.add(url.rstrip('/').lower())

with open(DANIEL_RAW, 'r', encoding='utf-8') as f:
    daniel_data = json.load(f)
team_re = re.compile(r'\bteam\b', re.IGNORECASE)
for d in daniel_data:
    if team_re.search(str(d.get('commentary', ''))):
        url = d.get('actor', {}).get('linkedinUrl', '')
        if url:
            daniel_urls.add(url.rstrip('/').lower())

# Some URLs appear in both - they go in both campaigns
both = luna_urls & daniel_urls
print(f"Luna URLs: {len(luna_urls)} | Daniel URLs: {len(daniel_urls)} | In both: {len(both)}")

# Filters
junk_re = re.compile(r'student|intern|seeking opportunities|open to work|job seeker|looking for.*role|fresher|trainee|apprentice', re.IGNORECASE)
dev_re = re.compile(r'full.?stack|front.?end|back.?end|software eng|software dev|web dev|mobile dev|devops|data eng|machine learning eng|ml eng|ai eng|blockchain|cloud eng|site reliability|sre |java dev|python dev|\.net dev|react dev|node dev|ios dev|android dev|qa eng|test eng|embedded|firmware|hardware eng|network eng|security eng|infra eng|platform eng|systems eng', re.IGNORECASE)
nonmktg_re = re.compile(r'recruiter|talent acq|human resource|\bhr\b|lawyer|attorney|legal|teacher|professor|therapist|nurse|doctor|physician|dentist|pharmacist|accountant|auditor|bookkeeper|real estate agent|realtor|civil eng|mechanical eng|electrical eng|chemical eng', re.IGNORECASE)

# Tier patterns
t1_re = re.compile(r'CMO|chief market|chief growth|chief revenue|chief digital|VP.{0,5}market|VP.{0,5}growth|VP.{0,5}digital|VP.{0,5}demand|VP.{0,5}performance|head of market|head of growth|head of digital|head of demand|head of performance|head of paid|head of media|head of ecomm|head of acquisition|director.{0,5}market|director.{0,5}growth|director.{0,5}digital|director.{0,5}performance|director.{0,5}ecomm|director.{0,5}media|director.{0,5}demand|managing director|co.?founder|founder|CEO|owner|president|partner|principal|agency owner|demand gen|paid media|paid search|ecommerce|dtc|d2c|social ads|\bsem\b|\bcro\b|pmax|performance max', re.IGNORECASE)
t2_re = re.compile(r'market.*manager|growth.*manager|digital.*manager|performance.*manager|ecomm.*manager|brand.*manager|campaign.*manager|media buyer|ppc.*manager|sem.*manager|senior market|senior growth|senior digital|market.*lead|growth.*lead|content director|head of content|revops|revenue operations|founding market|strategy director', re.IGNORECASE)
t3_re = re.compile(r'market|growth|brand|content|seo|social media|digital|demand|acquisition|retention|lifecycle|product market|go.to.market|gtm|paid media|ppc|performance|advertising|ads |ad ops|media plan', re.IGNORECASE)
wl_re = re.compile(r'fractional cmo|fractional chief|fractional market|fractional growth|freelance market|freelance digital|freelance growth|freelance paid|freelance seo|freelance content|freelance ppc|independent consultant|solo consultant|marketing consultant|growth consultant|digital consultant|media consultant', re.IGNORECASE)

na_codes = {'US', 'CA'}

def process_campaign(campaign_urls, enriched_map, output_dir, campaign_name):
    os.makedirs(output_dir, exist_ok=True)

    leads = []
    matched = 0
    unmatched = 0

    for url in campaign_urls:
        e = enriched_map.get(url)
        if not e:
            unmatched += 1
            continue
        matched += 1

        title = e['enriched_title']
        headline = e['enriched_headline']
        h = title + ' ' + headline

        # Filter
        if junk_re.search(h):
            continue
        if dev_re.search(h):
            continue
        if nonmktg_re.search(h):
            continue

        # Tier
        if wl_re.search(h):
            tier = 'WL'
        elif t1_re.search(h):
            tier = 'T1'
        elif t2_re.search(h):
            tier = 'T2'
        elif t3_re.search(h):
            tier = 'T3'
        else:
            tier = 'REMOVE'

        # Geo
        cc = e['enriched_country_code']
        loc = e['enriched_location']
        if cc in na_codes or 'United States' in loc or 'Canada' in loc:
            geo = 'NA'
        else:
            geo = 'INT'

        leads.append({
            'first_name': e['first_name'],
            'last_name': e['last_name'],
            'title': title,
            'company': e['enriched_company'],
            'company_size': e['enriched_company_size'],
            'headline': headline,
            'linkedin_url': url,
            'location': loc,
            'country_code': cc,
            'tier': tier,
            'geo': geo,
        })

    print(f"\n{campaign_name}: matched={matched}, unmatched={unmatched}, after filter={len(leads)}")

    # Write CSVs
    fields = ['first_name', 'last_name', 'title', 'company', 'company_size', 'headline', 'linkedin_url', 'location', 'country_code', 'tier', 'geo']

    tiers = {}
    for tier in ['T1', 'T2', 'T3', 'WL', 'REMOVE']:
        for geo in ['NA', 'INT']:
            sub = [l for l in leads if l['tier'] == tier and l['geo'] == geo]
            if sub:
                fname = f'{geo}-{tier}.csv'
                path = os.path.join(output_dir, fname)
                with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                    w = csv.DictWriter(f, fieldnames=fields)
                    w.writeheader()
                    w.writerows(sub)
                key = f'{geo}-{tier}'
                tiers[key] = len(sub)
                print(f"  {fname}: {len(sub)}")

    # Also save full list
    path = os.path.join(output_dir, 'ALL.csv')
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(leads)

    return tiers

# Process each campaign
print("\n=== LUNA CHEN (Growth) ===")
luna_tiers = process_campaign(luna_urls, enriched_map, LUNA_DIR, "Luna Chen")

print("\n=== DANIEL PAUL (Team) ===")
daniel_tiers = process_campaign(daniel_urls, enriched_map, DANIEL_DIR, "Daniel Paul")

print("\n=== FINAL SUMMARY ===")
print(f"Luna Chen dir: {LUNA_DIR}")
print(f"Daniel Paul dir: {DANIEL_DIR}")
