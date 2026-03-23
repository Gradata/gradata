---
name: n8n-validation-expert
description: Interpret validation errors and guide fixing them. Use when encountering validation errors, validation warnings, false positives, operator structure issues, or need help understanding validation results. Also use when asking about validation profiles, error types, or the validation loop process.
---

# n8n Validation Expert

Expert guide for interpreting and fixing n8n validation errors.

---

## Validation Philosophy

**Validate early, validate often**

Validation is typically iterative:
- Expect validation feedback loops
- Usually 2-3 validate → fix cycles
- Average: 23s thinking about errors, 58s fixing them

**Key insight**: Validation is an iterative process, not one-shot!

---

## Error Severity Levels

### 1. Errors (Must Fix)
**Blocks workflow execution** - Must be resolved before activation

**Types**:
- `missing_required` - Required field not provided
- `invalid_value` - Value doesn't match allowed options
- `type_mismatch` - Wrong data type (string instead of number)
- `invalid_reference` - Referenced node doesn't exist
- `invalid_expression` - Expression syntax error

**Example**:
```json
{
  "type": "missing_required",
  "property": "channel",
  "message": "Channel name is required",
  "fix": "Provide a channel name (lowercase, no spaces, 1-80 characters)"
}
```

### 2. Warnings (Should Fix)
**Doesn't block execution** - Workflow can be activated but may have issues

**Types**:
- `best_practice` - Recommended but not required
- `deprecated` - Using old API/feature
- `performance` - Potential performance issue

**Example**:
```json
{
  "type": "best_practice",
  "property": "errorHandling",
  "message": "Slack API can have rate limits",
  "suggestion": "Add onError: 'continueRegularOutput' with retryOnFail"
}
```

### 3. Suggestions (Optional)
**Nice to have** - Improvements that could enhance workflow

**Types**:
- `optimization` - Could be more efficient
- `alternative` - Better way to achieve same result

---

## The Validation Loop

### Pattern from Telemetry
**7,841 occurrences** of this pattern:

```
1. Configure node
   ↓
2. validate_node (23 seconds thinking about errors)
   ↓
3. Read error messages carefully
   ↓
4. Fix errors
   ↓
5. validate_node again (58 seconds fixing)
   ↓
6. Repeat until valid (usually 2-3 iterations)
```

**This is normal!** Expect 2-3 iterations of validate -> read errors -> fix -> validate again.

---

## Validation Profiles

Choose the right profile for your stage:

### minimal
**Use when**: Quick checks during editing

**Validates**:
- Only required fields
- Basic structure

**Pros**: Fastest, most permissive
**Cons**: May miss issues

### runtime (RECOMMENDED)
**Use when**: Pre-deployment validation

**Validates**:
- Required fields
- Value types
- Allowed values
- Basic dependencies

**Pros**: Balanced, catches real errors
**Cons**: Some edge cases missed

**This is the recommended profile for most use cases**

### ai-friendly
**Use when**: AI-generated configurations

**Validates**:
- Same as runtime
- Reduces false positives
- More tolerant of minor issues

**Pros**: Less noisy for AI workflows
**Cons**: May allow some questionable configs

### strict
**Use when**: Production deployment, critical workflows

**Validates**:
- Everything
- Best practices
- Performance concerns
- Security issues

**Pros**: Maximum safety
**Cons**: Many warnings, some false positives

---

## Common Error Types

### 1. missing_required
**What it means**: A required field is not provided

**How to fix**:
1. Use `get_node` to see required fields
2. Add the missing field to your configuration
3. Provide an appropriate value

**Example**:
```javascript
// Error
{
  "type": "missing_required",
  "property": "channel",
  "message": "Channel name is required"
}

// Fix
config.channel = "#general";
```

### 2. invalid_value
**What it means**: Value doesn't match allowed options

**How to fix**:
1. Check error message for allowed values
2. Use `get_node` to see options
3. Update to a valid value

**Example**:
```javascript
// Error
{
  "type": "invalid_value",
  "property": "operation",
  "message": "Operation must be one of: post, update, delete",
  "current": "send"
}

// Fix
config.operation = "post";  // Use valid operation
```

### 3. type_mismatch
**What it means**: Wrong data type for field

**How to fix**:
1. Check expected type in error message
2. Convert value to correct type

**Example**:
```javascript
// Error
{
  "type": "type_mismatch",
  "property": "limit",
  "message": "Expected number, got string",
  "current": "100"
}

// Fix
config.limit = 100;  // Number, not string
```

### 4. invalid_expression
**What it means**: Expression syntax error

**How to fix**:
1. Use n8n Expression Syntax skill
2. Check for missing `{{}}` or typos
3. Verify node/field references

**Example**:
```javascript
// Error
{
  "type": "invalid_expression",
  "property": "text",
  "message": "Invalid expression: $json.name",
  "current": "$json.name"
}

// Fix
config.text = "={{$json.name}}";  // Add {{}}
```

### 5. invalid_reference
**What it means**: Referenced node doesn't exist

**How to fix**:
1. Check node name spelling
2. Verify node exists in workflow
3. Update reference to correct name

