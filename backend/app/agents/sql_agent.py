"""
EKOS SQL Agent
Converts natural language to safe, read-only SQL queries and executes them.
"""

import json
import re
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.base_agent import BaseAgent
from app.agents.prompts import SQL_AGENT_PROMPT
from app.llm.groq_client import get_chat_model
from app.utils.logger import logger
from app.utils.exceptions import AgentExecutionError


class SQLAgent(BaseAgent):
    """Converts natural language to SQL and executes safely."""

    BLOCKED_KEYWORDS = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
        "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "--", "/*",
    ]

    def __init__(self, db_session: AsyncSession = None):
        super().__init__(
            name="sql_agent",
            description="Converts natural language questions to SQL queries",
        )
        self.db_session = db_session

    async def execute(self, state: dict) -> dict:
        """Generate and execute SQL for data queries."""
        query = state.get("query", "")
        sub_tasks = state.get("sub_tasks", [])

        # Get SQL-specific sub-tasks
        sql_tasks = [t for t in sub_tasks if t.get("agent") == "SQL_AGENT"]

        all_sql_results = []

        questions = [t.get("search_query", query) for t in sql_tasks] if sql_tasks else [query]

        for question in questions:
            # Generate SQL using LLM
            sql_query = await self._generate_sql(question)

            if not sql_query:
                continue

            # Validate SQL safety
            if not self._is_safe_query(sql_query):
                logger.warning(f"Blocked unsafe SQL query: {sql_query[:100]}")
                all_sql_results.append({
                    "question": question,
                    "sql_query": sql_query,
                    "status": "blocked",
                    "error": "Query contains blocked keywords",
                    "results": [],
                })
                continue

            # Execute SQL
            if self.db_session:
                result = await self._execute_query(sql_query, question)
                all_sql_results.append(result)
            else:
                all_sql_results.append({
                    "question": question,
                    "sql_query": sql_query,
                    "status": "generated",
                    "results": [],
                    "note": "No database session available",
                })

        state["sql_results"] = all_sql_results
        state["sql_summary"] = self._summarize_results(all_sql_results)

        logger.info(f"SQL Agent processed {len(all_sql_results)} queries")
        return state

    async def _generate_sql(self, question: str) -> str:
        """Generate SQL query from natural language question."""
        llm = get_chat_model(json_mode=True)
        chain = SQL_AGENT_PROMPT | llm
        response = await chain.ainvoke({"question": question})
        response_text = response.content

        try:
            parsed = json.loads(response_text)
            return parsed.get("sql_query", "")
        except json.JSONDecodeError:
            # Try to extract SQL from response
            match = re.search(r'SELECT\s+.*?(?:;|$)', response_text, re.IGNORECASE | re.DOTALL)
            return match.group(0) if match else ""

    def _is_safe_query(self, sql: str) -> bool:
        """Check if a SQL query is safe (read-only)."""
        sql_upper = sql.upper().strip()

        # Must start with SELECT
        if not sql_upper.startswith("SELECT"):
            return False

        # Check for blocked keywords
        for keyword in self.BLOCKED_KEYWORDS:
            # Use word boundary matching to avoid false positives
            if re.search(rf'\b{keyword}\b', sql_upper):
                if keyword == "SELECT":
                    continue
                return False

        return True

    async def _execute_query(self, sql_query: str, question: str) -> dict:
        """Execute a SQL query and return results."""
        try:
            # Add LIMIT if not present
            if "LIMIT" not in sql_query.upper():
                sql_query = sql_query.rstrip(";") + " LIMIT 100"

            result = await self.db_session.execute(text(sql_query))
            rows = result.fetchall()
            columns = list(result.keys())

            # Convert to list of dicts
            data = [dict(zip(columns, row)) for row in rows]

            # Serialize non-standard types
            for row in data:
                for key, value in row.items():
                    if hasattr(value, 'isoformat'):
                        row[key] = value.isoformat()
                    elif not isinstance(value, (str, int, float, bool, type(None))):
                        row[key] = str(value)

            return {
                "question": question,
                "sql_query": sql_query,
                "status": "success",
                "columns": columns,
                "row_count": len(data),
                "results": data,
            }

        except Exception as e:
            logger.error(f"SQL execution error: {e}")
            return {
                "question": question,
                "sql_query": sql_query,
                "status": "error",
                "error": str(e),
                "results": [],
            }

    @staticmethod
    def _summarize_results(sql_results: list[dict]) -> str:
        """Create a text summary of SQL results."""
        summaries = []
        for result in sql_results:
            if result.get("status") == "success":
                data = result.get("results", [])
                summary = f"Query: {result.get('question', '')}\n"
                summary += f"SQL: {result.get('sql_query', '')}\n"
                summary += f"Results: {result.get('row_count', 0)} rows\n"
                if data:
                    # Show first few rows as text
                    for row in data[:5]:
                        summary += "  " + " | ".join(f"{k}: {v}" for k, v in row.items()) + "\n"
                    if len(data) > 5:
                        summary += f"  ... and {len(data) - 5} more rows\n"
                summaries.append(summary)
            else:
                summaries.append(f"Query failed: {result.get('error', 'Unknown error')}")

        return "\n\n".join(summaries) if summaries else "No SQL queries executed."
