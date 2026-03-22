import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const API_KEY = process.env.GOOGLE_MAPS_API_KEY;
if (!API_KEY) {
  console.error("GOOGLE_MAPS_API_KEY environment variable is required");
  process.exit(1);
}

const BASE_URL = "https://places.googleapis.com/v1";

const SEARCH_FIELD_MASK = [
  "places.displayName",
  "places.formattedAddress",
  "places.nationalPhoneNumber",
  "places.websiteUri",
  "places.rating",
  "places.userRatingCount",
  "places.id",
  "places.types",
  "places.googleMapsUri",
].join(",");

const DETAIL_FIELD_MASK = [
  "displayName",
  "formattedAddress",
  "nationalPhoneNumber",
  "websiteUri",
  "rating",
  "userRatingCount",
  "id",
  "types",
  "googleMapsUri",
  "currentOpeningHours",
  "regularOpeningHours",
].join(",");

function formatPlace(place) {
  return {
    name: place.displayName?.text || null,
    address: place.formattedAddress || null,
    phone: place.nationalPhoneNumber || null,
    website: place.websiteUri || null,
    rating: place.rating || null,
    review_count: place.userRatingCount || null,
    place_id: place.id || null,
    types: place.types || [],
    google_maps_url: place.googleMapsUri || null,
  };
}

function formatPlaceDetails(place) {
  const base = formatPlace(place);
  const hours = place.currentOpeningHours || place.regularOpeningHours;
  base.opening_hours = hours?.weekdayDescriptions || null;
  return base;
}

async function apiRequest(url, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": API_KEY,
    ...options.headers,
  };

  const res = await fetch(url, { ...options, headers });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Google Places API error ${res.status}: ${body}`);
  }

  return res.json();
}

// --- MCP Server ---

const server = new McpServer({
  name: "google-maps-places",
  version: "1.0.0",
});

// Tool 1: Text Search
server.tool(
  "places_search_text",
  "Search for businesses by text query. Example: 'dental group in Houston TX'. Returns name, address, phone, website, rating, review count, place_id, types.",
  {
    query: z.string().describe("Search query, e.g. 'dental group in Houston TX'"),
    location_bias: z
      .object({
        latitude: z.number().describe("Latitude for location bias"),
        longitude: z.number().describe("Longitude for location bias"),
        radius_meters: z
          .number()
          .default(50000)
          .describe("Radius in meters for location bias (default 50000)"),
      })
      .optional()
      .describe("Optional location bias to prefer results near a point"),
  },
  async ({ query, location_bias }) => {
    const body = { textQuery: query };

    if (location_bias) {
      body.locationBias = {
        circle: {
          center: {
            latitude: location_bias.latitude,
            longitude: location_bias.longitude,
          },
          radius: location_bias.radius_meters || 50000,
        },
      };
    }

    const data = await apiRequest(`${BASE_URL}/places:searchText`, {
      method: "POST",
      headers: { "X-Goog-FieldMask": SEARCH_FIELD_MASK },
      body: JSON.stringify(body),
    });

    const places = (data.places || []).map(formatPlace);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(places, null, 2),
        },
      ],
    };
  }
);

// Tool 2: Place Details
server.tool(
  "places_get_details",
  "Get full details for a specific place by place_id. Returns name, address, phone, website, rating, review_count, opening_hours, types, Google Maps link.",
  {
    place_id: z
      .string()
      .describe("The place ID from a previous search result (e.g. 'ChIJ...')"),
  },
  async ({ place_id }) => {
    // Place IDs from the new API come as "places/XXXX" or just the ID
    const resourceName = place_id.startsWith("places/")
      ? place_id
      : `places/${place_id}`;

    const data = await apiRequest(`${BASE_URL}/${resourceName}`, {
      method: "GET",
      headers: { "X-Goog-FieldMask": DETAIL_FIELD_MASK },
    });

    const details = formatPlaceDetails(data);

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

// Tool 3: Nearby Search
server.tool(
  "places_search_nearby",
  "Search for places near a latitude/longitude. Requires a type filter (e.g. 'restaurant', 'dentist', 'car_repair'). Returns name, address, phone, website, rating, review count, place_id, types.",
  {
    latitude: z.number().describe("Latitude of the center point"),
    longitude: z.number().describe("Longitude of the center point"),
    radius_meters: z
      .number()
      .default(5000)
      .describe("Search radius in meters (default 5000, max 50000)"),
    type: z
      .string()
      .describe(
        "Place type to filter by, e.g. 'restaurant', 'dentist', 'car_repair'. See Google Places types."
      ),
  },
  async ({ latitude, longitude, radius_meters, type }) => {
    const body = {
      includedTypes: [type],
      locationRestriction: {
        circle: {
          center: { latitude, longitude },
          radius: radius_meters || 5000,
        },
      },
    };

    const data = await apiRequest(`${BASE_URL}/places:searchNearby`, {
      method: "POST",
      headers: { "X-Goog-FieldMask": SEARCH_FIELD_MASK },
      body: JSON.stringify(body),
    });

    const places = (data.places || []).map(formatPlace);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(places, null, 2),
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
