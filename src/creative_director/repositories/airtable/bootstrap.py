"""Create the Airtable schema in a base from `schema.TABLES`.

Idempotent: skips any table that already exists (by name). Run once against a
fresh base after setting AIRTABLE_API_KEY and AIRTABLE_BASE_ID:

    python -m creative_director.repositories.airtable.bootstrap
"""

from __future__ import annotations

import asyncio

from ...config import get_settings
from .client import AirtableClient
from .schema import TABLES


async def bootstrap(client: AirtableClient) -> list[str]:
    """Create any missing tables. Returns the names of tables created."""
    existing = {t["name"] for t in await client.list_tables()}
    created: list[str] = []
    for table in TABLES:
        if table.name in existing:
            continue
        spec = table.to_airtable()
        await client.create_table(spec["name"], spec["fields"])
        created.append(table.name)
    return created


async def _main() -> None:
    settings = get_settings()
    if not settings.airtable_api_key or not settings.airtable_base_id:
        raise SystemExit("Set AIRTABLE_API_KEY and AIRTABLE_BASE_ID in the environment.")
    async with AirtableClient(settings.airtable_api_key, settings.airtable_base_id) as client:
        created = await bootstrap(client)
    if created:
        print("Created tables:", ", ".join(created))
    else:
        print("All tables already present; nothing to do.")


if __name__ == "__main__":
    asyncio.run(_main())
