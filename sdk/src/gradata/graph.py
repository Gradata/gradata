"""
Learning Graph Data Model for Dashboard Visualization.
=======================================================
SDK LAYER: Layer 0 (patterns-safe). Pure data structures, no file I/O at module load.

Stolen from EverMemOS force-directed graph visualization. Gradata equivalent:
a data model that powers the gradata.ai dashboard's learning graph, showing
how corrections evolve into lessons, lessons graduate into rules, and rules
merge into meta-rules.

Usage::

    from gradata.graph import build_learning_graph, GraphNode, GraphEdge, to_json

    nodes, edges = build_learning_graph(lessons, meta_rules)
    graph_json = to_json(nodes, edges)
    # -> JSON ready for D3.js / force-directed graph rendering
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from gradata._types import Lesson, LessonState

# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------


@dataclass
class GraphNode:
    """A node in the learning graph.

    Attributes:
        id: Unique identifier (e.g. "lesson_0", "rule_3", "meta_formatting").
        type: Node type for styling ("correction", "lesson", "rule", "meta_rule").
        label: Human-readable label (truncated description).
        confidence: Current confidence score [0.0, 1.0].
        session: Session number when this node was created/last updated.
        category: Lesson category (e.g. "DRAFTING", "FORMATTING").
        state: Current lesson state (e.g. "INSTINCT", "PATTERN", "RULE").
        size: Visual size weight (based on confidence and fire_count).
    """
    id: str
    type: str
    label: str
    confidence: float
    session: int = 0
    category: str = ""
    state: str = ""
    size: float = 1.0


@dataclass
class GraphEdge:
    """An edge in the learning graph.

    Attributes:
        source: Source node ID.
        target: Target node ID.
        relation: Edge type for styling.
            - "graduated_from": lesson promoted from lower state
            - "merged_into": multiple lessons merged into meta-rule
            - "conflicts_with": two rules that contradict
            - "extends": one rule adds nuance to another
            - "updates": one rule supersedes another
            - "same_category": weak link between same-category lessons
        weight: Edge weight for layout (higher = closer nodes).
    """
    source: str
    target: str
    relation: str
    weight: float = 1.0


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------


def build_learning_graph(
    lessons: list[Lesson],
    meta_rules: list[dict] | None = None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Build a visualization graph of the learning pipeline.

    Creates nodes for each lesson and meta-rule, with edges showing
    graduation paths, category clusters, and meta-rule composition.

    Args:
        lessons: List of Lesson objects from the brain.
        meta_rules: Optional list of meta-rule dicts (from meta-rules.json).
            Each dict should have: id, principle, source_categories,
            source_lesson_ids, confidence.

    Returns:
        Tuple of (nodes, edges) ready for visualization.
    """
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    meta_rules = meta_rules or []

    # Build lesson nodes
    lesson_id_map: dict[int, str] = {}  # index -> node ID
    category_groups: dict[str, list[str]] = {}  # category -> [node_ids]

    for i, lesson in enumerate(lessons):
        node_id = f"lesson_{i}"
        lesson_id_map[i] = node_id

        # Determine node type from state
        if lesson.state == LessonState.RULE:
            node_type = "rule"
        elif lesson.state in (LessonState.ARCHIVED, LessonState.KILLED):
            node_type = "archived"
        else:
            node_type = "lesson"

        # Truncate label for display
        label = lesson.description[:60]
        if len(lesson.description) > 60:
            label += "..."

        # Size based on confidence and fire count
        size = 0.5 + lesson.confidence * 0.5
        if lesson.fire_count > 0:
            size += min(1.0, lesson.fire_count * 0.1)

        node = GraphNode(
            id=node_id,
            type=node_type,
            label=label,
            confidence=lesson.confidence,
            session=0,  # Not always available from Lesson
            category=lesson.category,
            state=lesson.state.value,
            size=round(size, 2),
        )
        nodes.append(node)

        # Track category groups
        if lesson.category not in category_groups:
            category_groups[lesson.category] = []
        category_groups[lesson.category].append(node_id)

    # Build graduation edges (INSTINCT -> PATTERN -> RULE within same category)
    for category, node_ids in category_groups.items():
        # Group by state
        by_state: dict[str, list[str]] = {}
        for nid in node_ids:
            node = next(n for n in nodes if n.id == nid)
            if node.state not in by_state:
                by_state[node.state] = []
            by_state[node.state].append(nid)

        # Connect INSTINCT -> PATTERN nodes in same category
        instincts = by_state.get("INSTINCT", [])
        patterns = by_state.get("PATTERN", [])
        rules = by_state.get("RULE", [])

        # Weak category links between same-state nodes
        for state_nodes in [instincts, patterns, rules]:
            for j in range(len(state_nodes)):
                for k in range(j + 1, min(j + 3, len(state_nodes))):
                    edges.append(GraphEdge(
                        source=state_nodes[j],
                        target=state_nodes[k],
                        relation="same_category",
                        weight=0.3,
                    ))

        # Graduation edges: PATTERN nodes link to RULE nodes in same category
        for p_id in patterns:
            for r_id in rules:
                edges.append(GraphEdge(
                    source=p_id,
                    target=r_id,
                    relation="graduated_from",
                    weight=0.8,
                ))

        for i_id in instincts:
            for p_id in patterns[:2]:  # Limit connections
                edges.append(GraphEdge(
                    source=i_id,
                    target=p_id,
                    relation="graduated_from",
                    weight=0.5,
                ))

    # Build meta-rule nodes and edges
    for mr in meta_rules:
        mr_id = mr.get("id", f"meta_{len(nodes)}")
        principle = mr.get("principle", "")
        label = principle[:60]
        if len(principle) > 60:
            label += "..."

        mr_node = GraphNode(
            id=mr_id,
            type="meta_rule",
            label=label,
            confidence=mr.get("confidence", 0.8),
            session=mr.get("created_session", 0),
            category=",".join(mr.get("source_categories", [])),
            state="META",
            size=1.5,  # Meta-rules are visually larger
        )
        nodes.append(mr_node)

        # Connect source lessons to meta-rule
        source_ids = mr.get("source_lesson_ids", [])
        for src_id in source_ids:
            # Try to find matching lesson node
            for i, lesson in enumerate(lessons):
                lesson_key = f"{lesson.date}_{lesson.category}_{lesson.description[:20]}"
                if src_id == lesson_key or src_id == lesson_id_map.get(i):
                    edges.append(GraphEdge(
                        source=lesson_id_map[i],
                        target=mr_id,
                        relation="merged_into",
                        weight=1.0,
                    ))
                    break

        # If no source lessons matched by ID, connect by category
        if not any(e.target == mr_id for e in edges):
            for cat in mr.get("source_categories", []):
                for nid in category_groups.get(cat, [])[:3]:
                    edges.append(GraphEdge(
                        source=nid,
                        target=mr_id,
                        relation="merged_into",
                        weight=0.6,
                    ))

    return nodes, edges


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def to_json(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    *,
    indent: int = 2,
) -> str:
    """Serialize graph to JSON for D3.js / dashboard consumption.

    Output format matches the common force-directed graph convention:
    {
        "nodes": [...],
        "links": [...]  // D3 convention uses "links" not "edges"
    }
    """
    return json.dumps(
        {
            "nodes": [asdict(n) for n in nodes],
            "links": [asdict(e) for e in edges],
        },
        indent=indent,
        ensure_ascii=False,
    )


