# Lead List Filtering SOP
# When Oliver uploads an unfiltered CSV, follow this exact process. No asking, just execute.

## Step 0: Assess the Input
- Count rows, list columns, check data completeness (% with title, company, email, linkedin, location)
- Identify the source (LinkedIn scrape, Apollo export, Clay, Prospeo, etc.)
- Show Oliver a 5-line summary: total rows, data quality, what's missing

## Step 1: Dedup Against Existing Lists
- Load ALL files in Leads/wip/ and Leads/enriched/
- Dedup by LinkedIn URL (normalized: lowercase, strip trailing slash)
- If no LinkedIn URL, dedup by email
- If neither, dedup by first_name + last_name + company
- Report: "X dupes removed, Y unique new leads"

## Step 2: Pre-Enrichment Filter (FREE — before spending money)
Run these filters using EXISTING data in the CSV (title, headline, location, company):

### 2a. Remove Junk
- Students, interns, job seekers, "seeking opportunities", "open to work"
- Non-marketing functions: engineers, designers, recruiters, lawyers, teachers, therapists, real estate
- Bots, test accounts, empty profiles

### 2b. Geo Filter (if location data exists)
- KEEP: US, Canada, UK, Australia, New Zealand, Ireland, EU (Germany, Netherlands, France, Spain, Italy, Nordics, Belgium, Austria, Switzerland, Portugal)
- KEEP: US metro areas (New York, San Francisco, LA, Chicago, Boston, Seattle, etc.)
- REMOVE: India, Pakistan, Turkey, Southeast Asia (unless Oliver says otherwise)
- NO LOCATION: keep but flag — will get from enrichment

