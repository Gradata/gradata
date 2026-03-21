data = [
    {"name": "Agency / Decision Makers", "contacted": 993, "replies": 87, "opps": 13, "persona": "agency-owner", "angle": "direct"},
    {"name": "Agency / Margin Pressure", "contacted": 998, "replies": 7, "opps": 2, "persona": "agency-owner", "angle": "margin-pressure"},
    {"name": "Agency / Operational Chaos", "contacted": 711, "replies": 2, "opps": 0, "persona": "agency-owner", "angle": "operational-chaos"},
    {"name": "Agency / Marketers", "contacted": 454, "replies": 8, "opps": 0, "persona": "agency-owner", "angle": "general"},
    {"name": "Agencies - Automation Margins", "contacted": 315, "replies": 1, "opps": 0, "persona": "agency-owner", "angle": "automation"},
    {"name": "Agencies - Cursor/future", "contacted": 244, "replies": 0, "opps": 0, "persona": "agency-owner", "angle": "future-tech"},
    {"name": "Research Invite (all)", "contacted": 9969, "replies": 159, "opps": 45, "persona": "mixed", "angle": "research-invite"},
    {"name": "Mobile App Founders", "contacted": 6007, "replies": 17, "opps": 4, "persona": "founder", "angle": "free-trial"},
    {"name": "Mobile App DMs", "contacted": 1943, "replies": 10, "opps": 4, "persona": "growth-lead", "angle": "free-trial"},
    {"name": "SEO SMB owners", "contacted": 4321, "replies": 33, "opps": 4, "persona": "smb-owner", "angle": "seo-automation"},
    {"name": "Apps / Founders CMO", "contacted": 508, "replies": 10, "opps": 3, "persona": "founder", "angle": "productivity"},
    {"name": "Ecomm Agency Killer", "contacted": 647, "replies": 1, "opps": 0, "persona": "ecom-director", "angle": "replace-agency"},
    {"name": "Ecomm Founders Advisor", "contacted": 410, "replies": 4, "opps": 1, "persona": "founder", "angle": "advisor-feedback"},
    {"name": "Shopify Replace agency", "contacted": 25, "replies": 0, "opps": 0, "persona": "ecom-director", "angle": "replace-agency"},
    {"name": "SMB Owners High Intent", "contacted": 778, "replies": 0, "opps": 0, "persona": "smb-owner", "angle": "growth-without-agency"},
    {"name": "Field Services 10-50", "contacted": 574, "replies": 2, "opps": 0, "persona": "smb-owner", "angle": "automation"},
    {"name": "Field Services 3-10", "contacted": 517, "replies": 0, "opps": 0, "persona": "smb-owner", "angle": "automation"},
    {"name": "In-house Media Buyers", "contacted": 301, "replies": 2, "opps": 0, "persona": "marketing-vp", "angle": "burnout"},
    {"name": "SMB Healthcare", "contacted": 85, "replies": 1, "opps": 0, "persona": "smb-owner", "angle": "fomo-scarcity"},
    {"name": "SMB Injury Law", "contacted": 377, "replies": 1, "opps": 0, "persona": "smb-owner", "angle": "automation"},
    {"name": "Urgency Freelancers", "contacted": 437, "replies": 0, "opps": 0, "persona": "freelancer", "angle": "urgency-scarcity"},
    {"name": "Research Freelancers", "contacted": 986, "replies": 3, "opps": 1, "persona": "freelancer", "angle": "research-invite"},
    {"name": "Oliver - Claude Skills", "contacted": 246, "replies": 9, "opps": 3, "persona": "mixed", "angle": "skill-offer"},
    {"name": "Oliver - Clawdbot", "contacted": 197, "replies": 3, "opps": 1, "persona": "mixed", "angle": "tool-offer"},
    {"name": "Oliver - AdGPTs", "contacted": 103, "replies": 4, "opps": 1, "persona": "mixed", "angle": "ad-automation"},
    {"name": "Oliver - Multi-Brands", "contacted": 97, "replies": 0, "opps": 0, "persona": "ecom-director", "angle": "multi-brand"},
    {"name": "Oliver - Claude 80HRs", "contacted": 99, "replies": 1, "opps": 1, "persona": "mixed", "angle": "time-savings"},
    {"name": "Oliver - Ad Audit", "contacted": 96, "replies": 0, "opps": 0, "persona": "mixed", "angle": "free-audit"},
]

# By persona
print("=== PERSONA PERFORMANCE ===")
personas = {}
for c in data:
    p = c["persona"]
    if p not in personas:
        personas[p] = {"contacted": 0, "replies": 0, "opps": 0}
    personas[p]["contacted"] += c["contacted"]
    personas[p]["replies"] += c["replies"]
    personas[p]["opps"] += c["opps"]

for p, s in sorted(personas.items(), key=lambda x: x[1]["replies"]/max(x[1]["contacted"],1), reverse=True):
    rate = (s["replies"]/s["contacted"]*100) if s["contacted"] > 0 else 0
    print(f"  {p}: {s['contacted']} contacted, {s['replies']} replies, {rate:.1f}%, {s['opps']} opps")

# By angle
print("\n=== ANGLE PERFORMANCE (sorted by reply rate) ===")
angles = {}
for c in data:
    a = c["angle"]
    if a not in angles:
        angles[a] = {"contacted": 0, "replies": 0, "opps": 0}
    angles[a]["contacted"] += c["contacted"]
    angles[a]["replies"] += c["replies"]
    angles[a]["opps"] += c["opps"]

for a, s in sorted(angles.items(), key=lambda x: x[1]["replies"]/max(x[1]["contacted"],1), reverse=True):
    rate = (s["replies"]/s["contacted"]*100) if s["contacted"] > 0 else 0
    print(f"  {a}: {s['contacted']} contacted, {s['replies']} replies, {rate:.1f}%, {s['opps']} opps")

# Totals
total_c = sum(c["contacted"] for c in data)
total_r = sum(c["replies"] for c in data)
total_o = sum(c["opps"] for c in data)
print(f"\n=== TOTALS ===")
print(f"  {total_c} contacted, {total_r} replies ({total_r/total_c*100:.1f}%), {total_o} opportunities")
