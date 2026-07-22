"""nfz-mcp — MCP server for the Polish National Health Fund (NFZ) public API.

Wraps https://api.nfz.gov.pl/ — NFZ's public REST API for waiting list
lookups ("kolejki") and the benefit dictionary. No authentication, no
registration.

Primary use case: "how long is the wait for a cardiologist in Warsaw?"
answered locally without scraping. Also useful for building oncall
availability dashboards.

Tools: search_queues, search_benefits, list_provinces.

Author: Bartosz Kuć <firma@bartosza.pl>
Repo:   https://github.com/bartosz-kuc/nfz-mcp
License: MIT
"""

import asyncio
import json
import re
from typing import Any

import requests

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

NFZ_BASE = "https://api.nfz.gov.pl/app-itl-api"
API_VERSION = "1.3"

PROVINCES = {
    "01": "DOLNOŚLĄSKIE",
    "02": "KUJAWSKO-POMORSKIE",
    "03": "LUBELSKIE",
    "04": "LUBUSKIE",
    "05": "ŁÓDZKIE",
    "06": "MAŁOPOLSKIE",
    "07": "MAZOWIECKIE",
    "08": "OPOLSKIE",
    "09": "PODKARPACKIE",
    "10": "PODLASKIE",
    "11": "POMORSKIE",
    "12": "ŚLĄSKIE",
    "13": "ŚWIĘTOKRZYSKIE",
    "14": "WARMIŃSKO-MAZURSKIE",
    "15": "WIELKOPOLSKIE",
    "16": "ZACHODNIOPOMORSKIE",
}

CASE_LABELS = {1: "stabilny", 2: "pilny"}
PROVINCE_RE = re.compile(r"^\d{2}$")


def _validate_province(p: str) -> str:
    p = p.strip()
    if not PROVINCE_RE.match(p) or p not in PROVINCES:
        raise ValueError(f"Province must be a 2-digit code in 01–16, got {p!r}. See list_provinces for the mapping.")
    return p


def _validate_case(c: int) -> int:
    c = int(c)
    if c not in (1, 2):
        raise ValueError(f"case must be 1 (stabilny) or 2 (pilny), got {c}")
    return c


def _get(path: str, params: dict) -> dict:
    params = {**params, "api-version": API_VERSION, "format": "json"}
    resp = requests.get(f"{NFZ_BASE}/{path}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _simplify_queue_entry(item: dict) -> dict:
    a = item.get("attributes", {})
    dates = a.get("dates") or {}
    stats = a.get("statistics") or {}
    provider_data = stats.get("provider-data", {}) if isinstance(stats, dict) else {}
    return {
        "benefit": a.get("benefit"),
        "provider": a.get("provider"),
        "place": a.get("place"),
        "address": a.get("address"),
        "locality": a.get("locality"),
        "phone": a.get("phone"),
        "case": CASE_LABELS.get(a.get("case"), a.get("case")),
        "first_available_date": dates.get("date"),
        "date_situation_as_of": dates.get("date-situation-as-at"),
        "awaiting": provider_data.get("awaiting"),
        "average_period": provider_data.get("average-period"),
        "queue_active": a.get("queue"),
    }


server = Server("nfz")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_queues",
            description=(
                "Search NFZ waiting lists (kolejki) for a medical service in a province. Returns the first-available "
                "date and average wait time reported by each provider. `benefit` is a partial (case-insensitive) match "
                "on the official service name — use `search_benefits` first if unsure. `case`: 1 = stabilny (routine), "
                "2 = pilny (urgent)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "benefit": {"type": "string", "description": "Partial name of the medical service (e.g., 'PORADNIA KARDIOLOGICZNA')"},
                    "province": {"type": "string", "description": "2-digit province code (see list_provinces). E.g., 07 = MAZOWIECKIE."},
                    "case": {"type": "integer", "enum": [1, 2], "default": 1, "description": "1 = stabilny (routine), 2 = pilny (urgent)"},
                    "locality": {"type": "string", "description": "Optional city filter (case-insensitive substring match on the response)."},
                    "limit": {"type": "integer", "default": 20, "description": "Max results to return (default 20, max 25 per NFZ API)"},
                },
                "required": ["benefit", "province"],
            },
        ),
        Tool(
            name="search_benefits",
            description=(
                "Search the NFZ benefit dictionary — the official service names that `search_queues` accepts. "
                "Use this to discover the exact wording before searching queues."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Partial name to search for (case-insensitive)"},
                    "limit": {"type": "integer", "default": 25, "description": "Max results (default 25)"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="list_provinces",
            description="Return the mapping of 2-digit province codes to voivodeship names used by NFZ.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "list_provinces":
        return [TextContent(type="text", text=json.dumps(PROVINCES, ensure_ascii=False, indent=2))]

    if name == "search_benefits":
        query = arguments["name"].strip()
        if not query:
            raise ValueError("name must be non-empty")
        limit = min(int(arguments.get("limit", 25)), 25)
        data = _get("benefits", {"name": query, "limit": limit, "page": 1})
        return [TextContent(type="text", text=json.dumps({
            "count": data.get("meta", {}).get("count"),
            "benefits": data.get("data", []),
        }, ensure_ascii=False, indent=2))]

    if name == "search_queues":
        benefit = arguments["benefit"].strip()
        province = _validate_province(arguments["province"])
        case = _validate_case(arguments.get("case", 1))
        locality_filter = (arguments.get("locality") or "").strip().lower()
        limit = min(int(arguments.get("limit", 20)), 25)

        data = _get("queues", {
            "benefit": benefit,
            "province": province,
            "case": case,
            "limit": limit,
            "page": 1,
        })
        entries = [_simplify_queue_entry(item) for item in data.get("data", [])]
        if locality_filter:
            entries = [e for e in entries if e.get("locality") and locality_filter in e["locality"].lower()]

        result = {
            "total_count_in_api": data.get("meta", {}).get("count"),
            "returned": len(entries),
            "search": {
                "benefit": benefit,
                "province": province,
                "province_name": PROVINCES[province],
                "case": CASE_LABELS[case],
                "locality_filter": arguments.get("locality"),
            },
            "results": entries,
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    raise ValueError(f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def sync_main():
    """Sync entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    sync_main()
