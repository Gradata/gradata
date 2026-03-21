# Cold Email Deliverability Guide

## Why This Matters
The best cold email in the world is worthless if it hits spam. Deliverability is the foundation that everything else sits on. Get this wrong and nothing else works.

## Domain Setup
- Use a separate domain for cold outreach (e.g., spritesai.com instead of sprites.ai)
- Never send cold email from the primary domain — one spam complaint can tank deliverability for all company email
- Set up SPF, DKIM, and DMARC records on the sending domain
- Warm up new domains for 2-3 weeks before any campaign (gradual volume increase)

## Sending Volume
- Keep under 50 emails/day per sending account
- If you need higher volume, use multiple sending accounts across multiple domains
- Ramp slowly: start at 5-10/day, add 5/day each week until you hit target volume
- Never blast 100+ emails from a new account on day one

## Email Content Rules
- **Plain text only.** No HTML templates, no images, no embedded logos
- **No tracking pixels.** They trigger spam filters. Use Instantly's native tracking sparingly
- **No links in email 1.** Links are spam signals. Save for email 2+ when there's some engagement
- **Under 150 words.** Short emails look personal. Long emails look like marketing
- **Personalize the first line.** Fully generic emails get filtered by Gmail's promotions tab
- **No "unsubscribe" link in 1-to-1 emails.** CAN-SPAM applies to bulk; genuine 1-to-1 outreach doesn't require it

## List Hygiene
- **Verify every email before sending.** Use NeverBounce, ZeroBounce, or similar
- **Bounce rate must stay under 3%.** Above that, ESPs start throttling your domain
- **Remove hard bounces immediately.** Never re-send to a bounced address
- **Clean catch-all domains carefully.** These accept any email but may not have a real person behind them
- **Remove duplicates across all active sequences.** Same person getting 2 sequences = spam complaint

## Spam Trigger Words to Avoid
- "Free," "guarantee," "act now," "limited time," "click here"
- "Unsubscribe," "opt-out" (in 1-to-1 context)
- Excessive capitalization or exclamation marks
- Dollar amounts in subject lines

## Monitoring
- Check spam placement weekly using a seed list (tools: GlockApps, Mail-Tester)
- Monitor bounce rate after every campaign send
- If reply rate suddenly drops with no copy change, it's likely a deliverability issue
- If you get a spam complaint, pause the sequence immediately and investigate

## Recovery
If deliverability tanks:
1. Stop all sending immediately
2. Remove any contacts who bounced or complained
3. Warm the domain again (2 weeks minimum)
4. Start with a small, highly-targeted list of verified emails
5. Monitor closely for the first 100 sends before scaling back up
