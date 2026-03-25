import json, re, csv, os

INPUT = 'c:/Users/olive/Downloads/dataset_linkedin-post-comments_2026-03-24_00-33-37-176.json'
EXISTING_DIR = 'c:/Users/olive/OneDrive/Desktop/Sprites Work/Leads/wip/luna-chen-growth'
OUTPUT_DIR = 'c:/Users/olive/OneDrive/Desktop/Sprites Work/Leads/wip/daniel-paul-team'

with open(INPUT, 'r', encoding='utf-8') as f:
    data = json.load(f)

team_pattern = re.compile(r'\bteam\b', re.IGNORECASE)
team_leads = [d for d in data if team_pattern.search(str(d.get('commentary', '')))]
print(f'Total comments: {len(data)} | Team matches: {len(team_leads)}')

# Extract unique leads
leads = []
seen_urls = set()
for d in team_leads:
    actor = d.get('actor', {})
    url = actor.get('linkedinUrl', '')
    if not url or url in seen_urls:
        continue
    seen_urls.add(url)
    loc = actor.get('location', {})
    parsed = loc.get('parsed', {})
    leads.append({
        'first_name': actor.get('firstName', ''),
        'last_name': actor.get('lastName', ''),
        'full_name': actor.get('name', ''),
        'headline': actor.get('headline', ''),
        'position': actor.get('position', ''),
        'linkedin_url': url,
        'location_text': loc.get('linkedinText', ''),
        'country': parsed.get('country', ''),
        'country_code': parsed.get('countryCode', ''),
        'comment': str(d.get('commentary', ''))[:200],
        'open_to_work': actor.get('openToWork', False),
        'premium': actor.get('premium', False),
        'top_skills': actor.get('topSkills', ''),
    })
print(f'Unique leads: {len(leads)}')

