"""
EKOS CSV Parser
Extracts data from CSV files using pandas.
"""

from pathlib import Path
import pandas as pd
from app.utils.logger import logger
from app.utils.exceptions import IngestionError


class CSVParser:
    """Parse CSV files and extract data as structured text."""

    SUPPORTED_EXTENSIONS = {".csv", ".tsv"}

    def parse(self, file_path: str) -> list[dict]:
        """Parse a CSV file and convert to structured text."""
        path = Path(file_path)
        if not path.exists():
            raise IngestionError(f"File not found: {file_path}", filename=path.name)

        try:
            separator = "\t" if path.suffix == ".tsv" else ","
            df = pd.read_csv(str(path), sep=separator, encoding="utf-8", on_bad_lines="skip")

            if df.empty:
                return []

            headers = list(df.columns)
            lines = [f"Data File: {path.name}"]
            lines.append(" | ".join(str(h) for h in headers))
            lines.append("-" * 60)

            for _, row in df.iterrows():
                cells = [str(val) if pd.notna(val) else "" for val in row]
                lines.append(" | ".join(cells))

            content = "\n".join(lines)

            # Also generate a summary
            summary = "Dataset Summary:\n"
            summary += f"- Rows: {len(df)}\n"
            summary += f"- Columns: {len(headers)}\n"
            for col in headers:
                if df[col].dtype in ["int64", "float64"]:
                    summary += f"- {col}: min={df[col].min()}, max={df[col].max()}, mean={df[col].mean():.2f}\n"

            result = [{
                "content": content + "\n\n" + summary,
                "metadata": {
                    "source": path.name,
                    "file_type": "csv",
                    "row_count": len(df),
                    "column_count": len(headers),
                    "columns": headers,
                    "file_path": str(path),
                }
            }]

            logger.info(f"Parsed CSV: {path.name} ({len(df)} rows, {len(headers)} columns)")
            return result

        except Exception as e:
            raise IngestionError(f"Failed to parse CSV: {e}", filename=path.name)
