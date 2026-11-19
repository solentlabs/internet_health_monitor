"""The docs' examples use only entity ids that a new install creates (with a speed test service chosen)."""

from __future__ import annotations

import re
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import SetupEntry

ROOT = Path(__file__).resolve().parents[2]
DOCS = [ROOT / "README.md", ROOT / "docs" / "dashboard-examples.md"]
ENTITY_ID = re.compile(r"\b(?:sensor|binary_sensor|button)\.internet_health_[a-z0-9_]+")


async def test_doc_entity_ids_exist(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Every IHM entity id in the docs is one the integration registers."""
    entry = await setup_entry(speed_test_backend="cloudflare")
    created = {e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}
    mentioned = {m for doc in DOCS for m in ENTITY_ID.findall(doc.read_text(encoding="utf-8"))}
    assert mentioned - created == set()
