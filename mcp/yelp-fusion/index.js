import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const API_KEY = process.env.YELP_API_KEY;
if (!API_KEY) {
  console.error("YELP_API_KEY environment variable is required");
  process.exit(1);
}

const BASE_URL = "https://api.yelp.com/v3";

async function yelpRequest(path) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      Accept: "application/json",
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Yelp API error ${res.status}: ${body}`);
  }

  return res.json();
}

function formatBusiness(biz) {
  return {
    id: biz.id || null,
    name: biz.name || null,
    rating: biz.rating || null,
    review_count: biz.review_count || null,
    phone: biz.display_phone || biz.phone || null,
    url: biz.url || null,
    address: biz.location
      ? [
          biz.location.address1,
          biz.location.address2,
          biz.location.address3,
          `${biz.location.city}, ${biz.location.state} ${biz.location.zip_code}`,
        ]
          .filter(Boolean)
          .join(", ")
      : null,
    categories: (biz.categories || []).map((c) => c.title),
    is_closed: biz.is_closed ?? null,
  };
}

function formatBusinessDetails(biz) {
  const base = formatBusiness(biz);
  base.hours = (biz.hours || []).map((h) => ({
    type: h.hours_type,
    schedule: (h.open || []).map((o) => ({
      day: o.day,
      start: o.start,
      end: o.end,
      is_overnight: o.is_overnight,
    })),
    is_open_now: h.is_open_now,
  }));
  base.photos = biz.photos || [];
  base.transactions = biz.transactions || [];
  base.price = biz.price || null;
  return base;
}

// --- MCP Server ---

const server = new McpServer({
  name: "yelp-fusion",
  version: "1.0.0",
});

// Tool 1: Business Search
server.tool(
  "yelp_search_businesses",
  "Search for businesses on Yelp. Example: term='dental group', location='Houston, TX'. Returns name, rating, review_count, phone, url, address, categories, is_closed.",
  {
    term: z
      .string()
      .optional()
      .describe("Search term, e.g. 'dental group', 'pizza', 'plumber'"),
    location: z
      .string()
      .describe("Location to search, e.g. 'Houston, TX' or '77001'"),
    categories: z
      .string()
      .optional()
      .describe(
        "Comma-separated Yelp category aliases to filter by, e.g. 'dentists,orthodontists'"
      ),
    limit: z
      .number()
      .min(1)
      .max(50)
      .default(20)
      .optional()
      .describe("Number of results to return (1-50, default 20)"),
  },
  async ({ term, location, categories, limit }) => {
    const params = new URLSearchParams();
    params.set("location", location);
    if (term) params.set("term", term);
    if (categories) params.set("categories", categories);
    if (limit) params.set("limit", String(limit));

    const data = await yelpRequest(`/businesses/search?${params.toString()}`);
    const businesses = (data.businesses || []).map(formatBusiness);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(
            { total: data.total, businesses },
            null,
            2
          ),
        },
      ],
    };
  }
);

// Tool 2: Business Details
server.tool(
  "yelp_get_business",
  "Get full details for a specific business by Yelp business ID. Returns name, rating, review_count, phone, url, address, categories, hours, photos, transactions.",
  {
    business_id: z
      .string()
      .describe(
        "The Yelp business ID from a previous search result (e.g. 'north-india-restaurant-san-francisco')"
      ),
  },
  async ({ business_id }) => {
    const data = await yelpRequest(
      `/businesses/${encodeURIComponent(business_id)}`
    );
    const details = formatBusinessDetails(data);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(details, null, 2),
        },
      ],
    };
  }
);

// Tool 3: Phone Search
server.tool(
  "yelp_search_by_phone",
  "Find a business by phone number. Useful for enrichment. Phone must include country code, e.g. '+18005551234'.",
  {
    phone: z
      .string()
      .describe(
        "Phone number with country code, e.g. '+18005551234'"
      ),
  },
  async ({ phone }) => {
    const params = new URLSearchParams();
    params.set("phone", phone);

    const data = await yelpRequest(
      `/businesses/search/phone?${params.toString()}`
    );
    const businesses = (data.businesses || []).map(formatBusiness);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(
            { total: data.total, businesses },
            null,
            2
          ),
        },
      ],
    };
  }
);

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("Server failed to start:", err);
  process.exit(1);
});
