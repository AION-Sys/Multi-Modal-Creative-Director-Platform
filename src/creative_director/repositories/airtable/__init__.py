"""Airtable backend: schema-as-code, REST client, repository, bootstrap."""

from .client import AirtableClient, AirtableError
from .repository import AirtableRepository

__all__ = ["AirtableClient", "AirtableError", "AirtableRepository"]