### 2c. Split Whitelabel
Keywords (check title + headline): fractional cmo, fractional chief, fractional marketing, fractional growth, freelance market, freelance digital, freelance growth, freelance paid, freelance seo, freelance content, freelance ppc, independent consultant, solo consultant, marketing consultant, growth consultant, digital consultant, media consultant
- Also catch: "I help [companies/brands] do X" pattern in headlines (consultants who don't say "consultant")
- Agency owners go to ICP, not whitelabel (they buy Sprites for clients)

### 2d. Report Pre-Enrichment Results
"Starting: X leads. After filter: Y ICP, Z whitelabel, W removed. Ready for enrichment?"

## Step 3: Enrichment (only on filtered leads)
Order: Free first, paid only with approval.
1. If missing titles/companies → Apify LinkedIn scraper ($4/1K). Ask Oliver for budget approval.
2. If missing emails → Prospeo (Oliver runs manually)
3. If missing phones → Lead Magic (Oliver runs manually)
NEVER enrich leads that will be filtered out. Filter FIRST, enrich SECOND.

## Step 4: Post-Enrichment Scoring (one comprehensive pass)
Score EVERY lead into exactly one bucket. No "manual review" bucket.

### Tier 1 — Decision Makers (buy tools)
Title matches: CMO, Chief Marketing/Growth/Revenue/Digital/Executive/Operating, VP of Marketing/Growth/Digital/Demand/Performance/Paid, Head of Marketing/Growth/Digital/Performance/Paid/Demand/Acquisition/Media/Ecommerce/Product Marketing, Director of Marketing/Growth/Digital/Performance/Paid/Demand/Product Marketing/Ecommerce/Media, Managing Director, General Manager, Co-Founder, Founder, CEO, Owner, President, Partner, Managing Partner, Principal, Agency Owner/Founder
Also Tier 1 if headline contains: ceo, chief executive, co-founder, founder, agency owner

### Tier 2 — Managers & Signal-Based
Title matches: Marketing/Growth/Digital/Performance/Ecommerce/Brand/Campaign Manager, Media Buyer, PPC/SEM Manager, Senior Marketing/Growth/Digital, Marketing/Growth/Digital Lead, Marketing/Growth Director, RevOps, Revenue Operations, Founding Marketer, Strategy Director/Lead, Content Director, Head of Content, Content Lead
Headline signals: agency, ecommerce, e-commerce, shopify, amazon fba, dtc, d2c, google ads, meta ads, facebook ads, paid media, ppc, media buying, performance market

### Tier 3 — Marketing Function (lower titles)
Headline/title contains any: marketing, growth, brand, content, seo, social media, digital, demand, acquisition, retention, lifecycle, product marketing, go-to-market, gtm

### Remove — Not Marketing Function
Everything else. If they don't match Tier 1, 2, 3, or whitelabel, they're not a marketing buyer.

## Step 5: Output
Write to Leads/wip/ with standardized schema:
first_name, last_name, full_name, title, headline, about_snippet, company, company_domain, company_linkedin_url, company_size, industry, location, linkedin_url, email, phone, icp_tier, lead_type

Split into separate files:
- [source]-ICP-FILTERED.csv (tiers 1-3)
- WHITELABEL-MASTER.csv (append, dedup)
- Archive removed to Leads/done/

## Step 6: Cleanup
- Archive all intermediate files to Leads/done/[source-date]/
- Remove any scripts, JSON files, temp files from wip/
- Final wip/ should only have actionable files
- Show Oliver the final state

## Complete Email Pipeline (7 Steps)
When Oliver provides a raw lead source and wants an Instantly-ready list:

### Step 1: Free Data Collection
- Source: LinkedIn scrape, post commenters, Apollo free search, web scrape
- Get: names, titles (if available), companies (if available), LinkedIn URLs
- Cost: $0 (or Apify at $4/1K if bulk LinkedIn scrape needed with approval)

### Step 2: First Filter (pre-enrichment)
- Remove: students, interns, job seekers, non-marketing functions
- Split: whitelabel candidates to separate list
- Use whatever data exists (headline, title keywords)

### Step 3: Apify LinkedIn Scrape (fill gaps)
- Only on the filtered survivors from Step 2
- Get: real title, company, location, headline, about snippet
- Cost: ~$4/1K profiles. Ask Oliver for approval.

### Step 4: Second Filter (post-enrichment, one comprehensive pass)
- Geo filter: US/CA/UK/AU/NZ/EU only
- Title scoring: Tier 1 (decision makers), Tier 2 (managers), Tier 3 (marketing function)
- Remove: non-marketing, non-target geo
- Move: new whitelabel catches to WHITELABEL-MASTER
- ONE PASS with full keyword lists. No second passes.

### Step 5: Prospeo API — Email + Phone Enrichment
- Only on Step 4 survivors (ICP + whitelabel)
- Endpoint: Enrich Person (by LinkedIn URL)
- Returns: verified email + mobile
- Cost: per Prospeo plan. State count before running.

### Step 6: ZeroBounce API — Double Verification
- Run all Prospeo emails through ZeroBounce for second-layer validation
- Filter to: valid + catch-all only. Remove invalid/unknown.
- Cost: per ZeroBounce plan. State count before running.

### Step 7: Output — Instantly Ready
- Clean CSV with: first_name, last_name, email (ZB-verified), company, title, linkedin_url, location, icp_tier
- Split: ICP list + whitelabel list (separate campaigns)
- Archive all intermediate files to done/

### Pipeline Rules
- Steps 1-2 are FREE. Always do these before spending money.
- Step 3 costs money. Filter first (Step 2), enrich survivors only.
- Steps 5-6 cost money. Filter twice (Steps 2+4) before enriching.
- Never enrich a lead that will be filtered out in the next step.
- Always state total count + estimated cost before Steps 3, 5, and 6.

## Efficiency Rules
- NEVER ask "want me to filter?" — just filter and show results
- NEVER label leads "needs manual review" — score them programmatically
- NEVER run enrichment before filtering — filter first, enrich the survivors
- NEVER run the filter multiple times — get it right in one comprehensive pass
- ALWAYS dedup against existing files before anything else
- ALWAYS show cost estimate before paid enrichment
- ALWAYS archive intermediate files when done
