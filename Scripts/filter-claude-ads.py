import json, re, sys
sys.stdout.reconfigure(errors='replace')

out_dir = 'C:/Users/olive/OneDrive/Desktop/Sprites Work/Leads/wip/claude-ads-post-scrape'
with open(f'{out_dir}/all-comments-raw.json', 'r', encoding='utf-8') as f:
    all_items = json.load(f)

def is_claude_ads(text):
    t = text.lower().strip()
    if re.search(r'claude\s*ads', t): return True
    if re.search(r'claude\s*adds', t): return True
    if re.search(r'claude\s*ada', t): return True
    if re.search(r"claude\s*ad's", t): return True
    if re.search(r'calude\s*ads', t): return True
    if re.search(r'cladude\s*ads', t): return True
    if re.search(r'clause\s*ads', t): return True
    if re.search(r'cluade\s*ads', t): return True
    if re.search(r'claud\s+ads', t): return True
    return False

filtered = [item for item in all_items if is_claude_ads(item.get('commentary', ''))]
urls = set()
for item in filtered:
    li_url = item.get('actor', {}).get('linkedinUrl', '')
    if li_url and '/in/' in li_url:
        urls.add(li_url)

print(f'Total comments: {len(all_items)}')
print(f'Claude ads matches (expanded): {len(filtered)}')
print(f'Unique profile URLs: {len(urls)}')

with open(f'{out_dir}/claude-ads-filtered.json', 'w', encoding='utf-8') as f:
    json.dump(filtered, f, ensure_ascii=False)
url_list = sorted(urls)
with open(f'{out_dir}/claude-ads-profile-urls.json', 'w', encoding='utf-8') as f:
    json.dump(url_list, f, ensure_ascii=False)

non_match = [(c.get('commentary', '')[:60]) for c in all_items if not is_claude_ads(c.get('commentary', ''))]
print(f'Remaining non-matches ({len(non_match)}):')
for c in non_match:
    safe = c.encode('ascii', 'replace').decode()
    print(f'  "{safe}"')

print(f'Profile scrape estimate: {len(urls)} x $0.004 = ${len(urls)*0.004:.2f}')
