import csv, sys, io, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = 'C:/Users/olive/OneDrive/Desktop/Sprites Work/Leads'
DONE = f'{BASE}/done/claude-code-80hrs-2026-03-16'
SRC = f'{BASE}/sources'

# --- URL NORMALIZATION (fixes http vs https mismatch) ---
def norm_url(u):
    u = (u or '').strip().lower().rstrip('/')
    u = re.sub(r'^https?://(www\.)?', '', u)
    return u

# --- GEO KEYWORDS ---
us_states = ['alabama','alaska','arizona','arkansas','california','colorado','connecticut','delaware','florida','georgia','hawaii','idaho','illinois','indiana','iowa','kansas','kentucky','louisiana','maine','maryland','massachusetts','michigan','minnesota','mississippi','missouri','montana','nebraska','nevada','new hampshire','new jersey','new mexico','new york','north carolina','north dakota','ohio','oklahoma','oregon','pennsylvania','rhode island','south carolina','south dakota','tennessee','texas','utah','vermont','virginia','washington','west virginia','wisconsin','wyoming','district of columbia']
us_metros = ['san francisco','los angeles','chicago','boston','seattle','denver','atlanta','austin','dallas','houston','phoenix','portland','nashville','miami','san diego','detroit','minneapolis','philadelphia','tampa','charlotte','raleigh','salt lake','sacramento','san jose','pittsburgh','cleveland','kansas city','st. louis','indianapolis','columbus','cincinnati','milwaukee','memphis','new orleans','oklahoma city','jacksonville','baltimore','greater new york','greater los angeles','greater chicago','greater boston','greater seattle','greater denver','greater atlanta','greater austin','greater dallas','greater houston','greater phoenix','san francisco bay','bay area','twin cities','research triangle','silicon valley','dmv area','dfw','socal','norcal','brooklyn','manhattan','queens','bronx','staten island','greater madison','greater burlington','greater minneapolis','greater st. paul','miami-fort lauderdale','dallas-fort worth','des moines','metropolitan fresno','lake oswego','encinitas','culver city','bend, oregon','cody, wyoming','arlington heights','knoxville','reading, pennsylvania','napa, california','carlsbad, california','santa monica','oakland, california']
ca_keywords = ['canada','toronto','vancouver','montreal','ottawa','calgary','edmonton','winnipeg','quebec','ontario','british columbia','alberta','manitoba','saskatchewan','nova scotia','new brunswick','newfoundland','greater toronto']
us_keywords = us_states + us_metros + ['united states', 'usa', 'u.s.']

intl_tlds = ['.co.uk','.uk','.com.au','.au','.co.nz','.nz','.de','.fr','.nl','.es','.it','.se','.no','.dk','.fi','.be','.at','.ch','.ie','.pt','.pl','.cz','.ro','.hu','.bg','.hr','.sk','.si','.lt','.lv','.ee','.gr','.co.za','.in','.jp','.kr','.sg','.hk','.tw','.br','.mx','.ar','.co','.cl','.pe','.ph','.my','.th','.id','.vn','.il','.ae','.sa','.ng','.ke','.eg','.eu']
na_tlds = ['.ca','.us']

non_icp_keywords = ['india','mumbai','delhi','bangalore','bengaluru','hyderabad','chennai','pune','kolkata','ahmedabad','kerala',
    'brazil','são paulo','sao paulo','rio de janeiro','brazil',
    'singapore','israel','tel aviv','argentina','buenos aires',
    'nigeria','lagos','kenya','nairobi','south africa','johannesburg','cape town',
    'pakistan','karachi','lahore','philippines','manila','indonesia','jakarta',
    'vietnam','hanoi','ho chi minh','thailand','bangkok','malaysia','kuala lumpur',
    'egypt','cairo','colombia','bogota','bogotá','mexico','mexico city','guadalajara',
    'china','beijing','shanghai','japan','tokyo','korea','seoul','taiwan','taipei',
    'russia','moscow','ukraine','kyiv','turkey','istanbul','saudi arabia','riyadh',
    'uae','dubai','abu dhabi','qatar','doha','bahrain','kuwait',
    'chile','santiago','peru','lima','ecuador','quito','venezuela','costa rica',
    'ghana','accra','ethiopia','addis ababa','tanzania','uganda','rwanda',
    'bangladesh','dhaka','sri lanka','nepal','myanmar']

