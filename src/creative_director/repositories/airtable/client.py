"""Thin async Airtable REST client.

Covers the data API (records) and the meta API (create tables) — just enough for
the repository and the bootstrap script. Kept deliberately small; if this grows,
it's the natural place to add retry/backoff on 429s.
"""

from __future__ import annotations

import httpx

_API_ROOT = "https://api.airtable.com/v0"


class AirtableError(Exception):
    pass


class AirtableClient:
    def __init__(self, api_key: str, base_id: str, *, timeout: float = 30.0) -> None:
        if not api_key or not base_id:
            raise AirtableError("Airtable api_key and base_id are required")
        self._base_id = base_id
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AirtableClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    # --- data API ---------------------------------------------------------
    def _table_url(self, table: str) -> str:
        return f"{_API_ROOT}/{self._base_id}/{table}"

    async def list_records(
        self, table: str, *, filter_by_formula: str | None = None
    ) -> list[dict]:
        params: dict = {}
        if filter_by_formula:
            params["filterByFormula"] = filter_by_formula
        records: list[dict] = []
        offset: str | None = None
        while True:
            if offset:
                params["offset"] = offset
            resp = await self._client.get(self._table_url(table), params=params)
            self._raise_for_status(resp)
            body = resp.json()
            records.extend(body.get("records", []))
            offset = body.get("offset")
            if not offset:
                break
        return records

    async def find_by_uuid(self, table: str, uuid: str) -> dict | None:
        # `id` is our UUID primary field; escape any quotes defensively.
        safe = uuid.replace("'", r"\'")
        records = await self.list_records(table, filter_by_formula=f"{{id}}='{safe}'")
        return records[0] if records else None

    async def create_record(self, table: str, fields: dict) -> dict:
        resp = await self._client.post(
            self._table_url(table), json={"fields": fields, "typecast": True}
        )
        self._raise_for_status(resp)
        return resp.json()

    async def update_record(self, table: str, record_id: str, fields: dict) -> dict:
        resp = await self._client.patch(
            f"{self._table_url(table)}/{record_id}",
            json={"fields": fields, "typecast": True},
        )
        self._raise_for_status(resp)
        return resp.json()

    async def delete_record(self, table: str, record_id: str) -> bool:
        resp = await self._client.delete(f"{self._table_url(table)}/{record_id}")
        self._raise_for_status(resp)
        return bool(resp.json().get("deleted", False))

    # --- meta API (bootstrap) --------------------------------------------
    async def list_tables(self) -> list[dict]:
        resp = await self._client.get(f"{_API_ROOT}/meta/bases/{self._base_id}/tables")
        self._raise_for_status(resp)
        return resp.json().get("tables", [])

    async def create_table(self, name: str, fields: list[dict]) -> dict:
        resp = await self._client.post(
            f"{_API_ROOT}/meta/bases/{self._base_id}/tables",
            json={"name": name, "fields": fields},
        )
        self._raise_for_status(resp)
        return resp.json()

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.is_success:
            return
        raise AirtableError(f"Airtable {resp.request.method} {resp.request.url} -> "
                            f"{resp.status_code}: {resp.text}")
