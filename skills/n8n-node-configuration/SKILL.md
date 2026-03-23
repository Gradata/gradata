---
name: n8n-node-configuration
description: Operation-aware node configuration guidance. Use when configuring nodes, understanding property dependencies, determining required fields, choosing between get_node detail levels, or learning common configuration patterns by node type.
---

# n8n Node Configuration

Expert guidance for operation-aware node configuration with property dependencies.

---

## Configuration Philosophy

**Progressive disclosure**: Start minimal, add complexity as needed

Configuration best practices:
- `get_node` with `detail: "standard"` is the most used discovery pattern
- 56 seconds average between configuration edits
- Covers 95% of use cases with 1-2K tokens response

**Key insight**: Most configurations need only standard detail, not full schema!

---

## Core Concepts

### 1. Operation-Aware Configuration

**Not all fields are always required** - it depends on operation!

**Example**: Slack node
```javascript
// For operation='post'
{
  "resource": "message",
  "operation": "post",
  "channel": "#general",  // Required for post
  "text": "Hello!"        // Required for post
}

// For operation='update'
{
  "resource": "message",
  "operation": "update",
  "messageId": "123",     // Required for update (different!)
  "text": "Updated!"      // Required for update
  // channel NOT required for update
}
```

**Key**: Resource + operation determine which fields are required!

### 2. Property Dependencies

**Fields appear/disappear based on other field values**

**Example**: HTTP Request node
```javascript
// When method='GET'
{
  "method": "GET",
  "url": "https://api.example.com"
  // sendBody not shown (GET doesn't have body)
}

// When method='POST'
{
  "method": "POST",
  "url": "https://api.example.com",
  "sendBody": true,       // Now visible!
  "body": {               // Required when sendBody=true
    "contentType": "json",
    "content": {...}
  }
}
```

**Mechanism**: displayOptions control field visibility

### 3. Progressive Discovery

**Use the right detail level**:

1. **get_node({detail: "standard"})** - DEFAULT
   - Quick overview (~1-2K tokens)
   - Required fields + common options
   - **Use first** - covers 95% of needs

2. **get_node({mode: "search_properties", propertyQuery: "..."})** (for finding specific fields)
   - Find properties by name
   - Use when looking for auth, body, headers, etc.

3. **get_node({detail: "full"})** (complete schema)
   - All properties (~3-8K tokens)
   - Use only when standard detail is insufficient

---

## Configuration Workflow

### Standard Process

```
1. Identify node type and operation
   ↓
2. Use get_node (standard detail is default)
   ↓
3. Configure required fields
   ↓
4. Validate configuration
   ↓
5. If field unclear → get_node({mode: "search_properties"})
   ↓
6. Add optional fields as needed
   ↓
7. Validate again
   ↓
8. Deploy
```

### Example: Configuring HTTP Request

**Step 1**: Identify what you need
```javascript
// Goal: POST JSON to API
```

**Step 2**: Get node info
```javascript
const info = get_node({
  nodeType: "nodes-base.httpRequest"
});

// Returns: method, url, sendBody, body, authentication required/optional
```

**Step 3**: Minimal config
```javascript
{
  "method": "POST",
  "url": "https://api.example.com/create",
  "authentication": "none"
}
```

**Step 4**: Validate
```javascript
validate_node({
  nodeType: "nodes-base.httpRequest",
  config,
  profile: "runtime"
});
// → Error: "sendBody required for POST"
```

**Step 5**: Add required field
```javascript
{
  "method": "POST",
  "url": "https://api.example.com/create",
  "authentication": "none",
  "sendBody": true
}
```

**Step 6**: Validate again
```javascript
validate_node({...});
// → Error: "body required when sendBody=true"
```

**Step 7**: Complete configuration
```javascript
{
  "method": "POST",
  "url": "https://api.example.com/create",
  "authentication": "none",
  "sendBody": true,
  "body": {
    "contentType": "json",
    "content": {
      "name": "={{$json.name}}",
      "email": "={{$json.email}}"
    }
  }
}
```

**Step 8**: Final validation
```javascript
validate_node({...});
// → Valid! ✅
```

---

## get_node Detail Levels

### Standard Detail (DEFAULT - Use This!)

**✅ Starting configuration**
```javascript
get_node({
  nodeType: "nodes-base.slack"
});
// detail="standard" is the default
```

**Returns** (~1-2K tokens):
- Required fields
- Common options
- Operation list
- Metadata

**Use**: 95% of configuration needs

### Full Detail (Use Sparingly)

**✅ When standard isn't enough**
```javascript
get_node({
  nodeType: "nodes-base.slack",
  detail: "full"
});
```

**Returns** (~3-8K tokens):
- Complete schema
- All properties
- All nested options

**Warning**: Large response, use only when standard insufficient

### Search Properties Mode

