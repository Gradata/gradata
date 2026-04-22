# Custom Domains

Brains are domain-agnostic by default. This guide shows how to configure a brain for your specific domain.

## Setting a Domain

Set the domain during initialization:

```bash
gradata init ./my-brain --domain "Customer Support"
```

Or programmatically:

```python
brain = Brain.init("./my-brain", domain="Customer Support")
```

## Registering Custom Task Types

The scope classifier detects task types from keywords. Add your own:

```python
brain.register_task_type(
    name="ticket_response",
    keywords=["ticket", "support request", "customer issue", "help desk"],
    domain_hint="support",
)

brain.register_task_type(
    name="escalation_note",
    keywords=["escalate", "priority", "urgent", "manager review"],
    domain_hint="support",
    prepend=True,  # Check this before default types
)
```

Now when the brain encounters "draft a ticket response", it correctly scopes it as `ticket_response` instead of a generic `email_draft`.

## CARL Contracts

CARL (Contracts for Agent Reinforcement Learning) lets you define behavioral rules per domain:

```python
from gradata.enhancements.behavioral_engine import BehavioralContract

support_contract = BehavioralContract(
    name="support_rules",
    domain="support",
    constraints=[
        "Always acknowledge the customer's frustration before offering a solution",
        "Include ticket number in every response",
        "Never promise specific resolution timelines unless confirmed",
    ],
)

brain.register_contract(support_contract)
```

Get applicable constraints for a task:

```python
constraints = brain.get_constraints("draft ticket response")
# ["Always acknowledge the customer's frustration...", ...]
```

## Custom Taxonomy

Create a `taxonomy.json` in your brain directory to define custom tags:

```json
{
  "categories": {
    "ticket_type": ["billing", "technical", "feature_request", "account"],
    "priority": ["p0", "p1", "p2", "p3"],
    "sentiment": ["frustrated", "neutral", "positive"]
  }
}
```

The brain loads this automatically and uses it for classification.

## Domain-Specific Scoping

Corrections and rules are scoped to domains. A lesson learned in `support` won't affect `sales` outputs:

```python
# This correction only creates rules for support email scopes
brain.correct(
    draft="We'll fix this right away.",
    final="I understand how frustrating this must be. Let me look into this for you.",
    context={"domain": "support", "task": "ticket_response"},
)
```

## Example: Engineering Domain

```python
brain = Brain.init("./eng-brain", domain="Engineering")

brain.register_task_type("code_review", ["review", "PR", "pull request", "diff"])
brain.register_task_type("incident_report", ["incident", "postmortem", "outage", "root cause"])
brain.register_task_type("design_doc", ["design", "RFC", "proposal", "architecture"])

brain.register_contract(BehavioralContract(
    name="eng_rules",
    domain="engineering",
    constraints=[
        "Code review comments must cite the specific line",
        "Incident reports must include a timeline",
        "Design docs must address failure modes",
    ],
))
```
