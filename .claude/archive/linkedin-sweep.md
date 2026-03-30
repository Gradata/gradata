# LinkedIn Post Lead Workflow & Sweep Rules

## Post Lead Workflow
When Oliver shares a LinkedIn post URL:
1. Scrape all commenters (load all comments, not just visible ones)
2. Filter by ICP title and geography rules (below)
3. Build lead list: Full Name, Title, Company, LinkedIn URL
4. Auto-load ICP leads into Clay under "Oliver's Leads"
5. Build a 1-week Instantly sequence relevant to the post topic

This is Oliver's primary cold prospecting trigger. Every post link = build a lead list.

## Rate Limiting (ban prevention)
- 30-60 second randomized delays between profile visits
- Max 200 profiles per daily session
- If LinkedIn shows captcha or "unusual activity", stop immediately and tell Oliver
- Browser profile persists at C:\Users\olive\.linkedin-browser\

## Queue + CSV Workflow
1. Source file goes in leads/raw/
2. Filter into leads/filtered/ (ICP match + no-match CSVs)
3. Sweep no-match list daily via linkedin-sweep-nomatch.py
4. When complete, merge ICP finds into leads/enriched/ with date suffix

## ICP Geography Filter
Include (any country with budget for $500-1k/mo):
US, CA, MX, UK, DE, FR, NL, BE, CH, AT, IE, LU, SE, DK, NO, FI, IS, ES, PT, IT, GR, PL, CZ, RO, HU, HR, EE, LV, LT, SI, SK, BG, AU, NZ, BR, CL, CO, AR, UY, CR, PA, UAE, IL, SA, QA, KW, BH, SG, JP, KR, HK, TW, ZA

Skip:
India, Pakistan, Bangladesh, Nepal, Sri Lanka, Egypt, Nigeria, Kenya, Ghana, Ethiopia, Tanzania, Uganda, Philippines, Indonesia, Vietnam, Thailand, Cambodia, Myanmar, Laos, Venezuela, Cuba, Bolivia, Nicaragua, Honduras, El Salvador, Iran, Syria, Iraq, Afghanistan, Uzbekistan, Tajikistan, Turkmenistan, Kyrgyzstan

## ICP Title Filter
Include: Performance Marketing, Paid Media, PPC, SEM, SEA, Google Ads, Meta Ads, Head/VP/Director Marketing, CMO, Founder, Owner, Agency Principal, Fractional CMO, E-commerce Manager/Director, Demand Gen, Growth Marketing

Skip: SEO only, social media only, content only, BizDev, data science, product, engineering, HR, finance

## CSV Columns
Full Name, First Name, Last Name, Title, Company, LinkedIn URL, State/Province, Country, Company Domain, Company LinkedIn URL

## Cross-referencing Scraper Exports
- When a scraper CSV is uploaded, cross-reference against existing leads by LinkedIn slug
- Filter unvisited entries by ICP keywords in occupation field
- Visit only ICP-geography candidates; skip known non-ICP regions
