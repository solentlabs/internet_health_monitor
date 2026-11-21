"""The docs' examples use only entity ids a new install creates, and the data use table matches Core's rules."""

from __future__ import annotations

import re
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from solentlabs.internet_health_monitor_core.data_plan import automatic_limit, every_days, full_test_mb
from solentlabs.internet_health_monitor_core.speed_test import SpeedTestResult

from .conftest import SetupEntry

ROOT = Path(__file__).resolve().parents[2]
DOCS = [ROOT / ".github" / "README.md", ROOT / "docs" / "dashboard-examples.md"]
ENTITY_ID = re.compile(r"\b(?:sensor|binary_sensor|button)\.internet_health_[a-z0-9_]+")


async def test_doc_entity_ids_exist(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Every IHM entity id in the docs is one the integration registers."""
    entry = await setup_entry(speed_test_backend="cloudflare", usage_totals=True)
    created = {e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}
    mentioned = {m for doc in DOCS for m in ENTITY_ID.findall(doc.read_text(encoding="utf-8"))}
    assert mentioned - created == set()


# Lines the README's data use table shows (Mbit/s down, up); it is rendered from Core's rules.
TABLE_LINES: list[tuple[int, int]] = [(100, 10), (300, 20), (1000, 40), (2000, 100)]
TABLE_BUDGETS_GB = (0, 10, 50)


def _spacing(days: int | None) -> str:
    """Days between automatic tests, as the table words them."""
    return {None: "none fits", 1: "daily", 7: "weekly"}.get(days, f"every {days} days")


def test_readme_data_table_matches_core() -> None:
    """README § How Much Data Speed Tests Use shows what data_plan.py computes."""
    rows = []
    for down, up in TABLE_LINES:
        last = SpeedTestResult("cloudflare", "s", down, up, None, None, None, 0.0, 0.0)
        limit = automatic_limit(last)
        cells = [f"{down}/{up}", f"about {round(full_test_mb(down, up), -1):.0f} MB", f"{limit.total_mb} MB"]
        cells += [_spacing(every_days(automatic_limit(last, b), b)) for b in TABLE_BUDGETS_GB]
        rows.append(f"| {' | '.join(cells)} |")
    assert "\n".join(rows) in (ROOT / ".github" / "README.md").read_text(encoding="utf-8")
