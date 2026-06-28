"""
EKOS Graph Agent
Traverses the knowledge graph for entity relationships.
"""

from app.agents.base_agent import BaseAgent
from app.db.knowledge_graph import get_knowledge_graph
from app.utils.logger import logger


class GraphAgent(BaseAgent):
    """Traverses knowledge graph to find entity relationships."""

    def __init__(self):
        super().__init__(
            name="graph_agent",
            description="Queries the knowledge graph for entity relationships",
        )

    async def execute(self, state: dict) -> dict:
        """Query the knowledge graph for relevant entities."""
        query = state.get("query", "")
        sub_tasks = state.get("sub_tasks", [])

        graph = get_knowledge_graph()

        # Get graph-specific sub-tasks
        graph_tasks = [t for t in sub_tasks if t.get("agent") == "GRAPH"]

        graph_results = {
            "entities_found": [],
            "relationships": [],
            "subgraphs": [],
        }

        # Extract entity mentions from query
        entity_queries = []
        if graph_tasks:
            for task in graph_tasks:
                entity_queries.append(task.get("search_query", query))
        else:
            entity_queries = [query]

        for eq in entity_queries:
            # Search for entities mentioned in the query
            terms = eq.replace(",", " ").split()
            for term in terms:
                if len(term) < 3:
                    continue
                found = graph.search_entities(term)
                for entity in found:
                    if entity not in graph_results["entities_found"]:
                        graph_results["entities_found"].append(entity)

                        # Get neighbors for found entities
                        neighbors = graph.get_neighbors(entity["entity_id"])
                        for neighbor in neighbors:
                            rel = {
                                "source": entity["entity_id"],
                                "target": neighbor["entity_id"],
                                "relationship": neighbor["relationship"],
                                "target_type": neighbor["entity_type"],
                            }
                            if rel not in graph_results["relationships"]:
                                graph_results["relationships"].append(rel)

                        # Get subgraph
                        subgraph = graph.get_subgraph(entity["entity_id"], depth=1)
                        if subgraph["nodes"]:
                            graph_results["subgraphs"].append({
                                "center": entity["entity_id"],
                                "subgraph": subgraph,
                            })

        # Build summary text
        summary_parts = []
        for entity in graph_results["entities_found"]:
            summary_parts.append(
                f"Entity: {entity['entity_id']} (type: {entity['entity_type']})"
            )
        for rel in graph_results["relationships"]:
            summary_parts.append(
                f"  {rel['source']} --[{rel['relationship']}]--> {rel['target']} ({rel['target_type']})"
            )

        state["graph_results"] = graph_results
        state["graph_summary"] = "\n".join(summary_parts) if summary_parts else "No graph relationships found."

        logger.info(
            f"Graph Agent found {len(graph_results['entities_found'])} entities, "
            f"{len(graph_results['relationships'])} relationships"
        )
        return state
