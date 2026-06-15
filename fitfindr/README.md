# FitFindr

A multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. Users describe what they're looking for in plain language; the agent searches listings, suggests outfit combinations using their wardrobe, and generates a shareable caption for the look.

---

## Tool Inventory

### Tool 1: `search_listings(description, size, max_price)`

**Purpose:** Search the mock listings dataset and return matching items sorted by relevance.

**Inputs:**
- `description` (str): Keywords describing the item (e.g., "vintage graphic tee")
- `size` (str | None): Size filter — case-insensitive, partial match. None = no filter.
- `max_price` (float | None): Maximum price inclusive. None = no filter.

**Returns:** `list[dict]` — matching listing dicts sorted by keyword relevance score, highest first. Each dict contains: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`. Returns `[]` on no match — never raises an exception.

---

### Tool 2: `suggest_outfit(new_item, wardrobe)`

**Purpose:** Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfit combinations using the Groq LLM.

**Inputs:**
- `new_item` (dict): A listing dict from search_listings
- `wardrobe` (dict): A wardrobe dict with an `items` key (list of wardrobe item dicts). May be empty.

**Returns:** `str` — non-empty outfit suggestion. If wardrobe is empty, returns general styling advice for the item. If LLM fails, returns a descriptive error string.

---

### Tool 3: `create_fit_card(outfit, new_item)`

**Purpose:** Generate a 2–3 sentence casual Instagram/TikTok-style caption for the thrifted outfit. Uses temperature=0.9 for varied output on each call.

**Inputs:**
- `outfit` (str): The outfit suggestion from suggest_outfit
- `new_item` (dict): The listing dict for the thrifted item

**Returns:** `str` — OOTD-style caption mentioning the item name, price, and platform. If `outfit` is empty, returns a descriptive error string — never raises.

---

## How the Planning Loop Works

The loop in `run_agent()` branches conditionally — it does not call all tools in a fixed sequence regardless of results.

```
1. Parse query → extract description, size, max_price using regex
2. search_listings(description, size, max_price)
      │
      ├── results == [] → set session["error"] with helpful message → RETURN EARLY
      │   (suggest_outfit and create_fit_card are never called)
      │
      └── results non-empty → session["selected_item"] = results[0]
3. suggest_outfit(selected_item, wardrobe)
      → session["outfit_suggestion"]
4. create_fit_card(outfit_suggestion, selected_item)
      → session["fit_card"]
5. Return session
```

The key branch is after step 2: if `search_listings` returns an empty list, the agent sets a user-facing error message describing what filters were applied and what the user can try differently, then returns immediately without calling the LLM tools. This prevents suggest_outfit from being called with an empty item.

---

## State Management

All state is stored in a single `session` dict initialized by `_new_session()`. Each tool writes its output to a named field; the next tool reads from that field directly — no re-entry from the user.

| Field | Set when | Read by |
|-------|----------|---------|
| `query` | init | display/logging |
| `parsed` | after query parse | search_listings call |
| `search_results` | after search | empty-check, selecting item |
| `selected_item` | after search succeeds | suggest_outfit, create_fit_card |
| `wardrobe` | init | suggest_outfit |
| `outfit_suggestion` | after suggest_outfit | create_fit_card |
| `fit_card` | after create_fit_card | UI display |
| `error` | on early termination | UI display, flow control |

---

## Error Handling

### search_listings — no results
**Trigger:** Query `"designer ballgown size XXS under $5"` — impossible combination.
**Agent response:** Sets `session["error"]` to: *"No listings found for 'designer ballgown' with filters (size XXS, under $5). Try broadening your search — remove the size filter, raise the price, or use different keywords."*
Returns immediately. `suggest_outfit` and `create_fit_card` are never called.

**Testing:**
```bash
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
# Output: []
```

### suggest_outfit — empty wardrobe
**Trigger:** User selects "Empty wardrobe (new user)".
**Agent response:** LLM is prompted for general styling advice instead of wardrobe-specific combinations. Returns a useful suggestion string, never crashes.

**Testing:**
```bash
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
r = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(r[0], get_empty_wardrobe()))
"
```

### create_fit_card — empty outfit string
**Trigger:** `create_fit_card("", item)`.
**Agent response:** Returns `"Could not generate fit card: outfit suggestion was empty."` — no exception.

**Testing:**
```bash
python -c "
from tools import search_listings, create_fit_card
r = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', r[0]))
"
```

---

## Spec Reflection

**One way the spec helped:** Writing the planning loop in plain conditional logic in planning.md before coding made the branching obvious — checking `if not results` before calling suggest_outfit was explicitly described, which prevented me from accidentally wiring a fixed 3-step sequence. The diagram also made it clear that `selected_item` needed to be stored in session *before* suggest_outfit, not derived inline.

**One way implementation diverged from the spec:** The original spec described using the LLM to parse the query (extract description/size/price from natural language). During implementation I switched to regex parsing instead — it's faster, free, and the query patterns are predictable enough that LLM parsing wasn't needed. The spec's AI Tool Plan was updated to reflect this change.

---

## AI Usage

**Instance 1 — search_listings implementation:**
I gave Claude the Tool 1 spec block (inputs, return value, failure mode description) and the `load_listings()` signature from data_loader.py, and asked it to implement `search_listings()`. It generated a function that filtered by price and size and scored by keyword overlap. I overrode the size matching logic — the generated version used exact string equality (`item["size"] == size`), which would miss entries like "S/M" when the user inputs "M". I changed it to case-insensitive substring matching (`size_upper in item["size"].upper()`).

**Instance 2 — create_fit_card prompt design:**
I gave Claude the Tool 3 spec (caption style requirements: casual, OOTD tone, mentions item/price/platform once, no hashtags) and asked it to write the LLM prompt. The generated prompt was too formal — it said "Please write a caption..." which produced product-description-style outputs. I rewrote the rules section to say "Sound like a real person posting an OOTD, not a product description" and added "Make it feel authentic and specific to THIS outfit," which significantly improved caption quality.

---

## Setup and Usage

```bash
git clone https://github.com/1WillShine/ai201-project2-fitfindr-starter.git
cd ai201-project2-fitfindr-starter
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your Groq API key

python app.py         # launch the UI at http://localhost:7860
python agent.py       # CLI test (happy path + no-results path)
pytest tests/         # run all tool tests
```
