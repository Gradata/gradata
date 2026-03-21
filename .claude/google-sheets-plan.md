# Google Sheets Integration Plan
# Status: APPROVED by Oliver 2026-03-17 | Pending: test Rube MCP next session
# Connected via: Rube MCP (claude mcp add rube --transport http https://rube.app/mcp)

## 1. Live Pipeline Dashboard (replaces static docs/startup-brief.md tables)
- One master Sheet with prospect name, stage, last touch, next step, ICP score, days since contact
- Oliver can check from his phone anytime
- Updated automatically after every session during wrap-up
- Replaces the pipeline section of docs/startup-brief.md (brief still has the text summary, Sheet has the live data)

## 2. Apify Scrape → Sheet → Enrichment Pipeline (BIGGEST WIN)
- Apify scrape output goes directly into a Google Sheet (not just a local CSV)
- ICP-score every row in the sheet, flag the best leads
- Export the top-scored rows to Prospeo-ready CSV
- Track enrichment status per row: scraped → ICP scored → enriched → verified → sent
- Full funnel visible at a glance without opening CSVs
- Replaces the current CSV-juggling workflow

## 3. Campaign Tracking
- One Sheet per campaign (like claude-code-80hrs)
- Tabs: Raw Commenters | ICP Matched | Enriched | Verified | Sent | Replied
- Real-time counts instead of checking Leads/STATUS.md
- Historical campaigns archived as separate Sheets

## 4. NotebookLM Feed Log
- Track what was fed into each notebook, when, from which call
- Quality-loop skill reads this to check "was this call's data actually fed back?"
- Replaces scanning file directories in docs/Exports/notebook-feeds/

## 5. Weekly Metrics
- Automated weekly row: emails sent, demos booked, deals progressed, calls made
- Quality-loop skill reads this to grade performance over time
- Rolling 4-week view for trend analysis

## Implementation Order (next session with Sheets access)
1. Test Rube MCP connectivity
2. Create Pipeline Dashboard sheet
3. Create claude-code-80hrs campaign sheet with tabs
4. Wire LISTBUILD CARL domain to write to Sheets
5. Wire wrap-up skill to update Pipeline Dashboard
6. Create NotebookLM feed log sheet
7. Create Weekly Metrics sheet
