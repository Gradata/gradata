---
name: lead-pipeline
description: Use when user wants to Manage the lead enrichment-to-send pipeline — from raw CSV to Prospeo enrichment to ZeroBounce verification to Instantly import. Use this skill whenever Oliver says "run the pipeline", "enrich batch", "next batch", "process leads", "clean the results", "upload to Instantly", "ZeroBounce results", or references moving leads through any stage of the enrichment pipeline. Also trigger when Oliver drops a CSV file path or says "I got the results back" from Prospeo or ZeroBounce.
---

# Lead Pipeline Automation

## Why This Exists
Lead campaigns go through a multi-step pipeline: raw list → Prospeo enrichment → ZeroBounce verification → Instantly import. Each step has specific file formats and handoff points. This skill tracks where each batch is and handles the data prep at each stage so Oliver just needs to upload/download from each tool.

## Pipeline Steps

### Step 1: Prep Next Batch
- Read `Leads/STATUS.md` and `Leads/wip/` to find the active campaign
- Check `Leads/enriched/` for which batches are already processed
- Build a Prospeo-ready CSV: First Name, Last Name, Company Domain, LinkedIn URL, Company
- Save to `Leads/enriched/prospeo_batchN_ready.csv`
- Tell Oliver: "Batch N ready — upload to Prospeo"

### Step 2: Post-Prospeo Cleanup
When Oliver has Prospeo results:
- Read the enriched CSV from wherever Oliver saved it
- Clean malformed rows (empty emails, broken formatting, duplicates)
- Save clean version to `Leads/enriched/prospeo_enriched_clean_batchN.csv`
- Tell Oliver: "Cleaned. Upload to ZeroBounce for verification."

### Step 3: Post-ZeroBounce Organization
When Oliver has ZeroBounce results:
- Move files from Downloads to `Leads/enriched/batchN_zerobounce/`
- Rename to clean names: `valid.csv`, `invalid.csv`, `catch_all.csv`
- Tell Oliver: "Valid file ready — upload to Instantly"

### Step 4: Track & Update
- Update Prospeo credit count in `docs/startup-brief.md`
- Log batch completion in `Leads/STATUS.md`
- Note how many valid/invalid/catch-all in the daily note

## Auto-Detect
If Oliver drops a file path or says "got results", figure out which step we're at by checking:
1. File contents (does it have Prospeo enrichment columns? ZeroBounce status columns?)
2. What's already in `Leads/enriched/`
3. `Leads/STATUS.md` for last known state

## Error Handling
- If a CSV has unexpected format, show Oliver a sample of rows and ask for clarification
- If files are in Downloads instead of Sprites Work, move them automatically
- If STATUS.md is missing or stale, rebuild it from what's in `Leads/enriched/`
