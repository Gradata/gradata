#!/usr/bin/env node
/**
 * PostToolUse hook: auto-tag prospect-facing activities in the delta system.
 *
 * Fires after every tool call. Checks if the tool was related to a prospect
 * action (email, deal update, prospect file edit, meeting creation) and calls
 * delta_tag.py to log the activity automatically.
 *
 * Input: JSON from stdin with { tool_name, tool_input, tool_output, session_id }
 * Silent on failure -- never breaks the tool chain.
 */

const { execSync } = require("child_process");

const DELTA_SCRIPT = "C:/Users/olive/SpritesWork/brain/scripts/delta_tag.py";
const PYTHON = "C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe";

// Tool patterns to skip (read-only, not prospect-facing)
const SKIP_TOOLS = [
  "mcp__claude_ai_Gmail__gmail_search_messages",
  "mcp__claude_ai_Gmail__gmail_read_message",
  "mcp__claude_ai_Gmail__gmail_read_thread",
  "mcp__claude_ai_Gmail__gmail_get_profile",
  "mcp__claude_ai_Gmail__gmail_list_labels",
  "mcp__claude_ai_Gmail__gmail_list_drafts",
  "mcp__claude_ai_Google_Calendar__gcal_list_events",
  "mcp__claude_ai_Google_Calendar__gcal_list_calendars",
  "mcp__claude_ai_Google_Calendar__gcal_get_event",
  "mcp__claude_ai_Google_Calendar__gcal_find_meeting_times",
  "mcp__claude_ai_Google_Calendar__gcal_find_my_free_time",
];

function readStdin() {
  try {
    return JSON.parse(require("fs").readFileSync("/dev/stdin", "utf8"));
  } catch {
    return null;
  }
}

/**
 * Try to extract prospect name and company from tool input/output.
 * Returns { prospect, company } with best-effort values.
 */
function extractProspectInfo(toolInput, toolOutput) {
  const info = { prospect: "", company: "" };
  const combined = JSON.stringify(toolInput || {}) + " " + JSON.stringify(toolOutput || {});

  // Look for prospect name in brain/prospects/ file paths
  const prospectPathMatch = combined.match(/brain\/prospects\/([^/]+)\//);
  if (prospectPathMatch) {
    // Convert kebab-case or snake_case to name
    info.prospect = prospectPathMatch[1]
      .replace(/[-_]/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  // Look for "to" field in email tool input (Gmail drafts/sends)
  if (toolInput && typeof toolInput === "object") {
    if (toolInput.to) {
      // Email "to" field might have a name or just an address
      const emailName = toolInput.to.match(/^([^<@]+)/);
      if (emailName && !info.prospect) {
        info.prospect = emailName[1].trim();
      }
    }
    if (toolInput.subject) {
      // Try to pull company from subject line patterns like "re: Sprites x CompanyName"
      const subjectCompany = toolInput.subject.match(/(?:x|for|re:?\s*)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)/);
      if (subjectCompany && !info.company) {
        info.company = subjectCompany[1].trim();
      }
    }
    // Rube/Pipedrive inputs may contain org or person names
    if (toolInput.org_name) info.company = toolInput.org_name;
    if (toolInput.person_name && !info.prospect) info.prospect = toolInput.person_name;
  }

  return info;
}

/**
 * Determine the activity type and detail from the tool call.
 * Returns null if this tool call should not be logged.
 */
function classifyActivity(toolName, toolInput, toolOutput) {
  // Gmail send/draft tools
  if (
    toolName === "mcp__claude_ai_Gmail__gmail_create_draft" ||
    toolName === "mcp__claude_ai_Gmail__gmail_send_message" ||
    toolName === "mcp__claude_ai_Gmail__gmail_send_draft"
  ) {
    const subject = (toolInput && toolInput.subject) || "no subject";
    return { type: "email_sent", detail: `Email: ${subject}` };
  }

  // Instantly email tools (outbound campaigns)
  if (
    toolName === "mcp__claude_ai_Instantly_MCP__reply_to_email" ||
    toolName === "mcp__claude_ai_Instantly_MCP__create_lead"
  ) {
    return { type: "email_sent", detail: "Instantly outbound action" };
  }

  // Rube multi-execute with Pipedrive context
  if (toolName === "mcp__rube__RUBE_MULTI_EXECUTE_TOOL") {
    const inputStr = JSON.stringify(toolInput || {}).toUpperCase();
    if (inputStr.includes("PIPEDRIVE")) {
      return { type: "deal_stage_change", detail: "Pipedrive update via Rube" };
    }
    // Not Pipedrive-related Rube call, skip
    return null;
  }

  // Calendar event creation
  if (toolName === "mcp__claude_ai_Google_Calendar__gcal_create_event") {
    const summary = (toolInput && toolInput.summary) || "meeting";
    return { type: "meeting", detail: `Calendar: ${summary}` };
  }

  // Write/Edit to brain/prospects/ files
  if (toolName === "Write" || toolName === "Edit") {
    const filePath = (toolInput && (toolInput.file_path || toolInput.path)) || "";
    if (filePath.includes("brain/prospects/") || filePath.includes("brain\\prospects\\")) {
      // Determine sub-type from file name
      let subType = "prospect_update";
      const lowerPath = filePath.toLowerCase();
      if (lowerPath.includes("cheat") || lowerPath.includes("prep")) {
        subType = "demo_prep";
      } else if (lowerPath.includes("objection")) {
        subType = "objection_handling";
      } else if (lowerPath.includes("research") || lowerPath.includes("enrich")) {
        subType = "prospect_research";
      }
      const fileName = filePath.split(/[/\\]/).pop() || "prospect file";
      return { type: subType, detail: `Updated ${fileName}` };
    }
    // Non-prospect file edits are system work, skip
    return null;
  }

  // Apollo enrichment (prospect-facing research)
  if (toolName && toolName.startsWith("mcp__claude_ai_Apollo_io__")) {
    // Only log enrichment and search, not profile lookups
    if (toolName.includes("enrich") || toolName.includes("search")) {
      return { type: "prospect_research", detail: `Apollo: ${toolName.split("__").pop()}` };
    }
    return null;
  }

  // No match -- not a prospect-facing action
  return null;
}

function shellEscape(str) {
  if (!str) return '""';
  // Escape double quotes and wrap in double quotes
  return '"' + str.replace(/"/g, '\\"').replace(/\n/g, " ").substring(0, 200) + '"';
}

function main() {
  const data = readStdin();
  if (!data || !data.tool_name) return;

  const toolName = data.tool_name;

  // Skip read-only tools
  if (SKIP_TOOLS.includes(toolName)) return;

  const activity = classifyActivity(toolName, data.tool_input, data.tool_output);
  if (!activity) return;

  const info = extractProspectInfo(data.tool_input, data.tool_output);
  const session = data.session_id || "unknown";

  // Default prep level: 1 for basic actions, 2 for research/prep
  let prepLevel = 1;
  if (activity.type === "demo_prep" || activity.type === "prospect_research") {
    prepLevel = 2;
  }

  const cmd = [
    `"${PYTHON}"`,
    `"${DELTA_SCRIPT}"`,
    "log-activity",
    "--type", activity.type,
    "--prospect", shellEscape(info.prospect || "unknown"),
    "--company", shellEscape(info.company || "unknown"),
    "--detail", shellEscape(activity.detail),
    "--prep", String(prepLevel),
    "--session", shellEscape(String(session)),
  ].join(" ");

  try {
    execSync(cmd, { timeout: 5000, stdio: "ignore" });
  } catch {
    // Silent failure -- never break the tool chain
  }
}

main();
