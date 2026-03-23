---
name: n8n-code-javascript
description: Use when writing JavaScript in n8n Code nodes — $input/$json/$node syntax, $helpers.httpRequest(), Luxon DateTime, Code node mode selection, or troubleshooting JS Code node errors. For Python in n8n, use n8n-code-python. For expression syntax in non-code fields, use n8n-expression-syntax.
---

# JavaScript Code Node

Expert guidance for writing JavaScript code in n8n Code nodes.

---

## Quick Start

```javascript
// Basic template for Code nodes
const items = $input.all();

// Process data
const processed = items.map(item => ({
  json: {
    ...item.json,
    processed: true,
    timestamp: new Date().toISOString()
  }
}));

return processed;
```

### Essential Rules

1. **Choose "Run Once for All Items" mode** (recommended for most use cases)
2. **Access data**: `$input.all()`, `$input.first()`, or `$input.item`
3. **CRITICAL**: Must return `[{json: {...}}]` format
4. **CRITICAL**: Webhook data is under `$json.body` (not `$json` directly)
5. **Built-ins available**: $helpers.httpRequest(), DateTime (Luxon), $jmespath()

---

## Mode Selection Guide

The Code node offers two execution modes. Choose based on your use case:

### Run Once for All Items (Recommended - Default)

**Use this mode for:** 95% of use cases

- **How it works**: Code executes **once** regardless of input count
- **Data access**: `$input.all()` or `items` array
- **Best for**: Aggregation, filtering, batch processing, transformations, API calls with all data
- **Performance**: Faster for multiple items (single execution)

```javascript
// Example: Calculate total from all items
const allItems = $input.all();
const total = allItems.reduce((sum, item) => sum + (item.json.amount || 0), 0);

return [{
  json: {
    total,
    count: allItems.length,
    average: total / allItems.length
  }
}];
```

**When to use:**
- ✅ Comparing items across the dataset
- ✅ Calculating totals, averages, or statistics
- ✅ Sorting or ranking items
- ✅ Deduplication
- ✅ Building aggregated reports
- ✅ Combining data from multiple items

### Run Once for Each Item

**Use this mode for:** Specialized cases only

- **How it works**: Code executes **separately** for each input item
- **Data access**: `$input.item` or `$item`
- **Best for**: Item-specific logic, independent operations, per-item validation
- **Performance**: Slower for large datasets (multiple executions)

```javascript
// Example: Add processing timestamp to each item
const item = $input.item;

return [{
  json: {
    ...item.json,
    processed: true,
    processedAt: new Date().toISOString()
  }
}];
```

**When to use:**
- ✅ Each item needs independent API call
- ✅ Per-item validation with different error handling
- ✅ Item-specific transformations based on item properties
- ✅ When items must be processed separately for business logic

**Decision Shortcut:**
- **Need to look at multiple items?** → Use "All Items" mode
- **Each item completely independent?** → Use "Each Item" mode
- **Not sure?** → Use "All Items" mode (you can always loop inside)

---

## Data Access Patterns

### Pattern 1: $input.all() - Most Common

**Use when**: Processing arrays, batch operations, aggregations

```javascript
// Get all items from previous node
const allItems = $input.all();

// Filter, map, reduce as needed
const valid = allItems.filter(item => item.json.status === 'active');
const mapped = valid.map(item => ({
  json: {
    id: item.json.id,
    name: item.json.name
  }
}));

return mapped;
```

### Pattern 2: $input.first() - Very Common

**Use when**: Working with single objects, API responses, first-in-first-out

```javascript
// Get first item only
const firstItem = $input.first();
const data = firstItem.json;

return [{
  json: {
    result: processData(data),
    processedAt: new Date().toISOString()
  }
}];
```

### Pattern 3: $input.item - Each Item Mode Only

**Use when**: In "Run Once for Each Item" mode

```javascript
// Current item in loop (Each Item mode only)
const currentItem = $input.item;

return [{
  json: {
    ...currentItem.json,
    itemProcessed: true
  }
}];
```

### Pattern 4: $node - Reference Other Nodes

**Use when**: Need data from specific nodes in workflow

```javascript
// Get output from specific node
const webhookData = $node["Webhook"].json;
const httpData = $node["HTTP Request"].json;

return [{
  json: {
    combined: {
      webhook: webhookData,
      api: httpData
    }
  }
}];
```

**See**: [DATA_ACCESS.md](DATA_ACCESS.md) for comprehensive guide

---

## Critical: Webhook Data Structure

**MOST COMMON MISTAKE**: Webhook data is nested under `.body`

```javascript
// ❌ WRONG - Will return undefined
const name = $json.name;
const email = $json.email;

// ✅ CORRECT - Webhook data is under .body
const name = $json.body.name;
const email = $json.body.email;

// Or with $input
const webhookData = $input.first().json.body;
const name = webhookData.name;
```

**Why**: Webhook node wraps all request data under `body` property. This includes POST data, query parameters, and JSON payloads.

**See**: [DATA_ACCESS.md](DATA_ACCESS.md) for full webhook structure details

---

## Return Format Requirements

**CRITICAL RULE**: Always return array of objects with `json` property

### Correct Return Formats

