import json, csv, os, re

# Load profiles
with open('C:/Users/olive/OneDrive/Desktop/Sprites Work/Leads/wip/pulse-post-scrape/pulse-profiles-raw.json', 'r', encoding='utf-8') as f:
    profiles = json.load(f)

print(f'Loaded {len(profiles)} profiles')

# Load existing lead URLs for dedup
existing_urls = set()
active_dir = 'C:/Users/olive/OneDrive/Desktop/Sprites Work/Leads/active/claude-80hrs-phone-enrichment'
for fn in os.listdir(active_dir):
    if fn.endswith('.csv'):
        with open(os.path.join(active_dir, fn), 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = (row.get('linkedin_url') or '').lower().rstrip('/')
                url = re.sub(r'^https?://(www\.)?', '', url)
                if url:
                    existing_urls.add(url)
print(f'Existing URLs for dedup: {len(existing_urls)}')

# GEO SETS
NA_CODES = {'US','CA'}
ICP_INTL_CODES = {'GB','AU','NZ','IE','DE','NL','FR','ES','IT','SE','NO','DK','FI','BE','AT','CH','PT','PL','CZ','RO','HU','HR','BG','GR','LT','LV','EE','SK','SI','LU','MT','CY','IS'}
NON_ICP_CODES = {'IN','PK','BD','LK','NP','TR','PH','ID','MY','TH','VN','MM','KH','LA','NG','KE','GH','ZA','EG','MA','TN','DZ','SA','AE','QA','KW','BH','OM','JO','LB','IQ','IR','AF','UZ','KZ','TM','KG','TJ','CN','HK','TW','KR','JP','SG','BR','AR','CL','CO','PE','VE','EC','UY','PY','BO','MX','CR','PA','GT','HN','SV','NI','DO','CU','JM','TT','PR'}

non_icp_kw = ['india','pakistan','bangladesh','sri lanka','nepal','turkey','philippines','indonesia','malaysia','thailand','vietnam','myanmar','cambodia','nigeria','kenya','ghana','south africa','egypt','morocco','tunisia','algeria','saudi arabia','dubai','uae','united arab','qatar','kuwait','bahrain','oman','jordan','lebanon','iraq','iran','afghanistan','china','hong kong','taiwan','singapore','brazil','argentina','chile','colombia','peru','venezuela','ecuador','mexico','costa rica','panama','guatemala','honduras']

def geo_bucket(profile):
    loc = profile.get('location', {}) or {}
    cc = (loc.get('countryCode') or '').upper()
    parsed = loc.get('parsed', {}) or {}
    cc2 = (parsed.get('countryCode') or '').upper()
    code = cc or cc2

    if code in NA_CODES: return 'na'
    if code in NON_ICP_CODES: return 'non-icp-geo'
    if code in ICP_INTL_CODES: return 'intl'

    loc_text = (loc.get('linkedinText') or '').lower()
    country_text = (parsed.get('country') or '').lower()
    full = loc_text + ' ' + country_text

    us_patterns = ['united states','usa',' us ','california','new york','texas','florida','illinois','washington','massachusetts','georgia','colorado','arizona','oregon','ohio','michigan','pennsylvania','virginia','north carolina','san francisco','los angeles','chicago','boston','seattle','denver','atlanta','austin','dallas','houston','miami','portland','minneapolis','nashville','philadelphia','phoenix','tampa','detroit','pittsburgh','st. louis','san diego','las vegas','salt lake','indianapolis','kansas city','charlotte','raleigh']
    ca_patterns = ['canada','toronto','vancouver','montreal','calgary','ottawa','edmonton','winnipeg']

    for p in us_patterns:
        if p in full: return 'na'
    for p in ca_patterns:
        if p in full: return 'na'
    for kw in non_icp_kw:
        if kw in full: return 'non-icp-geo'

    uk_au = ['united kingdom','england','london','manchester','birmingham','scotland','wales','australia','sydney','melbourne','brisbane','perth','new zealand','auckland','wellington','ireland','dublin']
    eu = ['germany','berlin','munich','hamburg','netherlands','amsterdam','rotterdam','france','paris','spain','madrid','barcelona','italy','milan','rome','sweden','stockholm','norway','oslo','denmark','copenhagen','finland','helsinki','belgium','brussels','austria','vienna','switzerland','zurich','geneva','portugal','lisbon','poland','warsaw','czech','prague']
    for p in uk_au + eu:
        if p in full: return 'intl'

    if not full.strip(): return 'no-geo'
    return 'unknown-geo'

# ICP TIER
def classify_icp(title, headline):
    t = (title or '').lower()
    h = (headline or '').lower()
    both = t + ' ' + h

    wl_kw = ['fractional cmo','fractional chief','fractional marketing','fractional growth','freelance market','freelance digital','freelance growth','freelance paid','freelance seo','freelance content','freelance ppc','independent consultant','solo consultant','marketing consultant','growth consultant','digital consultant','media consultant']
    for kw in wl_kw:
        if kw in both: return 'WHITELABEL'
    if re.search(r'i help (companies|brands|businesses|startups)', h):
        return 'WHITELABEL'

    t1_titles = ['cmo','chief marketing','chief growth','chief revenue','chief digital','chief executive','chief operating','vp of marketing','vp of growth','vp of digital','vp of demand','vp of performance','vp of paid','vp marketing','vp growth','vp digital','vp demand','vp performance','vp paid','head of marketing','head of growth','head of digital','head of performance','head of paid','head of demand','head of acquisition','head of media','head of ecommerce','head of e-commerce','head of product marketing','director of marketing','director of growth','director of digital','director of performance','director of paid','director of demand','director of product marketing','director of ecommerce','director of e-commerce','director of media','managing director','general manager','co-founder','cofounder','founder','ceo','owner','president','partner','managing partner','principal','agency owner','agency founder']
    for kw in t1_titles:
        if kw in t or kw in h: return 'TIER1'

    t2_titles = ['marketing manager','growth manager','digital manager','performance manager','ecommerce manager','e-commerce manager','brand manager','campaign manager','media buyer','ppc manager','sem manager','senior marketing','senior growth','senior digital','marketing lead','growth lead','digital lead','growth director','marketing director','revops','revenue operations','founding marketer','strategy director','strategy lead','content director','head of content','content lead']
    t2_signals = ['agency','ecommerce','e-commerce','shopify','amazon fba','dtc','d2c','google ads','meta ads','facebook ads','paid media','ppc','media buying','performance market']
    for kw in t2_titles:
        if kw in t: return 'TIER2'
    for kw in t2_signals:
        if kw in h: return 'TIER2'

    t3_kw = ['marketing','growth','brand','content','seo','social media','digital','demand','acquisition','retention','lifecycle','product marketing','go-to-market','gtm']
    for kw in t3_kw:
        if kw in both: return 'TIER3'

    return 'REMOVE'

# PROCESS
results = []
stats = {'total': 0, 'dedup': 0, 'non_icp_geo': 0, 'remove_icp': 0}
geo_counts = {}
tier_counts = {}

for p in profiles:
    stats['total'] += 1

    li_url = (p.get('linkedinUrl') or '').lower().rstrip('/')
    li_norm = re.sub(r'^https?://(www\.)?', '', li_url)

    if li_norm in existing_urls:
        stats['dedup'] += 1
        continue

    geo = geo_bucket(p)
    geo_counts[geo] = geo_counts.get(geo, 0) + 1

    if geo == 'non-icp-geo':
        stats['non_icp_geo'] += 1
        continue

    # Extract title/company from currentPosition or experience
    title = ''
    company = ''
    company_url = ''
    cp = p.get('currentPosition', [])
    if cp and isinstance(cp, list) and len(cp) > 0:
        title = cp[0].get('position') or cp[0].get('title') or ''
        company = cp[0].get('companyName') or ''
        company_url = cp[0].get('companyLinkedinUrl') or ''
    elif p.get('experience') and isinstance(p['experience'], list) and len(p['experience']) > 0:
        exp = p['experience'][0]
        title = exp.get('position') or exp.get('title') or ''
        company = exp.get('companyName') or ''
        company_url = exp.get('companyLinkedinUrl') or ''

    headline = p.get('headline') or ''

    tier = classify_icp(title, headline)
    tier_counts[tier] = tier_counts.get(tier, 0) + 1

    if tier == 'REMOVE':
        stats['remove_icp'] += 1
        continue

    loc = p.get('location', {}) or {}
    loc_text = loc.get('linkedinText') or ''

    results.append({
        'first_name': p.get('firstName') or '',
        'last_name': p.get('lastName') or '',
        'full_name': ((p.get('firstName') or '') + ' ' + (p.get('lastName') or '')).strip(),
        'title': title,
        'headline': headline,
        'company': company,
        'company_linkedin_url': company_url,
        'linkedin_url': p.get('linkedinUrl') or '',
        'location': loc_text,
        'icp_tier': tier,
        'geo_bucket': geo,
        'source': 'pulse-post-carlos'
    })

print(f'Total profiles: {stats["total"]}')
print(f'Deduped (already in 80hrs lists): {stats["dedup"]}')
print(f'Non-ICP geo removed: {stats["non_icp_geo"]}')
print(f'Non-marketing removed: {stats["remove_icp"]}')
print(f'Survivors: {len(results)}')
print()
print('Geo breakdown:', dict(sorted(geo_counts.items())))
print('Tier breakdown:', dict(sorted(tier_counts.items())))

# Split
na = [r for r in results if r['geo_bucket'] == 'na']
intl = [r for r in results if r['geo_bucket'] == 'intl']
wl = [r for r in results if r['icp_tier'] == 'WHITELABEL']
no_geo = [r for r in results if r['geo_bucket'] in ('no-geo','unknown-geo')]

na = [r for r in na if r['icp_tier'] != 'WHITELABEL']
intl = [r for r in intl if r['icp_tier'] != 'WHITELABEL']

na_t1 = [r for r in na if r['icp_tier']=='TIER1']
na_t2 = [r for r in na if r['icp_tier']=='TIER2']
na_t3 = [r for r in na if r['icp_tier']=='TIER3']
intl_t1 = [r for r in intl if r['icp_tier']=='TIER1']
intl_t2 = [r for r in intl if r['icp_tier']=='TIER2']
intl_t3 = [r for r in intl if r['icp_tier']=='TIER3']

print(f'NA: T1={len(na_t1)}, T2={len(na_t2)}, T3={len(na_t3)}')
print(f'INTL: T1={len(intl_t1)}, T2={len(intl_t2)}, T3={len(intl_t3)}')
print(f'WL: {len(wl)}, No-geo: {len(no_geo)}')

# Write CSVs
out_dir = 'C:/Users/olive/OneDrive/Desktop/Sprites Work/Leads/active/pulse-post-carlos'
os.makedirs(out_dir, exist_ok=True)

headers = ['first_name','last_name','full_name','title','headline','company','company_linkedin_url','linkedin_url','location','icp_tier','source']

def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)

for name, rows in [
    (f'01-NA-USA-CANADA-{len(na_t1)}-leads-TIER1', na_t1),
    (f'01-NA-USA-CANADA-{len(na_t2)}-leads-TIER2', na_t2),
    (f'01-NA-USA-CANADA-{len(na_t3)}-leads-TIER3', na_t3),
    (f'02-INTL-EU-AU-OTHER-{len(intl_t1)}-leads-TIER1', intl_t1),
    (f'02-INTL-EU-AU-OTHER-{len(intl_t2)}-leads-TIER2', intl_t2),
    (f'02-INTL-EU-AU-OTHER-{len(intl_t3)}-leads-TIER3', intl_t3),
    (f'03-WHITELABEL-{len(wl)}-leads', wl),
]:
    if rows:
        path = os.path.join(out_dir, name + '.csv')
        write_csv(path, rows)
        print(f'Wrote: {name}.csv')

print()
print('Output directory:', out_dir)
for fn in sorted(os.listdir(out_dir)):
    print(f'  {fn}')