**Example**:
```javascript
// Error
{
  "type": "invalid_reference",
  "property": "expression",
  "message": "Node 'HTTP Requets' does not exist",
  "current": "={{$node['HTTP Requets'].json.data}}"
}

// Fix - correct typo
config.expression = "={{$node['HTTP Request'].json.data}}";
```

---

## Auto-Sanitization System

### What It Does
**Automatically fixes common operator structure issues** on ANY workflow update

**Runs when**:
- `n8n_create_workflow`
- `n8n_update_partial_workflow`
- Any workflow save operation

### What It Fixes

| Issue | Operators | Auto-Fix |
|-------|-----------|----------|
| Binary ops with singleValue | equals, notEquals, contains, greaterThan, etc. | Removes `singleValue` |
| Unary ops missing singleValue | isEmpty, isNotEmpty, true, false | Adds `singleValue: true` |
| IF/Switch metadata | IF v2.2+, Switch v3.2+ | Adds `conditions.options` metadata |

### What It CANNOT Fix

#### 1. Broken Connections
References to non-existent nodes

**Solution**: Use `cleanStaleConnections` operation in `n8n_update_partial_workflow`

#### 2. Branch Count Mismatches
3 Switch rules but only 2 output connections

**Solution**: Add missing connections or remove extra rules

#### 3. Paradoxical Corrupt States
API returns corrupt data but rejects updates

**Solution**: May require manual database intervention

---

## False Positives

Warnings that are technically flagged but acceptable in context:

| Warning | Acceptable When | Fix When |
|---------|----------------|----------|
| Missing error handling | Simple/dev workflows | Production, important data |
| No retry logic | Idempotent ops, manual triggers | Flaky external services |
| Missing rate limiting | Internal/low-volume APIs | Public APIs, high volume |
| Unbounded query | Small datasets, aggregations | Production, large tables |

**Reduce false positives**: Use `profile: "ai-friendly"` for more tolerant validation.

---

## Validation Result Structure

Response contains: `valid` (boolean), `errors` (must fix), `warnings` (should review), `suggestions` (optional), `summary` (counts).

**Reading order**:
1. Check `result.valid` -- false means errors exist that block deployment
2. Fix all `result.errors` first (each has `type`, `property`, `message`, `fix`)
3. Review `result.warnings` -- decide which are acceptable (see False Positives)
4. Consider `result.suggestions` -- optional improvements

---

## Workflow Validation

### validate_workflow (Structure)
**Validates entire workflow**, not just individual nodes

**Checks**:
1. **Node configurations** - Each node valid
2. **Connections** - No broken references
3. **Expressions** - Syntax and references valid
4. **Flow** - Logical workflow structure

**Example**:
```javascript
validate_workflow({
  workflow: {
    nodes: [...],
    connections: {...}
  },
  options: {
    validateNodes: true,
    validateConnections: true,
    validateExpressions: true,
    profile: "runtime"
  }
})
```

### Common Workflow Errors

#### 1. Broken Connections
```json
{
  "error": "Connection from 'Transform' to 'NonExistent' - target node not found"
}
```

**Fix**: Remove stale connection or create missing node

#### 2. Circular Dependencies
```json
{
  "error": "Circular dependency detected: Node A → Node B → Node A"
}
```

**Fix**: Restructure workflow to remove loop

#### 3. Multiple Start Nodes
```json
{
  "warning": "Multiple trigger nodes found - only one will execute"
}
```

**Fix**: Remove extra triggers or split into separate workflows

#### 4. Disconnected Nodes
```json
{
  "warning": "Node 'Transform' is not connected to workflow flow"
}
```

**Fix**: Connect node or remove if unused

---

## Recovery Strategies

| Strategy | When | How |
|----------|------|-----|
| **Start Fresh** | Config severely broken | `get_node` for required fields, build minimal config, add incrementally |
| **Binary Search** | Validates but executes wrong | Remove half nodes, test, narrow down |
| **Clean Stale Connections** | "Node not found" errors | `n8n_update_partial_workflow({operations: [{type: "cleanStaleConnections"}]})` |
| **Auto-fix** | Operator structure errors | `n8n_autofix_workflow({id, applyFixes: false})` to preview, then `applyFixes: true` |

---

## Best Practices

### ✅ Do

- Validate after every significant change
- Read error messages completely
- Fix errors iteratively (one at a time)
- Use `runtime` profile for pre-deployment
- Check `valid` field before assuming success
- Trust auto-sanitization for operator issues
- Use `get_node` when unclear about requirements
- Document false positives you accept

### ❌ Don't

- Skip validation before activation
- Try to fix all errors at once
- Ignore error messages
- Use `strict` profile during development (too noisy)
- Assume validation passed (always check result)
- Manually fix auto-sanitization issues
- Deploy with unresolved errors
- Ignore all warnings (some are important!)

---

---

**Detailed Guides**: [ERROR_CATALOG.md](ERROR_CATALOG.md) | [FALSE_POSITIVES.md](FALSE_POSITIVES.md)