def to_mermaid(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    *,
    max_nodes: int = 30,
) -> str:
    """Render graph as a Mermaid diagram (for documentation).

    Args:
        nodes: Graph nodes.
        edges: Graph edges.
        max_nodes: Maximum nodes to render (for readability).

    Returns:
        Mermaid graph definition string.
    """
    lines = ["graph TD"]

    # Render top nodes by confidence
    sorted_nodes = sorted(nodes, key=lambda n: n.confidence, reverse=True)[:max_nodes]
    node_ids = {n.id for n in sorted_nodes}

    # Node shapes by type
    shape_map = {
        "lesson": ("([", "])",),     # Stadium shape
        "rule": ("[[", "]]"),        # Subroutine shape
        "meta_rule": ("{{", "}}"),   # Hexagon
        "archived": ("(", ")"),      # Rounded
    }

    for node in sorted_nodes:
        open_b, close_b = shape_map.get(node.type, ("([", "])"))
        safe_label = node.label.replace('"', "'")[:40]
        lines.append(f"    {node.id}{open_b}\"{safe_label}\"{close_b}")

    # Render edges between visible nodes only
    style_map = {
        "graduated_from": "-->",
        "merged_into": "==>",
        "conflicts_with": "-. conflicts .->",
        "extends": "-- extends -->",
        "updates": "-- updates -->",
        "same_category": "-.-",
    }

    for edge in edges:
        if edge.source in node_ids and edge.target in node_ids:
            arrow = style_map.get(edge.relation, "-->")
            lines.append(f"    {edge.source} {arrow} {edge.target}")

    return "\n".join(lines)


def write_graph(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    output_path: str | Path,
) -> Path:
    """Write graph JSON to a file.

    Args:
        nodes: Graph nodes.
        edges: Graph edges.
        output_path: Path to write the JSON file.

    Returns:
        Path to the written file.
    """
    path = Path(output_path)
    path.write_text(to_json(nodes, edges), encoding="utf-8")
    return path
