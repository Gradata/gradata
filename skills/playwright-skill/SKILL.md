---
name: playwright-skill
description: Use when user wants to General-purpose browser automation with Playwright. Use for prospect website research, tech stack detection, ad verification, screenshot capture, and any browser-based scraping task. Do NOT use for Google Ads Transparency or Meta Ad Library (use APIs instead). Triggers on "scrape", "check their website", "screenshot", "what tech do they use", "browser automation".
---

# Playwright Browser Automation Skill

Complete browser automation with Playwright. Auto-detects dev servers, writes clean scripts to /tmp.

## Setup (one-time)

```bash
cd "C:/Users/olive/OneDrive/Desktop/Sprites Work/skills/playwright-skill"
npm install
npx playwright install chromium
```

## Core Workflow

1. **Write script** to `/tmp/playwright-test-*.js`
2. **Execute** via `node run.js /tmp/playwright-test-*.js`
3. **Return** console output + screenshots

## Configuration

- Browser: Chromium, visible by default (`headless: false`)
- Slow motion: 100ms (prevents bot detection)
- Timeout: 30 seconds
- Screenshots: saved to `/tmp/`

## Use Cases for Sprites Prospecting

### Check prospect website tech stack
```javascript
const { chromium } = require('playwright');
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto('https://[prospect-domain]');
// Check for Meta Pixel
const metaPixel = await page.evaluate(() => typeof fbq !== 'undefined');
// Check for Google Analytics
const ga = await page.evaluate(() => typeof gtag !== 'undefined' || typeof ga !== 'undefined');
// Check for Shopify
const shopify = await page.evaluate(() => typeof Shopify !== 'undefined');
console.log({ metaPixel, ga, shopify });
await browser.close();
```

### Screenshot prospect homepage
```javascript
const { chromium } = require('playwright');
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto('https://[prospect-domain]', { waitUntil: 'networkidle' });
await page.screenshot({ path: '/tmp/prospect-screenshot.png', fullPage: true });
await browser.close();
```

### Check if prospect is running Google Ads
```javascript
// Scrape their site for Google Ads conversion tracking
const { chromium } = require('playwright');
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto('https://[prospect-domain]');
const scripts = await page.evaluate(() =>
  Array.from(document.querySelectorAll('script')).map(s => s.src || s.textContent.substring(0, 200))
);
const hasGoogleAds = scripts.some(s => s.includes('googleadservices') || s.includes('conversion') || s.includes('AW-'));
console.log({ hasGoogleAds, adScripts: scripts.filter(s => s.includes('google')) });
await browser.close();
```

## Rules
- Always use `headless: true` for prospecting (no need for visible browser)
- Clean up browser instances (`await browser.close()`)
- Don't scrape Google Ads Transparency Center or Meta Ad Library — use their APIs
- Don't scrape LinkedIn — per Oliver's rule
- Rate limit: 1 request per 2 seconds to any single domain