def geo_bucket(loc):
    loc = (loc or '').strip().lower()
    if not loc:
        return 'unknown'
    if any(x in loc for x in us_keywords):
        return 'na'
    if any(x in loc for x in ca_keywords):
        return 'na'
    if any(x in loc for x in non_icp_keywords):
        return 'non-icp-geo'
    return 'international'

def tld_geo(domain):
    domain = (domain or '').strip().lower()
    if not domain: return 'unknown'
    for t in intl_tlds:
        if domain.endswith(t): return 'international'
    for t in na_tlds:
        if domain.endswith(t): return 'na'
    return 'unknown'

# ===================================================================
# STEP 1: Build PHONE lookup from ALL Prospeo enrichment files
# ===================================================================
phone_map = {}  # norm_url -> phone
email_map = {}  # norm_url -> email

# Source A: prospeo-2011-leadmagic (622 phones, 931 emails)
with open(f'{SRC}/prospeo-enrichments/prospeo-2011-leadmagic.csv', 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        url = norm_url(row.get('LinkedIn URL',''))
        email = (row.get('Prospeo Email','') or '').strip()
        phone = (row.get('Prospeo Mobile','') or '').strip()
        if phone and phone != 'Not revealed': phone_map[url] = phone
        if email and '@' in email: email_map.setdefault(url, email)

# Source B: prospeo-841-filtered-done (332 phones, 455 emails)
with open(f'{SRC}/prospeo-enrichments/prospeo-841-filtered-done.csv', 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        url = norm_url(row.get('linkedin_url',''))
        email = (row.get('Prospeo Email','') or row.get('email','') or '').strip()
        phone = (row.get('Prospeo Mobile','') or row.get('phone','') or '').strip()
        if phone and phone != 'Not revealed': phone_map.setdefault(url, phone)
        if email and '@' in email: email_map.setdefault(url, email)

# Source C: prospeo-123 (6b33ef) (23 phones, 29 emails)
with open(f'{SRC}/prospeo-enrichments/prospeo_people_enriched_20260319_205932_6b33ef.csv', 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        url = norm_url(row.get('linkedin_url',''))
        email = (row.get('Prospeo Email','') or '').strip()
        phone = (row.get('Prospeo Mobile','') or '').strip()
        if phone and phone != 'Not revealed': phone_map.setdefault(url, phone)
        if email and '@' in email: email_map.setdefault(url, email)

# Source D: prospeo_enriched_clean_zerobounce (622 phones, 931 emails — overlaps with A)
with open(f'{SRC}/prospeo-enrichments/prospeo_enriched_clean_zerobounce.csv', 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        url = norm_url(row.get('LinkedIn URL',''))
        email = (row.get('Prospeo Email','') or '').strip()
        phone = (row.get('Prospeo Mobile','') or '').strip()
        if phone and phone != 'Not revealed': phone_map.setdefault(url, phone)
        if email and '@' in email: email_map.setdefault(url, email)

# Source E: zerobounce_valid_clean (existing — emails only)
zb_path = f'{BASE}/enriched/zerobounce_valid_clean.csv'
if os.path.exists(zb_path):
    with open(zb_path, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            url = norm_url(row.get('LinkedIn URL',''))
            email = (row.get('Email','') or '').strip()
            if email and '@' in email: email_map.setdefault(url, email)

# Source F: leadmagic-phone-enrichment (emails only, 0 phones)
with open(f'{BASE}/wip/leadmagic-phone-enrichment.csv', 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        url = norm_url(row.get('linkedin_url',''))
        email = (row.get('email','') or '').strip()
        if email and '@' in email: email_map.setdefault(url, email)

# Source G: Apollo exports (phones + emails + location)
apollo_phone_map = {}
apollo_email_map = {}
apollo_loc_map = {}  # norm_url -> location string
apollo_country_map = {}  # norm_url -> country

for fname, url_col in [
    ('apollo-contacts-export (2).csv', 'Person Linkedin Url'),
    ('2b-perf-mktg-claude-skill-commenters-2026-03-13-Valid-Emails-New-batch-export-1773698030676.csv', 'LinkedIn URL'),
    ('canada-numbers-export-1773697306240.csv', 'LinkedIn URL'),
    ('2b-perf-mktg-claude-skill-commenters-2026-03-13-Valid-Emails-export-1773695517911.csv', 'LinkedIn URL'),
]:
    path = f'{SRC}/apollo-exports/{fname}'
    with open(path, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            url = norm_url(row.get(url_col,''))
            if not url: continue
            # Phone
            phone = (row.get('Mobile Phone','') or '').strip()
            if phone and phone != 'Not revealed':
                phone_map.setdefault(url, phone)
            # Email
            email = (row.get('Work Email','') or row.get('Email','') or '').strip()
            if email and '@' in email:
                email_map.setdefault(url, email)
            # Location from State/Province + Country
            state = (row.get('State/Province','') or '').strip()
            country = (row.get('Country','') or '').strip()
            if state or country:
                loc = f'{state}, {country}'.strip(', ') if state else country
                apollo_loc_map[url] = loc
                if country:
                    apollo_country_map[url] = country

print(f'Phone lookup: {len(phone_map)} phones from ALL sources')
print(f'Email lookup: {len(email_map)} emails from ALL sources')
print(f'Apollo location data: {len(apollo_loc_map)} profiles with State/Country')

# ===================================================================
# STEP 2: Build Apollo DEDUP set (ALL 191 unique contacts)
# ===================================================================
apollo_urls = set()
apollo_names = set()
for fname, url_col in [
    ('apollo-contacts-export (2).csv', 'Person Linkedin Url'),
    ('2b-perf-mktg-claude-skill-commenters-2026-03-13-Valid-Emails-New-batch-export-1773698030676.csv', 'LinkedIn URL'),
    ('canada-numbers-export-1773697306240.csv', 'LinkedIn URL'),
    ('2b-perf-mktg-claude-skill-commenters-2026-03-13-Valid-Emails-export-1773695517911.csv', 'LinkedIn URL'),
]:
    path = f'{SRC}/apollo-exports/{fname}'
    with open(path, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            url = norm_url(row.get(url_col,''))
            fn = (row.get('First Name','') or '').strip()
            ln = (row.get('Last Name','') or '').strip()
            name = f'{fn} {ln}'.strip().lower()
            if url: apollo_urls.add(url)
            if name and name != ' ': apollo_names.add(name)

print(f'Apollo dedup set: {len(apollo_urls)} URLs, {len(apollo_names)} names')

# ===================================================================
# STEP 3: Build location + extra data from Apify (old enrichments)
# ===================================================================
loc_map = {}
extra_data = {}

for src in ['apify-enriched-ICP-UNFILTERED.csv', 'apify-geo-filtered-out.csv', 'apify-enriched-ICP-FILTERED-DONE.csv', 'apify-prospeo-enriched-clean-DONE.csv']:
    path = f'{DONE}/{src}'
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                url = norm_url(row.get('linkedin_url',''))
                loc = (row.get('location','') or '').strip()
                if url:
                    if loc: loc_map[url] = loc
                    extra_data[url] = {
                        'company_size': row.get('company_size',''),
                        'industry': row.get('industry',''),
                        'headline': row.get('headline',''),
                        'title': row.get('title',''),
                        'company': row.get('company',''),
                        'company_domain': row.get('company_domain',''),
                        'full_name': row.get('full_name',''),
                        'first_name': row.get('first_name',''),
                        'last_name': row.get('last_name',''),
                    }

# Also pull location from Prospeo enrichment files (they have location column)
for fname, url_col in [
    ('prospeo-841-filtered-done.csv', 'linkedin_url'),
    ('prospeo_people_enriched_20260319_205932_6b33ef.csv', 'linkedin_url'),
]:
    path = f'{SRC}/prospeo-enrichments/{fname}'
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                url = norm_url(row.get(url_col,''))
                loc = (row.get('location','') or '').strip()
                if url and loc and url not in loc_map:
                    loc_map[url] = loc

# ===================================================================
# STEP 3b: Merge NEW Apify LinkedIn profile scrape results (no-geo batches)
# ===================================================================
import json as _json
apify_cc_map = {}   # norm_url -> countryCode (e.g. 'US','CA','GB')
apify_loc_text = {} # norm_url -> parsed location text

APIFY_BATCH_DIR = f'{BASE}/wip/apify-nogeo-batches'
for batch_file in ['batch-01-apify-results.json','batch-02-apify-results.json','batch-03-apify-results.json','batch-04-apify-results.json']:
    path = f'{APIFY_BATCH_DIR}/{batch_file}'
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8') as f:
        items = _json.load(f)
    for item in items:
        url = norm_url(item.get('linkedinUrl',''))
        if not url:
            continue
        loc = item.get('location') or {}
        cc = loc.get('countryCode','')
        parsed = loc.get('parsed') or {}
        loc_text = loc.get('linkedinText','') or parsed.get('text','')
        if cc:
            apify_cc_map[url] = cc
        if loc_text:
            apify_loc_text[url] = loc_text
            if url not in loc_map:
                loc_map[url] = loc_text

print(f'Location lookup: {len(loc_map)} from Apify + Prospeo + new scrapes')
print(f'Apify country codes: {len(apify_cc_map)} from LinkedIn scrapes')
print(f'Apollo location supplement: {len(apollo_loc_map)} from Apollo exports')

# --- ICP GEO from country code ---
NA_CODES = {'US','CA'}
ICP_INTL_CODES = {'GB','AU','NZ','IE','DE','FR','NL','AT','BE','CH','DK','ES','FI','IT','NO','PT','SE','PL','CZ'}

def cc_geo(url):
    """Return geo bucket from Apify country code"""
    cc = apify_cc_map.get(url,'')
    if cc in NA_CODES:
        return 'na'
    if cc in ICP_INTL_CODES:
        return 'international'
    if cc:
        return 'non-icp-geo'  # has geo but not ICP region
    return 'unknown'

# ===================================================================
# STEP 4: Process ICP-FILTERED-DONE (841 leads)
# ===================================================================
output_headers = ['first_name','last_name','full_name','title','headline','company','company_domain','linkedin_url','location','company_size','industry','email','phone','source']

na_icp = []
intl_icp = []
no_geo = []
non_icp_dropped = 0
seen_urls = set()
apollo_dupes = 0

with open(f'{DONE}/apify-enriched-ICP-FILTERED-DONE.csv', 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        url = norm_url(row.get('linkedin_url',''))
        name = (row.get('full_name','') or '').strip().lower()

        if url in seen_urls: continue
        if url in apollo_urls or name in apollo_names:
            apollo_dupes += 1
            seen_urls.add(url)
            continue
        seen_urls.add(url)

        out = {
            'first_name': row.get('first_name',''),
            'last_name': row.get('last_name',''),
            'full_name': row.get('full_name',''),
            'title': row.get('title',''),
            'headline': row.get('headline',''),
            'company': row.get('company',''),
            'company_domain': row.get('company_domain',''),
            'linkedin_url': row.get('linkedin_url',''),
            'location': row.get('location',''),
            'company_size': row.get('company_size',''),
            'industry': row.get('industry',''),
            'email': email_map.get(url, ''),
            'phone': phone_map.get(url, ''),
            'source': 'ICP-FILTERED',
        }

        bucket = cc_geo(url)
        if bucket == 'unknown':
            bucket = geo_bucket(row.get('location',''))
        if bucket == 'na':
            na_icp.append(out)
        elif bucket == 'international':
            intl_icp.append(out)
        elif bucket == 'non-icp-geo':
            non_icp_dropped += 1
        else:
            no_geo.append(out)

print(f'\nICP-FILTERED-DONE: {len(na_icp)} NA + {len(intl_icp)} INTL + {len(no_geo)} no-geo (deduped {apollo_dupes} Apollo)')

# ===================================================================
# STEP 5: Process leadmagic pipeline (2,011 leads)
# Uses Apollo export location + TLD as geo signal
# ===================================================================
prospeo_added = 0
with open(f'{BASE}/wip/leadmagic-phone-enrichment.csv', 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        url = norm_url(row.get('linkedin_url',''))
        name = f"{row.get('first_name','')} {row.get('last_name','')}".strip().lower()

        if url in seen_urls: continue
        if url in apollo_urls or name in apollo_names:
            apollo_dupes += 1
            seen_urls.add(url)
            continue
        seen_urls.add(url)

        email = email_map.get(url, '') or (row.get('email','') or '').strip()
        phone = phone_map.get(url, '')

        # Location: try new Apify scrape first, then old Apify, then Apollo exports
        location = apify_loc_text.get(url, '') or loc_map.get(url, '') or apollo_loc_map.get(url, '')
        ed = extra_data.get(url, {})
        domain = ed.get('company_domain','') or row.get('domain','')

        out = {
            'first_name': ed.get('first_name','') or row.get('first_name',''),
            'last_name': ed.get('last_name','') or row.get('last_name',''),
            'full_name': ed.get('full_name','') or f"{row.get('first_name','')} {row.get('last_name','')}".strip(),
            'title': ed.get('title','') or row.get('job_title',''),
            'headline': ed.get('headline',''),
            'company': ed.get('company','') or row.get('company',''),
            'company_domain': domain,
            'linkedin_url': row.get('linkedin_url',''),
            'location': location,
            'company_size': ed.get('company_size',''),
            'industry': ed.get('industry',''),
            'email': email,
            'phone': phone,
            'source': 'LEADMAGIC-PIPELINE',
        }

        # Country code is most reliable — try FIRST
        bucket = cc_geo(url)
        if bucket == 'unknown':
            bucket = geo_bucket(location)
        if bucket == 'unknown':
            # Try Apollo country
            country = apollo_country_map.get(url, '')
            if country:
                bucket = geo_bucket(country)
        if bucket == 'unknown':
            bucket = tld_geo(domain)

        if bucket == 'na':
            na_icp.append(out)
        elif bucket == 'international':
            intl_icp.append(out)
        elif bucket == 'non-icp-geo':
            non_icp_dropped += 1  # Has geo but not ICP region — drop
        else:
            no_geo.append(out)
        prospeo_added += 1

print(f'Leadmagic pipeline: added {prospeo_added} ({len(no_geo)} no geo)')
print(f'Apollo dupes removed so far: {apollo_dupes}')

# ===================================================================
# STEP 6: Process prospeo-123 (6b33ef) — NEW contacts not in other pipelines
# ===================================================================
p123_added = 0
with open(f'{SRC}/prospeo-enrichments/prospeo_people_enriched_20260319_205932_6b33ef.csv', 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        url = norm_url(row.get('linkedin_url',''))
        fn = (row.get('first_name','') or row.get('Prospeo First name','') or '').strip()
        ln = (row.get('last_name','') or row.get('Prospeo Last name','') or '').strip()
        name = f'{fn} {ln}'.strip().lower()

        if url in seen_urls: continue
        if url in apollo_urls or name in apollo_names:
            apollo_dupes += 1
            seen_urls.add(url)
            continue
        seen_urls.add(url)

        email = email_map.get(url, '') or (row.get('Prospeo Email','') or '').strip()
        phone = phone_map.get(url, '')
        location = (row.get('location','') or '').strip()
        domain = (row.get('company_domain','') or row.get('Prospeo Company domain','') or '').strip()

        out = {
            'first_name': fn or (row.get('Prospeo First name','') or ''),
            'last_name': ln or (row.get('Prospeo Last name','') or ''),
            'full_name': (row.get('Prospeo Full name','') or f'{fn} {ln}').strip(),
            'title': row.get('title','') or row.get('Prospeo Job title',''),
            'headline': row.get('headline',''),
            'company': row.get('company','') or row.get('Prospeo Company name',''),
            'company_domain': domain,
            'linkedin_url': row.get('linkedin_url',''),
            'location': location,
            'company_size': '',
            'industry': row.get('Prospeo Company industry',''),
            'email': email if '@' in (email or '') else '',
            'phone': phone,
            'source': 'PROSPEO-123',
        }

        bucket = cc_geo(url)
        if bucket == 'unknown':
            bucket = geo_bucket(location)
        if bucket == 'unknown':
            bucket = tld_geo(domain)

        if bucket == 'na':
            na_icp.append(out)
        elif bucket == 'international':
            intl_icp.append(out)
        elif bucket == 'non-icp-geo':
            non_icp_dropped += 1
        else:
            no_geo.append(out)
        p123_added += 1

print(f'Prospeo-123 batch: added {p123_added}')

# ===================================================================
# STEP 7: Process Valid-Emails-export (27 leads — separate from apollo104)
# ===================================================================
ve_added = 0
for fname in ['2b-perf-mktg-claude-skill-commenters-2026-03-13-Valid-Emails-export-1773695517911.csv']:
    path = f'{SRC}/apollo-exports/{fname}'
    with open(path, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            url = norm_url(row.get('LinkedIn URL',''))
            fn = (row.get('First Name','') or '').strip()
            ln = (row.get('Last Name','') or '').strip()
            name = f'{fn} {ln}'.strip().lower()

            if url in seen_urls: continue
            # These ARE in Apollo already, so skip them for the phone queue
            # They're already enriched in Apollo
            seen_urls.add(url)
            # Don't add — they're Apollo contacts

print(f'Valid-Emails-export (27): skipped (already in Apollo)')

# ===================================================================
# STEP 8: Process NO-MATCH swept (40 leads)
# ===================================================================
na_nomatch = []
intl_nomatch = []
nomatch_apollo_dupes = 0

with open(f'{DONE}/claude-code-80hrs-NO-MATCH-SWEPT.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        url = ''
        for col in ['linkedin_url', 'LinkedIn URL']:
            url = norm_url(row.get(col,''))
            if url: break
        name = ''
        for col in ['full_name', 'Full Name']:
            name = (row.get(col,'') or '').strip().lower()
            if name: break
        if not name:
            fn = row.get('first_name','') or row.get('First Name','')
            ln = row.get('last_name','') or row.get('Last Name','')
            name = f'{fn} {ln}'.strip().lower()

        if url in seen_urls: continue
        if url in apollo_urls or name in apollo_names:
            nomatch_apollo_dupes += 1
            if url: seen_urls.add(url)
            continue
        if url: seen_urls.add(url)

        location = loc_map.get(url, '') or apollo_loc_map.get(url, '')

        out = {
            'first_name': row.get('first_name','') or row.get('First Name',''),
            'last_name': row.get('last_name','') or row.get('Last Name',''),
            'full_name': name.title(),
            'title': row.get('title','') or row.get('Title',''),
            'headline': row.get('headline','') or row.get('Headline','') or row.get('Occupation (Full)',''),
            'company': row.get('company','') or row.get('Company',''),
            'company_domain': row.get('company_domain','') or row.get('Company Domain','') or row.get('Company Domain (Estimated)',''),
            'linkedin_url': row.get('linkedin_url','') or row.get('LinkedIn URL',''),
            'location': location,
            'company_size': '',
            'industry': '',
            'email': email_map.get(url, ''),
            'phone': phone_map.get(url, ''),
            'source': 'NO-MATCH-SWEPT',
        }

        bucket = geo_bucket(location)
        if bucket == 'na':
            na_nomatch.append(out)
        else:
            intl_nomatch.append(out)

print(f'\nNO-MATCH-SWEPT: {len(na_nomatch)} NA + {len(intl_nomatch)} INTL (deduped {nomatch_apollo_dupes} Apollo)')

# ===================================================================
# STEP 9: ICP TIER CLASSIFICATION + FILTER
# ===================================================================
wl_kw = ['fractional cmo','fractional chief','fractional marketing','fractional growth',
    'freelance market','freelance digital','freelance growth','freelance paid','freelance seo',
    'freelance content','freelance ppc','independent consultant','solo consultant',
    'marketing consultant','growth consultant','digital consultant','media consultant']
wl_pattern = re.compile(r'i help\s+(companies|brands|businesses|startups|founders|ceos|teams)', re.I)

t1_titles = ['cmo','chief marketing','chief growth','chief revenue','chief digital','chief executive',
    'chief operating','vp of marketing','vp of growth','vp of digital','vp of demand','vp of performance',
    'vp of paid','vp marketing','vp growth','vp digital','vp demand','vp performance','vp paid',
    'head of marketing','head of growth','head of digital','head of performance','head of paid',
    'head of demand','head of acquisition','head of media','head of ecommerce','head of e-commerce',
    'head of product marketing','director of marketing','director of growth','director of digital',
    'director of performance','director of paid','director of demand','director of product marketing',
    'director of ecommerce','director of e-commerce','director of media','managing director',
    'general manager','co-founder','cofounder','founder','ceo','owner','president','partner',
    'managing partner','principal','agency owner','agency founder']
t1_headline = ['ceo','chief executive','co-founder','cofounder','founder','agency owner']

t2_titles = ['marketing manager','growth manager','digital manager','performance manager',
    'ecommerce manager','e-commerce manager','brand manager','campaign manager','media buyer',
    'ppc manager','sem manager','senior marketing','senior growth','senior digital',
    'marketing lead','growth lead','digital lead','marketing director','growth director',
    'revops','revenue operations','founding marketer','strategy director','strategy lead',
    'content director','head of content','content lead']
t2_headline = ['agency','ecommerce','e-commerce','shopify','amazon fba','dtc','d2c',
    'google ads','meta ads','facebook ads','paid media','ppc','media buying','performance market']

t3_kw = ['marketing','growth','brand','content','seo','social media','digital','demand',
    'acquisition','retention','lifecycle','product marketing','go-to-market','gtm']

junk_kw = ['student','intern','seeking opportunities','open to work','job seeker','looking for',
    'aspiring','recent graduate','fresh graduate']
non_mktg_kw = ['engineer','developer','software','designer','recruiter','lawyer','attorney',
    'teacher','therapist','nurse','doctor','accountant','auditor','paralegal','architect']

def classify_icp(title, headline):
    t = (title or '').lower().strip()
    h = (headline or '').lower().strip()
    combined = f'{t} {h}'
    if any(x in combined for x in junk_kw):
        return 'REMOVE'
    if any(x in t for x in non_mktg_kw) and not any(x in combined for x in ['marketing','growth','brand','media']):
        return 'REMOVE'
    if any(x in combined for x in wl_kw) or wl_pattern.search(h):
        return 'WHITELABEL'
    if any(x in t for x in t1_titles) or any(x in h for x in t1_headline):
        return 'TIER1'
    if any(x in t for x in t2_titles) or any(x in h for x in t2_headline):
        return 'TIER2'
    if any(x in combined for x in t3_kw):
        return 'TIER3'
    if not t and not h:
        return 'NO-DATA'
    return 'REMOVE'

# Filter all lists
def filter_list(rows):
    kept = []
    whitelabel = []
    removed = 0
    nodata = 0
    for r in rows:
        tier = classify_icp(r.get('title',''), r.get('headline',''))
        if tier in ('REMOVE', 'NO-DATA'):
            if tier == 'NO-DATA': nodata += 1
            else: removed += 1
            continue
        r['icp_tier'] = tier
        if tier == 'WHITELABEL':
            whitelabel.append(r)
        else:
            kept.append(r)
    return kept, whitelabel, removed, nodata

na_icp, na_wl, na_rm, na_nd = filter_list(na_icp)
intl_icp, intl_wl, intl_rm, intl_nd = filter_list(intl_icp)
no_geo, ng_wl, ng_rm, ng_nd = filter_list(no_geo)
na_nomatch, nm_wl, nm_rm, nm_nd = filter_list(na_nomatch)
intl_nomatch, inm_wl, inm_rm, inm_nd = filter_list(intl_nomatch)

all_wl = na_wl + intl_wl + ng_wl + nm_wl + inm_wl
total_rm = na_rm + intl_rm + ng_rm + nm_rm + inm_rm
total_nd = na_nd + intl_nd + ng_nd + nm_nd + inm_nd

print(f'\nICP FILTER: kept T1/T2/T3, split {len(all_wl)} whitelabel, removed {total_rm} non-ICP, removed {total_nd} no-data')

# ===================================================================
# STEP 10: Write output files
# ===================================================================
out_dir = f'{BASE}/active/claude-80hrs-phone-enrichment'
os.makedirs(out_dir, exist_ok=True)

output_headers_tier = output_headers + ['icp_tier']

def write_csv(path, rows, headers):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    return len(rows)

# Clean out old files first
import glob as _glob
for old in _glob.glob(f'{out_dir}/*.csv'):
    os.remove(old)

n1 = write_csv(f'{out_dir}/01-NA-USA-CANADA-{len(na_icp)}-leads.csv', na_icp, output_headers_tier)
n2 = write_csv(f'{out_dir}/02-INTL-EU-AU-OTHER-{len(intl_icp)}-leads.csv', intl_icp, output_headers_tier)
nwl = write_csv(f'{out_dir}/03-WHITELABEL-{len(all_wl)}-leads.csv', all_wl, output_headers_tier) if all_wl else 0

na_emails = sum(1 for r in na_icp if r['email'])
intl_emails = sum(1 for r in intl_icp if r['email'])
wl_emails = sum(1 for r in all_wl if r['email'])

print(f'\n{"="*70}')
print(f'OUTPUT FILES in {out_dir}/')
print(f'{"="*70}')
print(f'{"File":<55} {"Leads":>5} {"Email":>6}')
print(f'{"-"*70}')
print(f'{f"01-NA-USA-CANADA-{n1}-leads.csv":<55} {n1:>5} {na_emails:>6}')
print(f'{f"02-INTL-EU-AU-OTHER-{n2}-leads.csv":<55} {n2:>5} {intl_emails:>6}')
if nwl: print(f'{f"03-WHITELABEL-{nwl}-leads.csv":<55} {nwl:>5} {wl_emails:>6}')
print(f'{"-"*70}')
total = n1 + n2 + (nwl or 0)
total_emails = na_emails + intl_emails + wl_emails
print(f'{"TOTAL":<55} {total:>5} {total_emails:>6}')
print(f'{"="*70}')
print(f'Apollo contacts deduped: {apollo_dupes + nomatch_apollo_dupes}')
print(f'Non-ICP geo dropped: {non_icp_dropped} (IN, BR, SG, etc.)')
print(f'ICP filter dropped: {total_rm} non-marketing + {total_nd} no-data = {total_rm + total_nd}')
