# honest-nfz-mcp

Local MCP server for the **Polish National Health Fund (NFZ) public API** — waiting lists ("kolejki") and the medical-service dictionary. No authentication required.

Part of the [honest-mcp family](https://github.com/bartosz-kuc?tab=repositories) of small, auditable, local-first MCP servers.

## Why

Every Polish resident, at some point, wants to know **"jak długo trzeba czekać na kardiologa?"** — how long the queue for a cardiologist actually is. NFZ publishes this via a REST API but the friendly search on `terminyleczenia.nfz.gov.pl` doesn't help when you want to compare 20 providers at once or feed the data to an AI.

This server hands NFZ's data to your AI as structured JSON. Ask "cheapest wait time for a rehabilitation-cardiology facility in Mazowieckie?" and get an actual answer with provider names, wait statistics and — where NFZ provides them — first-available dates.

## Features

Three tools:

- `search_queues` — waiting list search: partial-name benefit + province + `case` (routine vs urgent) + optional `locality` (city/district), returns the first-available date (NFZ currently often leaves it empty) and the provider-reported wait statistics per provider.
- `search_benefits` — search the NFZ service dictionary to discover the exact benefit name to use.
- `list_provinces` — the 2-digit province code map (01–16).

## Data source

- Endpoint: [api.nfz.gov.pl/app-itl-api/](https://api.nfz.gov.pl/app-itl-api/) — NFZ's public "Informator o Terminach Leczenia" API
- No API key, no registration
- Public info about NFZ-contracted providers only

## Requirements

- Python 3.10+

## Setup

```bash
git clone https://github.com/bartosz-kuc/honest-nfz-mcp.git
cd honest-nfz-mcp
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

On Windows use `python` instead of `python3`, and `venv\Scripts\pip` / `venv\Scripts\python` instead of the `venv/bin/...` paths (here and in the configs below).

Register with Claude Code:

```bash
claude mcp add nfz /absolute/path/to/venv/bin/python /absolute/path/to/server.py
```

Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nfz": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

## Example usage

> **Note (September 2026):** NFZ's API currently returns no `dates` for most queue entries, so `first_available_date` is often `null`. NFZ has also renamed many services (e.g. `ŚWIADCZENIA Z ZAKRESU OKULISTYKI` instead of `PORADNIA OKULISTYCZNA`) — use `search_benefits` to find the current wording.

> "Which cardio-rehab facilities in Mazowieckie have the shortest wait?"

Two-step: `search_benefits(name="kardio")` → find exact benefit name → `search_queues(benefit="ZAKŁAD/OŚRODEK REHABILITACJI KARDIOLOGICZNEJ", province="07", case=1, limit=25)` → list of providers with their queue data.

> "Any ophthalmology openings in Kraków?"

`search_queues(benefit="ŚWIADCZENIA Z ZAKRESU OKULISTYKI", province="06", case=1, locality="KRAKÓW")` — `locality` is a case-insensitive substring filter applied by the NFZ API, so it covers the whole province, not just the first result page. Matches are re-checked locally, scanning at most 10 result pages of 25.

## Data flow

```
Your AI client
     ↕  MCP stdio
This server (Python, on your machine)
     ↕  HTTPS
api.nfz.gov.pl (National Health Fund)
```

No cloud middle. No telemetry.

## Author

**Bartosz Kuć** — Warsaw-based developer, JDG owner running [skanfirmy.pl](https://skanfirmy.pl).

- GitHub: https://github.com/bartosz-kuc

- Email: firma@bartosza.pl

## Consulting

Available for consulting on Polish tax and business integrations (KSeF, GUS/NFZ/GIOŚ APIs, mBank data), MCP server design, and AI-assisted tooling for JDGs and small teams. See **[skanfirmy.pl/uslugi](https://skanfirmy.pl/uslugi)** for productized packages (audit 3k PLN, setup 8-15k PLN, retainer 2-4k PLN/mo), or reach out via email.

## License

MIT — see [LICENSE](LICENSE).

## Related

- Part of the honest-mcp family — see the [family index](https://github.com/bartosz-kuc?tab=repositories).
