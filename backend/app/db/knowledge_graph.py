"""
EKOS Knowledge Graph
In-memory graph using NetworkX for entity relationship management.
"""

import json
from pathlib import Path
from typing import Optional
import networkx as nx
from app.config import get_settings
from app.utils.logger import logger


class KnowledgeGraph:
    """NetworkX-based knowledge graph for entity relationships."""

    RELATIONSHIP_TYPES = [
        "part_of", "maintained_by", "caused_by", "related_to",
        "uses_part", "located_in", "reported_by", "resolved_by",
        "depends_on", "similar_to",
    ]

    def __init__(self):
        self.settings = get_settings()
        self.graph = nx.DiGraph()
        self._graph_path = Path(self.settings.knowledge_graph_path)
        self._load()

    def add_entity(self, entity_id: str, entity_type: str, properties: dict = None):
        """Add an entity (node) to the graph."""
        self.graph.add_node(
            entity_id,
            entity_type=entity_type,
            **(properties or {}),
        )

    def add_relationship(
        self, source: str, target: str, relationship_type: str, properties: dict = None
    ):
        """Add a relationship (edge) between two entities."""
        # Ensure both nodes exist
        if not self.graph.has_node(source):
            self.add_entity(source, "unknown")
        if not self.graph.has_node(target):
            self.add_entity(target, "unknown")

        self.graph.add_edge(
            source, target,
            relationship=relationship_type,
            **(properties or {}),
        )

    def get_neighbors(self, entity_id: str, relationship_type: str = None) -> list[dict]:
        """Get all neighbors of an entity, optionally filtered by relationship type."""
        if not self.graph.has_node(entity_id):
            return []

        neighbors = []
        for _, target, data in self.graph.out_edges(entity_id, data=True):
            if relationship_type and data.get("relationship") != relationship_type:
                continue
            node_data = self.graph.nodes.get(target, {})
            neighbors.append({
                "entity_id": target,
                "entity_type": node_data.get("entity_type", "unknown"),
                "relationship": data.get("relationship", "related_to"),
                "properties": {k: v for k, v in node_data.items() if k != "entity_type"},
            })

        # Also check incoming edges
        for source, _, data in self.graph.in_edges(entity_id, data=True):
            if relationship_type and data.get("relationship") != relationship_type:
                continue
            node_data = self.graph.nodes.get(source, {})
            neighbors.append({
                "entity_id": source,
                "entity_type": node_data.get("entity_type", "unknown"),
                "relationship": f"reverse_{data.get('relationship', 'related_to')}",
                "properties": {k: v for k, v in node_data.items() if k != "entity_type"},
            })

        return neighbors

    def find_path(self, source: str, target: str) -> list[str]:
        """Find shortest path between two entities."""
        if not self.graph.has_node(source) or not self.graph.has_node(target):
            return []
        try:
            return list(nx.shortest_path(self.graph, source, target))
        except nx.NetworkXNoPath:
            return []

    def get_subgraph(self, entity_id: str, depth: int = 2) -> dict:
        """Get a subgraph around an entity up to a certain depth."""
        if not self.graph.has_node(entity_id):
            return {"nodes": [], "edges": []}

        # BFS to find nodes within depth
        visited = {entity_id}
        frontier = [entity_id]
        for _ in range(depth):
            next_frontier = []
            for node in frontier:
                for neighbor in self.graph.successors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.append(neighbor)
                for neighbor in self.graph.predecessors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.append(neighbor)
            frontier = next_frontier

        # Build subgraph data
        nodes = []
        for node_id in visited:
            data = self.graph.nodes.get(node_id, {})
            nodes.append({
                "id": node_id,
                "type": data.get("entity_type", "unknown"),
                "properties": {k: v for k, v in data.items() if k != "entity_type"},
            })

        edges = []
        for u, v, data in self.graph.edges(data=True):
            if u in visited and v in visited:
                edges.append({
                    "source": u,
                    "target": v,
                    "relationship": data.get("relationship", "related_to"),
                })

        return {"nodes": nodes, "edges": edges}

    def search_entities(self, query: str, entity_type: str = None) -> list[dict]:
        """Search for entities by name (substring match)."""
        results = []
        query_lower = query.lower()

        for node_id, data in self.graph.nodes(data=True):
            if entity_type and data.get("entity_type") != entity_type:
                continue
            if query_lower in node_id.lower():
                results.append({
                    "entity_id": node_id,
                    "entity_type": data.get("entity_type", "unknown"),
                    "properties": {k: v for k, v in data.items() if k != "entity_type"},
                })

        return results

    def save(self):
        """Save graph to JSON file."""
        self._graph_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "nodes": [
                {"id": n, **d} for n, d in self.graph.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, **d}
                for u, v, d in self.graph.edges(data=True)
            ],
        }

        with open(self._graph_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Saved knowledge graph ({self.graph.number_of_nodes()} nodes, "
                     f"{self.graph.number_of_edges()} edges)")

    def _load(self):
        """Load graph from JSON file."""
        if not self._graph_path.exists():
            self._seed_default_graph()
            return

        try:
            with open(self._graph_path, "r") as f:
                data = json.load(f)

            for node in data.get("nodes", []):
                node_id = node.pop("id")
                self.graph.add_node(node_id, **node)

            for edge in data.get("edges", []):
                source = edge.pop("source")
                target = edge.pop("target")
                self.graph.add_edge(source, target, **edge)

            logger.info(f"Loaded knowledge graph ({self.graph.number_of_nodes()} nodes, "
                         f"{self.graph.number_of_edges()} edges)")
        except Exception as e:
            logger.warning(f"Failed to load knowledge graph: {e}")
            self._seed_default_graph()

    def _seed_default_graph(self):
        """Seed the graph with sample manufacturing entities."""
        # Machines
        machines = [
            ("MCH-X001", "machine", {"name": "CNC Milling Machine X", "location": "Line-3"}),
            ("MCH-Y002", "machine", {"name": "Hydraulic Press Y", "location": "Line-2"}),
            ("MCH-Z003", "machine", {"name": "Laser Cutting Station Z", "location": "Line-1"}),
            ("MCH-A004", "machine", {"name": "Robotic Welding Arm A", "location": "Line-4"}),
            ("MCH-B005", "machine", {"name": "Conveyor System B", "location": "Line-1"}),
        ]

        # Production lines
        lines = [
            ("Line-1", "production_line", {"area": "Main Floor North"}),
            ("Line-2", "production_line", {"area": "Main Floor South"}),
            ("Line-3", "production_line", {"area": "Main Floor East"}),
            ("Line-4", "production_line", {"area": "Main Floor West"}),
        ]

        # Technicians
        techs = [
            ("Carlos Rodriguez", "technician", {"specialization": "CNC, Hydraulics"}),
            ("Emily Foster", "technician", {"specialization": "Laser, Robotics"}),
            ("Tom Baker", "technician", {"specialization": "Hydraulics, Conveyor"}),
            ("David Park", "technician", {"specialization": "Inspection, Calibration"}),
        ]

        # Parts
        parts = [
            ("SKF-7210", "part", {"name": "Spindle Bearing Set", "type": "bearing"}),
            ("Grundfos-CRN3", "part", {"name": "Coolant Pump Assembly", "type": "pump"}),
            ("Parker-H-Series", "part", {"name": "Hydraulic Junction Seals", "type": "seal"}),
            ("Fanuc-AiF-22", "part", {"name": "Servo Motor Joint 3", "type": "motor"}),
            ("Continental-Forte", "part", {"name": "Reinforced Conveyor Belt", "type": "belt"}),
        ]

        for entity_id, entity_type, props in machines + lines + techs + parts:
            self.add_entity(entity_id, entity_type, props)

        # Relationships
        relationships = [
            ("MCH-X001", "Line-3", "part_of"),
            ("MCH-Y002", "Line-2", "part_of"),
            ("MCH-Z003", "Line-1", "part_of"),
            ("MCH-A004", "Line-4", "part_of"),
            ("MCH-B005", "Line-1", "part_of"),
            ("MCH-X001", "Carlos Rodriguez", "maintained_by"),
            ("MCH-X001", "Emily Foster", "maintained_by"),
            ("MCH-Y002", "Tom Baker", "maintained_by"),
            ("MCH-Z003", "Emily Foster", "maintained_by"),
            ("MCH-A004", "Emily Foster", "maintained_by"),
            ("MCH-B005", "Tom Baker", "maintained_by"),
            ("MCH-X001", "SKF-7210", "uses_part"),
            ("MCH-X001", "Grundfos-CRN3", "uses_part"),
            ("MCH-X001", "Parker-H-Series", "uses_part"),
            ("MCH-A004", "Fanuc-AiF-22", "uses_part"),
            ("MCH-B005", "Continental-Forte", "uses_part"),
        ]

        for source, target, rel_type in relationships:
            self.add_relationship(source, target, rel_type)

        self.save()
        logger.info("Seeded default knowledge graph with manufacturing entities")

    def get_stats(self) -> dict:
        """Get graph statistics."""
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": dict(
                zip(
                    *np.unique(
                        [d.get("entity_type", "unknown") for _, d in self.graph.nodes(data=True)],
                        return_counts=True,
                    )
                )
            ) if self.graph.number_of_nodes() > 0 else {},
        }


# Avoid numpy import at module level for get_stats
try:
    import numpy as np
except ImportError:
    pass


# Singleton
_knowledge_graph: Optional[KnowledgeGraph] = None


def get_knowledge_graph() -> KnowledgeGraph:
    """Get or create the singleton knowledge graph."""
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = KnowledgeGraph()
    return _knowledge_graph
