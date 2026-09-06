"""Write FastAPI's OpenAPI schema to docs/openapi.json."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import create_app


def main() -> None:
    dest = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(create_app().openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
