import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import wappalyzer from "simple-wappalyzer";

// Key marketing signals we highlight when detected
const MARKETING_SIGNALS = {
  "Facebook Pixel": "Running Meta/Facebook ads",
  "Meta Pixel": "Running Meta/Facebook ads",
  "Google Ads": "Running Google Ads",
  "Google Ads Conversion Tracking": "Running Google Ads",
  "Google Analytics": "Tracking digital marketing (GA)",
  "GA4": "Tracking digital marketing (GA4)",
  "Google Tag Manager": "Marketing team active (GTM)",
  "Shopify": "Shopify ecommerce platform",
  "WooCommerce": "WooCommerce ecommerce (WordPress)",
  "WordPress": "WordPress CMS",
  "Klaviyo": "Email marketing via Klaviyo",
  "HubSpot": "HubSpot CRM / marketing",
  "Mailchimp": "Email marketing via Mailchimp",
  "Hotjar": "User behavior analytics (Hotjar)",
  "Intercom": "Live chat / customer support",
  "Drift": "Conversational marketing",
  "Salesforce": "Salesforce CRM",
  "Marketo": "Marketing automation (Marketo)",
  "Pardot": "B2B marketing automation (Pardot)",
  "ActiveCampaign": "Email/marketing automation",
  "Segment": "Customer data platform (Segment)",
  "Mixpanel": "Product analytics (Mixpanel)",
  "Amplitude": "Product analytics (Amplitude)",
  "Heap": "Product analytics (Heap)",
  "TikTok Pixel": "Running TikTok ads",
  "LinkedIn Insight Tag": "Running LinkedIn ads",
  "Pinterest Tag": "Running Pinterest ads",
  "Snapchat Pixel": "Running Snapchat ads",
};

async function fetchPage(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch(url, {
      signal: controller.signal,
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        Accept:
          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
      },
      redirect: "follow",
    });

    const html = await response.text();

    // Convert headers to plain object
    const headers = {};
    response.headers.forEach((value, key) => {
      headers[key] = value;
    });

    return {
      url: response.url,
      html,
      statusCode: response.status,
      headers,
    };
  } finally {
    clearTimeout(timeout);
  }
}

function normalizeUrl(domain) {
  let url = domain.trim();
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    url = "https://" + url;
  }
  // Strip trailing slash for consistency
  return url.replace(/\/+$/, "");
}

function formatResults(result, domain) {
  const apps = result.applications || result.technologies || [];

  if (apps.length === 0) {
    return `No technologies detected for ${domain}.\n\nThis can happen if the site blocks automated requests, uses heavy client-side rendering, or has minimal detectable fingerprints.`;
  }

  // Group by category
  const byCategory = {};
  const signals = [];

  for (const app of apps) {
    const name = app.name;
    const version = app.version ? ` ${app.version}` : "";
    const confidence = app.confidence ? ` (${app.confidence}%)` : "";
    const label = `${name}${version}${confidence}`;

    // Check for marketing signals
    if (MARKETING_SIGNALS[name]) {
      signals.push(`  → ${name}: ${MARKETING_SIGNALS[name]}`);
    }

    // Extract category names
    const cats = app.categories || [];
    for (const cat of cats) {
      // categories can be [{id: name}] or [{name: ...}] depending on version
      let catName;
      if (typeof cat === "object") {
        catName = cat.name || Object.values(cat)[0] || "Other";
      } else {
        catName = String(cat);
      }
      if (!byCategory[catName]) byCategory[catName] = [];
      byCategory[catName].push(label);
    }

    // If no categories, put in Other
    if (cats.length === 0) {
      if (!byCategory["Other"]) byCategory["Other"] = [];
      byCategory["Other"].push(label);
    }
  }

  let output = `Tech Stack: ${domain}\n`;
  output += `${"=".repeat(40)}\n\n`;

  // Marketing signals first if any
  if (signals.length > 0) {
    output += `MARKETING SIGNALS:\n`;
    output += signals.join("\n") + "\n\n";
  }

  // Sort categories alphabetically
  const sortedCats = Object.keys(byCategory).sort();
  for (const cat of sortedCats) {
    output += `${cat}:\n`;
    for (const tech of byCategory[cat]) {
      output += `  - ${tech}\n`;
    }
    output += "\n";
  }

  output += `Total: ${apps.length} technologies detected`;
  return output;
}

// Create MCP server
const server = new McpServer({
  name: "wappalyzer",
  version: "1.0.0",
});

server.tool(
  "techstack_lookup",
  "Detect technologies used by a website (CMS, analytics, ads, frameworks, etc). Returns categorized tech stack with marketing signal highlights.",
  {
    domain: z
      .string()
      .describe(
        'Domain to analyze, e.g. "example.com" or "https://example.com"'
      ),
  },
  async ({ domain }) => {
    try {
      const url = normalizeUrl(domain);
      const pageData = await fetchPage(url);
      const result = await wappalyzer(pageData);
      const formatted = formatResults(result, domain);

      return {
        content: [{ type: "text", text: formatted }],
      };
    } catch (error) {
      let message = `Failed to analyze ${domain}: ${error.message}`;

      if (error.name === "AbortError") {
        message = `Timeout: ${domain} did not respond within 15 seconds.`;
      } else if (error.code === "ENOTFOUND") {
        message = `Domain not found: ${domain}. Check spelling.`;
      } else if (error.code === "ECONNREFUSED") {
        message = `Connection refused by ${domain}.`;
      }

      return {
        content: [{ type: "text", text: message }],
        isError: true,
      };
    }
  }
);

// Start server
const transport = new StdioServerTransport();
await server.connect(transport);