**✅ Looking for specific field**
```javascript
get_node({
  nodeType: "nodes-base.httpRequest",
  mode: "search_properties",
  propertyQuery: "auth"
});
```

**Use**: Find authentication, headers, body fields, etc.

**Escalation path**: standard (default) -> search_properties (specific field) -> full detail (only if needed)

---

## Property Dependencies Deep Dive

### displayOptions Mechanism

**Fields have visibility rules**:

```javascript
{
  "name": "body",
  "displayOptions": {
    "show": {
      "sendBody": [true],
      "method": ["POST", "PUT", "PATCH"]
    }
  }
}
```

**Translation**: "body" field shows when:
- sendBody = true AND
- method = POST, PUT, or PATCH

### Common Dependency Patterns

| Pattern | Example | Mechanism |
|---------|---------|-----------|
| **Boolean Toggle** | `sendBody: true` shows `body` field | Single field controls visibility |
| **Operation Switch** | Slack `post` needs channel+text; `update` needs messageId+text | Resource+operation determine fields |
| **Type Selection** | IF node: string/boolean types show different operators | Type field changes available options |

### Finding Property Dependencies

```javascript
// Search for specific property
get_node({nodeType: "nodes-base.httpRequest", mode: "search_properties", propertyQuery: "body"});

// Or get full schema with all displayOptions rules
get_node({nodeType: "nodes-base.httpRequest", detail: "full"});
```

**Use when**: Validation fails and you don't understand why a field is missing/required

---

## Common Node Patterns

### Pattern 1: Resource/Operation Nodes

**Examples**: Slack, Google Sheets, Airtable

**Structure**:
```javascript
{
  "resource": "<entity>",      // What type of thing
  "operation": "<action>",     // What to do with it
  // ... operation-specific fields
}
```

**How to configure**:
1. Choose resource
2. Choose operation
3. Use get_node to see operation-specific requirements
4. Configure required fields

### Pattern 2: HTTP-Based Nodes

**Examples**: HTTP Request, Webhook

**Structure**:
```javascript
{
  "method": "<HTTP_METHOD>",
  "url": "<endpoint>",
  "authentication": "<type>",
  // ... method-specific fields
}
```

**Dependencies**:
- POST/PUT/PATCH → sendBody available
- sendBody=true → body required
- authentication != "none" → credentials required

### Pattern 3: Database Nodes

**Examples**: Postgres, MySQL, MongoDB

**Structure**:
```javascript
{
  "operation": "<query|insert|update|delete>",
  // ... operation-specific fields
}
```

**Dependencies**:
- operation="executeQuery" → query required
- operation="insert" → table + values required
- operation="update" → table + values + where required

### Pattern 4: Conditional Logic Nodes

**Examples**: IF, Switch, Merge

**Structure**:
```javascript
{
  "conditions": {
    "<type>": [
      {
        "operation": "<operator>",
        "value1": "...",
        "value2": "..."  // Only for binary operators
      }
    ]
  }
}
```

**Dependencies**:
- Binary operators (equals, contains, etc.) → value1 + value2
- Unary operators (isEmpty, isNotEmpty) → value1 only + singleValue: true

---

## Handling Conditional Requirements

Discover conditional field requirements through:
1. **Validation errors**: `validate_node({...})` tells you what's missing and when
2. **Property search**: `get_node({mode: "search_properties", propertyQuery: "body"})` shows displayOptions rules
3. **Iterative config**: Start minimal, validation guides you to add what's needed

**Common conditional rules**:
- HTTP Request: `body` required when `sendBody=true` AND method IN (POST, PUT, PATCH, DELETE)
- IF node: `singleValue=true` for unary operators (isEmpty, isNotEmpty) -- auto-sanitization handles this
- Slack: Different operations require different fields (post needs channel+text, update needs messageId+text)

---

## Configuration Anti-Patterns

- **Over-configuring upfront**: Start minimal (method + url + auth), add fields only when validation tells you they're needed
- **Skipping validation**: Always `validate_node()` before deploying -- never YOLO
- **Ignoring operation context**: Different operations need different fields. Always re-check `get_node()` when changing operation

---

## Best Practices

### Do
- Start with `get_node` (standard detail, default) -- covers 95% of needs
- Validate iteratively: configure -> validate -> fix -> repeat (2-3 cycles normal)
- Use `search_properties` mode when a field seems missing or conditionally required
- Respect operation context: different operations = different required fields
- Trust auto-sanitization for operator structure (singleValue, IF/Switch metadata)

### Don't
- Jump to `detail="full"` immediately (3-8K tokens; try standard first)
- Configure blindly without validation
- Copy configs between operations without re-checking requirements
- Manually fix auto-sanitization issues

---

**Detailed References**: [DEPENDENCIES.md](DEPENDENCIES.md) | [OPERATION_PATTERNS.md](OPERATION_PATTERNS.md)