```javascript
// ✅ Single result
return [{
  json: {
    field1: value1,
    field2: value2
  }
}];

// ✅ Multiple results
return [
  {json: {id: 1, data: 'first'}},
  {json: {id: 2, data: 'second'}}
];

// ✅ Transformed array
const transformed = $input.all()
  .filter(item => item.json.valid)
  .map(item => ({
    json: {
      id: item.json.id,
      processed: true
    }
  }));
return transformed;

// ✅ Empty result (when no data to return)
return [];

// ✅ Conditional return
if (shouldProcess) {
  return [{json: processedData}];
} else {
  return [];
}
```

**Common mistakes**: returning `{json: {}}` without array wrapper, returning `[{field: value}]` without json key, returning plain strings. All cause workflow failures.

**See**: [ERROR_PATTERNS.md](ERROR_PATTERNS.md) and [COMMON_PATTERNS.md](COMMON_PATTERNS.md) for detailed patterns (aggregation, regex filtering, transformation, ranking, reporting).

---

## Error Prevention - Top 5 Mistakes

### #1: Empty Code or Missing Return (Most Common)

```javascript
// ❌ WRONG: No return statement
const items = $input.all();
// ... processing code ...
// Forgot to return!

// ✅ CORRECT: Always return data
const items = $input.all();
// ... processing ...
return items.map(item => ({json: item.json}));
```

### #2: Expression Syntax Confusion
Use `$input.first().json.field` or template literals `` `${$json.field}` `` — never `{{ }}` in Code nodes.

### #3: Incorrect Return Wrapper
Must return `[{json: {...}}]` — array of objects with json key. No bare objects or arrays.

### #4: Missing Null Checks
Use optional chaining: `item.json?.user?.email || 'fallback'`

### #5: Webhook Body Nesting
Webhook data lives under `$json.body`, not `$json` directly.

**See**: [ERROR_PATTERNS.md](ERROR_PATTERNS.md) for comprehensive error guide

---

## Built-in Functions & Helpers

### $helpers.httpRequest()

Make HTTP requests from within code:

```javascript
const response = await $helpers.httpRequest({
  method: 'GET',
  url: 'https://api.example.com/data',
  headers: {
    'Authorization': 'Bearer token',
    'Content-Type': 'application/json'
  }
});

return [{json: {data: response}}];
```

### DateTime (Luxon)

Date and time operations:

```javascript
// Current time
const now = DateTime.now();

// Format dates
const formatted = now.toFormat('yyyy-MM-dd');
const iso = now.toISO();

// Date arithmetic
const tomorrow = now.plus({days: 1});
const lastWeek = now.minus({weeks: 1});

return [{
  json: {
    today: formatted,
    tomorrow: tomorrow.toFormat('yyyy-MM-dd')
  }
}];
```

### $jmespath()

Query JSON structures:

```javascript
const data = $input.first().json;

// Filter array
const adults = $jmespath(data, 'users[?age >= `18`]');

// Extract fields
const names = $jmespath(data, 'users[*].name');

return [{json: {adults, names}}];
```

**See**: [BUILTIN_FUNCTIONS.md](BUILTIN_FUNCTIONS.md) for complete reference

---

## Best Practices

### 1. Always Validate Input Data

```javascript
const items = $input.all();

// Check if data exists
if (!items || items.length === 0) {
  return [];
}

// Validate structure
if (!items[0].json) {
  return [{json: {error: 'Invalid input format'}}];
}

// Continue processing...
```

### 2. Use Try-Catch for Error Handling

```javascript
try {
  const response = await $helpers.httpRequest({
    url: 'https://api.example.com/data'
  });

  return [{json: {success: true, data: response}}];
} catch (error) {
  return [{
    json: {
      success: false,
      error: error.message
    }
  }];
}
```

### 3. Prefer Array Methods Over Loops
Use `.filter().map()` over manual loops. Filter early, process late.

### 4. Debug with console.log()
Debug statements appear in browser console (F12). Use `console.log()` to inspect data.

---

## When to Use Code Node

Use Code node when:
- ✅ Complex transformations requiring multiple steps
- ✅ Custom calculations or business logic
- ✅ Recursive operations
- ✅ API response parsing with complex structure
- ✅ Multi-step conditionals
- ✅ Data aggregation across items

Consider other nodes when:
- ❌ Simple field mapping → Use **Set** node
- ❌ Basic filtering → Use **Filter** node
- ❌ Simple conditionals → Use **IF** or **Switch** node
- ❌ HTTP requests only → Use **HTTP Request** node

**Code node excels at**: Complex logic that would require chaining many simple nodes

---

## Quick Reference Checklist

Before deploying Code nodes, verify:

- [ ] Return statement exists — returns `[{json: {...}}]`
- [ ] Data access correct — `$input.all()`, `$input.first()`, or `$input.item`
- [ ] No `{{ }}` expressions — use JS template literals
- [ ] Null checks with optional chaining
- [ ] Webhook data accessed via `.body`
- [ ] Mode set to "All Items" (unless per-item logic needed)

## Related Files
- [DATA_ACCESS.md](DATA_ACCESS.md) | [COMMON_PATTERNS.md](COMMON_PATTERNS.md) | [ERROR_PATTERNS.md](ERROR_PATTERNS.md) | [BUILTIN_FUNCTIONS.md](BUILTIN_FUNCTIONS.md)
- n8n docs: https://docs.n8n.io/code/code-node/ | Luxon: https://moment.github.io/luxon/
