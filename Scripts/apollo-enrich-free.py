"""
Free Apollo enrichment via People Search API.
Searches by name + headline keywords to get title + company.
Zero credits consumed.
"""
import json, csv, os, sys, time, re

# Config
LUNA_RAW = 'c:/Users/olive/Downloads/dataset_linkedin-post-comments_2026-03-24_00-56-50-577.json'
DANIEL_RAW = 'c:/Users/olive/Downloads/dataset_linkedin-post-comments_2026-03-24_00-33-37-176.json'
OUTPUT_DIR = 'c:/Users/olive/OneDrive/Desktop/Sprites Work/Leads/wip'

# We'll use requests directly since MCP is one-at-a-time
# Apollo API key from environment or hardcoded team key
APOLLO_API_KEY = None  # Will be passed as arg

def extract_leads(filepath, keyword_pattern):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    pattern = re.compile(keyword_pattern, re.IGNORECASE)
    leads = []
    seen = set()
    for d in data:
        if not pattern.search(str(d.get('commentary', ''))):
            continue
        actor = d.get('actor', {})
        url = actor.get('linkedinUrl', '')
        if not url or url in seen:
            continue
        seen.add(url)
        loc = actor.get('location', {})
        parsed = loc.get('parsed', {})
        leads.append({
            'first_name': actor.get('firstName', '') or '',
            'last_name': actor.get('lastName', '') or '',
            'full_name': actor.get('name', '') or '',
            'headline': actor.get('headline', '') or '',
            'position': actor.get('position', '') or '',
            'linkedin_url': url,
            'location_text': loc.get('linkedinText', '') or '',
            'country': parsed.get('country', '') or '',
            'country_code': parsed.get('countryCode', '') or '',
            'comment': str(d.get('commentary', ''))[:200],
        })
    return leads

def search_apollo(first_name, last_name, headline, api_key):
    """Search Apollo by name + keywords from headline. Returns title, company or None."""
    import urllib.request, urllib.parse

    # Build keyword query: name + first meaningful word from headline
    # Extract company from headline if possible (after @ or "at")
    company_hint = ''
    m = re.search(r'(?:@|at|At|AT)\s+([A-Z][A-Za-z0-9\s&.]+)', headline)
    if m:
        company_hint = m.group(1).strip()[:30]

    query = f"{first_name} {last_name}"
    if company_hint:
        query += f" {company_hint}"

    url = "https://api.apollo.io/api/v1/mixed_people/search"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key,
    }
    payload = json.dumps({
        "q_keywords": query,
        "per_page": 1,
        "page": 1,
    }).encode('utf-8')

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode('utf-8'))

        people = result.get('people', [])
        if people:
            p = people[0]
            org = p.get('organization', {}) or {}
            return {
                'apollo_title': p.get('title', ''),
                'apollo_company': org.get('name', ''),
                'apollo_has_email': p.get('has_email', False),
                'apollo_has_phone': p.get('has_direct_phone', ''),
                'apollo_id': p.get('id', ''),
            }
    except Exception as e:
        pass

    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python apollo-enrich-free.py <apollo_api_key> [start_index]")
        sys.exit(1)

    api_key = sys.argv[1]
    start_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    # Extract all leads from both files
    print("Loading Luna Chen leads...")
    luna_leads = extract_leads(LUNA_RAW, r'\bgrowth\b|\bgrow\b|\bgrowing\b')
    print(f"  {len(luna_leads)} leads")

    print("Loading Daniel Paul leads...")
    daniel_leads = extract_leads(DANIEL_RAW, r'\bteam\b')
    print(f"  {len(daniel_leads)} leads")

    # Dedup across both lists
    all_leads = []
    seen_urls = set()
    for l in luna_leads + daniel_leads:
        url = l['linkedin_url'].rstrip('/').lower()
        if url not in seen_urls:
            seen_urls.add(url)
            all_leads.append(l)

    print(f"Total unique: {len(all_leads)}")

    # Output file
    output_path = os.path.join(OUTPUT_DIR, 'apollo-enriched-all.csv')
    fields = ['first_name', 'last_name', 'full_name', 'headline', 'position',
              'linkedin_url', 'location_text', 'country', 'country_code', 'comment',
              'apollo_title', 'apollo_company', 'apollo_has_email', 'apollo_has_phone', 'apollo_id']

    # Resume from existing file if start_idx > 0
    existing = 0
    if os.path.exists(output_path) and start_idx > 0:
        with open(output_path, 'r', encoding='utf-8-sig') as f:
            existing = sum(1 for _ in csv.DictReader(f))
        print(f"Resuming from index {start_idx} ({existing} already done)")
        mode = 'a'
        write_header = False
    else:
        mode = 'w'
        write_header = True

    f = open(output_path, mode, newline='', encoding='utf-8-sig')
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
    if write_header:
        writer.writeheader()

    matched = 0
    missed = 0
    errors = 0

    for i, lead in enumerate(all_leads[start_idx:], start=start_idx):
        if i % 100 == 0 and i > start_idx:
            print(f"  Progress: {i}/{len(all_leads)} | Matched: {matched} | Missed: {missed} | Errors: {errors}")
            f.flush()

        result = search_apollo(lead['first_name'], lead['last_name'], lead['headline'], api_key)

        if result:
            lead.update(result)
            matched += 1
        else:
            lead['apollo_title'] = ''
            lead['apollo_company'] = ''
            lead['apollo_has_email'] = ''
            lead['apollo_has_phone'] = ''
            lead['apollo_id'] = ''
            missed += 1

        writer.writerow(lead)

        # Rate limit: Apollo free tier ~5 req/sec
        time.sleep(0.25)

    f.close()

    print(f"\nDone! {len(all_leads)} leads processed.")
    print(f"Matched: {matched} ({matched/len(all_leads)*100:.1f}%)")
    print(f"Missed: {missed}")
    print(f"Errors: {errors}")
    print(f"Output: {output_path}")

if __name__ == '__main__':
    main()