# Dedup against luna-chen-growth
existing_urls = set()
if os.path.exists(EXISTING_DIR):
    for fname in os.listdir(EXISTING_DIR):
        if fname.endswith('.csv'):
            with open(os.path.join(EXISTING_DIR, fname), 'r', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    u = row.get('linkedin_url', '').rstrip('/').lower()
                    if u:
                        existing_urls.add(u)

deduped = [l for l in leads if l['linkedin_url'].rstrip('/').lower() not in existing_urls]
print(f'Dupes with luna-chen: {len(leads) - len(deduped)} | After dedup: {len(deduped)}')

# Filters
junk_re = re.compile(r'student|intern|seeking opportunities|open to work|job seeker|looking for.*role|fresher|trainee|apprentice', re.IGNORECASE)
dev_re = re.compile(r'full.?stack|front.?end|back.?end|software eng|software dev|web dev|mobile dev|devops|data eng|machine learning eng|ml eng|ai eng|blockchain|cloud eng|site reliability|sre |java dev|python dev|\.net dev|react dev|node dev|ios dev|android dev|qa eng|test eng|embedded|firmware|hardware eng|network eng|security eng|infra eng|platform eng|systems eng', re.IGNORECASE)
nonmktg_re = re.compile(r'recruiter|talent acq|human resource|\bhr\b|lawyer|attorney|legal|teacher|professor|therapist|nurse|doctor|physician|dentist|pharmacist|accountant|auditor|bookkeeper|real estate agent|realtor|civil eng|mechanical eng|electrical eng|chemical eng', re.IGNORECASE)

clean, filtered_out = [], []
rj, rd, rn = 0, 0, 0
for l in deduped:
    h = (l['headline'] or '') + ' ' + (l['position'] or '')
    if junk_re.search(h):
        rj += 1
        continue
    if dev_re.search(h):
        rd += 1
        l['filter_reason'] = 'dev'
        filtered_out.append(l)
        continue
    if nonmktg_re.search(h):
        rn += 1
        l['filter_reason'] = 'non_mktg'
        filtered_out.append(l)
        continue
    clean.append(l)

print(f'Removed: junk={rj} dev={rd} non_mktg={rn} | Clean: {len(clean)}')

# Tier
na_codes = {'US', 'CA'}
t1_re = re.compile(r'CMO|chief market|chief growth|chief revenue|chief digital|VP.{0,5}market|VP.{0,5}growth|VP.{0,5}digital|VP.{0,5}demand|VP.{0,5}performance|head of market|head of growth|head of digital|head of demand|head of performance|head of paid|head of media|head of ecomm|head of acquisition|director.{0,5}market|director.{0,5}growth|director.{0,5}digital|director.{0,5}performance|director.{0,5}ecomm|director.{0,5}media|director.{0,5}demand|managing director|co.?founder|founder|CEO|owner|president|partner|principal|agency owner|demand gen|paid media|paid search|ecommerce|dtc|d2c|social ads|\bsem\b|\bcro\b|pmax|performance max', re.IGNORECASE)
t2_re = re.compile(r'market.*manager|growth.*manager|digital.*manager|performance.*manager|ecomm.*manager|brand.*manager|campaign.*manager|media buyer|ppc.*manager|sem.*manager|senior market|senior growth|senior digital|market.*lead|growth.*lead|content director|head of content|revops|revenue operations|founding market|strategy director', re.IGNORECASE)
t3_re = re.compile(r'market|growth|brand|content|seo|social media|digital|demand|acquisition|retention|lifecycle|product market|go.to.market|gtm|paid media|ppc|performance|advertising|ads |ad ops|media plan', re.IGNORECASE)
wl_re = re.compile(r'fractional cmo|fractional chief|fractional market|fractional growth|freelance market|freelance digital|freelance growth|freelance paid|freelance seo|freelance content|freelance ppc|independent consultant|solo consultant|marketing consultant|growth consultant|digital consultant|media consultant', re.IGNORECASE)

na, intl = [], []
for l in clean:
    h = (l['headline'] or '') + ' ' + (l['position'] or '')
    if wl_re.search(h):
        l['tier'] = 'WL'
    elif t1_re.search(h):
        l['tier'] = 'T1'
    elif t2_re.search(h):
        l['tier'] = 'T2'
    elif t3_re.search(h):
        l['tier'] = 'T3'
    else:
        l['tier'] = 'REMOVE'

    if l['country_code'] in na_codes or 'United States' in l['location_text'] or 'Canada' in l['location_text']:
        na.append(l)
    else:
        intl.append(l)

na_t = {t: len([x for x in na if x['tier'] == t]) for t in ['T1', 'T2', 'T3', 'WL', 'REMOVE']}
int_t = {t: len([x for x in intl if x['tier'] == t]) for t in ['T1', 'T2', 'T3', 'WL', 'REMOVE']}
print(f'\nNA ({len(na)}): {na_t}')
print(f'INT ({len(intl)}): {int_t}')

# Save
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(os.path.join(OUTPUT_DIR, 'raw.json'), 'w', encoding='utf-8') as f:
    json.dump(clean, f, indent=2, ensure_ascii=False)

fields = ['first_name', 'last_name', 'full_name', 'headline', 'position', 'linkedin_url', 'location_text', 'country', 'country_code', 'comment', 'tier', 'open_to_work', 'premium', 'top_skills']

for tier in ['T1', 'T2', 'T3', 'WL']:
    for geo, grp in [('NA', na), ('INT', intl)]:
        sub = [x for x in grp if x['tier'] == tier]
        if sub:
            path = os.path.join(OUTPUT_DIR, f'{geo}-{tier}.csv')
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
                w.writeheader()
                w.writerows(sub)
            print(f'{geo}-{tier}: {len(sub)}')

# REMOVE manual review
rem = [x for x in clean if x['tier'] == 'REMOVE']
with open(os.path.join(OUTPUT_DIR, 'REMOVE-MANUAL-REVIEW.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
    w.writeheader()
    w.writerows(rem)
print(f'REMOVE-MANUAL-REVIEW: {len(rem)}')

# Email worthy
ew = rem + filtered_out
na_ew = [x for x in ew if x.get('country_code', '') in na_codes or 'United States' in x.get('location_text', '') or 'Canada' in x.get('location_text', '')]
int_ew = [x for x in ew if x not in na_ew]
ew_fields = fields + ['filter_reason']
for name, grp in [('NA-EMAIL-WORTHY.csv', na_ew), ('INT-EMAIL-WORTHY.csv', int_ew)]:
    if grp:
        path = os.path.join(OUTPUT_DIR, name)
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=ew_fields, extrasaction='ignore')
            w.writeheader()
            w.writerows(grp)
        print(f'{name}: {len(grp)}')

# Non-marketing separate
nonmktg_list = [x for x in filtered_out if x.get('filter_reason') == 'non_mktg']
with open(os.path.join(OUTPUT_DIR, 'FILTERED-NON-MARKETING.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=ew_fields, extrasaction='ignore')
    w.writeheader()
    w.writerows(nonmktg_list)
print(f'FILTERED-NON-MARKETING: {len(nonmktg_list)}')

print(f'\n=== TOP NA T1 ===')
na_t1 = [x for x in na if x['tier'] == 'T1']
for l in na_t1[:15]:
    print(f"  {l['full_name']} | {l['position'][:65]} | {l['location_text']}")

print(f'\nAll files saved to: {OUTPUT_DIR}')
