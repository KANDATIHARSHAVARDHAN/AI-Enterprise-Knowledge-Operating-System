"""
EKOS SQL Agent
Converts natural language to safe, read-only SQL queries and executes them.
In production (Firestore mode), uses an in-memory SQLite database seeded with
enterprise data so the SQL Agent works without a MySQL server.
"""

import json
import re
import sqlite3
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.base_agent import BaseAgent
from app.agents.prompts import SQL_AGENT_PROMPT
from app.llm.groq_client import get_chat_model
from app.config import get_settings
from app.utils.logger import logger


# Module-level SQLite connection for Firestore mode
_sqlite_conn: sqlite3.Connection = None


def _get_sqlite_connection() -> sqlite3.Connection:
    """Get or create a seeded SQLite in-memory database for the SQL Agent."""
    global _sqlite_conn
    if _sqlite_conn is not None:
        return _sqlite_conn

    _sqlite_conn = sqlite3.connect(":memory:", check_same_thread=False)
    _sqlite_conn.row_factory = sqlite3.Row
    cursor = _sqlite_conn.cursor()

    # Create machine_events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS machine_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            machine_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'medium',
            root_cause TEXT,
            reported_by TEXT,
            department TEXT,
            production_line TEXT,
            downtime_hours REAL DEFAULT 0,
            cost_usd REAL DEFAULT 0,
            event_date TEXT NOT NULL,
            resolved_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create maintenance_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            machine_name TEXT NOT NULL,
            action_type TEXT NOT NULL,
            description TEXT NOT NULL,
            technician TEXT NOT NULL,
            parts_replaced TEXT,
            parts_cost_usd REAL DEFAULT 0,
            labor_cost_usd REAL DEFAULT 0,
            total_cost_usd REAL DEFAULT 0,
            duration_hours REAL DEFAULT 0,
            status TEXT DEFAULT 'completed',
            notes TEXT,
            log_date TEXT NOT NULL,
            next_maintenance_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed from SQL file if available
    settings = get_settings()
    seed_path = Path(settings.base_dir) / "scripts" / "seed_data.sql"
    if seed_path.exists():
        try:
            seed_sql = seed_path.read_text(encoding="utf-8")
            # Extract only INSERT statements for machine_events and maintenance_logs
            for statement in seed_sql.split(";"):
                statement = statement.strip()
                if not statement:
                    continue
                # Skip non-INSERT or USE statements
                upper = statement.upper()
                if upper.startswith("USE ") or upper.startswith("--") or upper.startswith("CREATE"):
                    continue
                if "INSERT INTO machine_events" in upper or "INSERT INTO maintenance_logs" in upper:
                    try:
                        cursor.execute(statement)
                    except sqlite3.OperationalError as e:
                        logger.debug(f"Skipping seed statement: {e}")
            _sqlite_conn.commit()
            count_events = cursor.execute("SELECT COUNT(*) FROM machine_events").fetchone()[0]
            count_logs = cursor.execute("SELECT COUNT(*) FROM maintenance_logs").fetchone()[0]
            logger.info(
                f"SQLite seeded: {count_events} machine_events, "
                f"{count_logs} maintenance_logs"
            )
        except Exception as e:
            logger.warning(f"Failed to seed SQLite from {seed_path}: {e}")
    else:
        logger.info("No seed_data.sql found. SQLite tables created empty.")

    return _sqlite_conn


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
        self.settings = get_settings()

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

            # Execute SQL — route to correct backend
            if self.settings.database_provider == "firestore":
                result = self._execute_sqlite_query(sql_query, question)
                all_sql_results.append(result)
            elif self.db_session:
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

    def _execute_sqlite_query(self, sql_query: str, question: str) -> dict:
        """Execute a SQL query on the in-memory SQLite database (Firestore mode)."""
        try:
            conn = _get_sqlite_connection()

            # Add LIMIT if not present
            if "LIMIT" not in sql_query.upper():
                sql_query = sql_query.rstrip(";") + " LIMIT 100"

            cursor = conn.execute(sql_query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()

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
                "engine": "sqlite",
            }

        except Exception as e:
            logger.error(f"SQLite execution error: {e}")
            return {
                "question": question,
                "sql_query": sql_query,
                "status": "error",
                "error": str(e),
                "results": [],
            }

    async def _execute_query(self, sql_query: str, question: str) -> dict:
        """Execute a SQL query on the MySQL database."""
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
