# Google Maps Places MCP Server

MCP server for searching businesses via Google Maps Places API (New). Built for prospecting — find businesses by type and location.

## Tools

- **places_search_text** — Text search (e.g. "dental group in Houston TX"). Optional location bias.
- **places_get_details** — Full details for a place by place_id (hours, phone, website, etc.).
- **places_search_nearby** — Search near a lat/lng with a type filter (e.g. "dentist" within 10km).

## Setup

### 1. Get a Google Maps API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable **Places API (New)**
4. Create an API key under Credentials
5. Restrict the key to Places API (New) for security

### 2. Install

```bash
cd mcp/google-maps-places
npm install
```

### 3. Configure in Claude Code

Add to your Claude Code MCP settings (`~/.claude/projects/<project>/settings.json` or global `~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "google-maps-places": {
      "command": "node",
      "args": ["C:/Users/olive/OneDrive/Desktop/Sprites Work/mcp/google-maps-places/index.js"],
      "env": {
        "GOOGLE_MAPS_API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

### 4. Test

Restart Claude Code. The three tools should appear. Try:

> Find dental groups in Houston, TX

## API Reference

Uses [Google Maps Places API (New)](https://developers.google.com/maps/documentation/places/web-service/op-overview):
- Text Search: `POST /v1/places:searchText`
- Nearby Search: `POST /v1/places:searchNearby`
- Place Details: `GET /v1/places/{place_id}`
