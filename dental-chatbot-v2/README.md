# Site Chatbot

A JSON-driven chatbot you attach to any website. The Python engine is generic. **The bot’s personality, steps, and pathways live in one file: `flow.json`.**

Dental is only an example. Swap in `flow/oil_company.json` and the same code becomes an oil-company assistant.

## Install

```bash
cd dental-chatbot-v2
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Create a Postgres database (default name `dental_chatbot_v2`), then:

```bash
python scripts/init_db.py
python scripts/import_flow.py flow/dental_reception.json
python scripts/import_flow.py flow/oil_company.json
python scripts/import_appointments.py flow/appointments.json
# URLs come from .env — edit CHATBOT_API_URL / CHATBOT_DEFAULT_FLOW there
uvicorn app.api_server:app --reload --host $CHATBOT_API_HOST --port $CHATBOT_API_PORT
```

On startup the API writes `../chatbot-config.js` from `.env` for the demo site.

## Attach it to a website

### Demo site (this repo)

`index.html` loads `./chatbot-config.js` (no hardcoded API host). Set in `.env`:

```env
CHATBOT_API_URL=http://127.0.0.1:8000
CHATBOT_DEFAULT_FLOW=dental_reception
```

Switch bots by changing `CHATBOT_DEFAULT_FLOW=oil_company` and restarting the API.

### Any other site

```html
<script
  src="YOUR_API_URL/widget.js"
  data-api="YOUR_API_URL"
  data-flow="dental_reception"
></script>
```

Or fetch `/public-config` from the API and inject the script from `apiUrl` / `flowKey`.

Branding (title, color, avatar) is read from the flow JSON. You can override it on the tag:

| Attribute | Meaning |
|-----------|---------|
| `data-flow` | Which `flow_key` to run |
| `data-api` | API origin (optional if `widget.js` is served by the API) |
| `data-title` | Header title |
| `data-avatar` | Header emoji |
| `data-color` | Primary color |
| `data-position` | `right` or `left` |

## How a new chatbot is made

1. Copy an example in `flow/`.
2. Change `flow_key`, `branding`, `nodes`, and each option’s `next`.
3. Import it:

```bash
python scripts/import_flow.py flow/your_company.json
```

4. Point the website widget at `data-flow="your_company"`.

No Python changes are required to add/remove steps or to point a step at a different next step.

## flow.json contract

```json
{
  "flow_key": "oil_company",
  "name": "PetroServe Assistant",
  "branding": {
    "title": "PetroServe",
    "avatar": "🛢️",
    "primary_color": "#c2410c"
  },
  "navigation": {
    "back_enabled": true,
    "main_menu_enabled": true,
    "main_menu_node": "MAIN_MENU"
  },
  "start_node": "MAIN_MENU",
  "nodes": [
    {
      "key": "MAIN_MENU",
      "type": "menu",
      "message": "How can we help?",
      "options": [
        { "key": "QUOTE", "label": "Request a Quote", "next": "SELECT_PRODUCT" }
      ]
    },
    {
      "key": "CONTACT_NAME",
      "type": "input",
      "input_key": "contact_name",
      "validation_type": "name",
      "next": "CONTACT_PHONE"
    }
  ]
}
```

### Pathways

- Menu buttons use `options[].next`.
- Typed answers use the node’s `next`.
- Add a step by adding a node and pointing some `next` at it.
- Remove a step by deleting the node and relinking `next`.
- `{{field}}` and `{{summary}}` in messages are filled from answers (`input_key`).

### Node types

`menu` · `input` · `phone` · `email` · `date` · `time` · `confirmation` · `action` · `end`

### Plugins (optional, still named from JSON)

| JSON field | What it does |
|------------|----------------|
| `options_source.provider` | Live choices (`available_dates`, `available_slots`, `lookup_results`) |
| `action.handler` | Side effect (`create_order`) |
| `on_input.handler` | After a typed answer (`lookup_orders`) |
| `on_select.handler` | After a choice (`show_order_details`) |

Menus that feed an action **must** set `input_key` so the answer is stored.

## Package layout

```
app/           generic engine, plugins, API
flow/          JSON bots (dental + oil examples)
frontend/      website widget
database/      generic schema
scripts/       init_db, import_flow, import_appointments
```

The website in the repo root only loads `/widget.js`. It does not contain chatbot logic.
