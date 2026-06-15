# FitFindr — Planning

## Overview

FitFindr is a multi-tool AI agent that helps users find secondhand clothing items and figure out how to style them. A user describes what they're looking for in plain language; the agent searches a mock listings dataset, suggests outfit combinations based on their wardrobe, and generates a shareable caption for the look.

## A Complete Interaction

**Example query:** "vintage graphic tee under $30, size M"

1. **Parse:** Extract `description="vintage graphic tee"`, `size="M"`, `max_price=30.0` using regex.
2. **search_listings("vintage graphic tee", size="M", max_price=30.0):** Returns 3 matching items sorted by keyword relevance. Top result: "Faded Band Tee — $22, Depop, Good condition."
3. **suggest_outfit(new_item=<band tee>, wardrobe=<example wardrobe>):** Returns: "Pair this faded band tee with your straight-leg jeans and chunky white sneakers for a classic 90s grunge look. Tuck the front hem slightly and roll the sleeves once for shape."
4. **create_fit_card(outfit=<suggestion>, new_item=<band tee>):** Returns: "thrifted this faded band tee off depop for $22 and it was made for my straight-legs 🖤 full look below"
5. **User sees:** Three panels — listing details, outfit idea, shareable caption.

**Error path:** If search_listings returns [], the agent sets session["error"] with a helpful message (what to try differently) and returns immediately — it does NOT call suggest_outfit with empty input.

---

## Tool 1: search_listings

**What it does:** Searches the mock listings dataset and returns items matching the user's keywords, optional size, and optional price ceiling.

**Inputs:**
- `description` (str): Keywords extracted from the user query (e.g., "vintage graphic tee")
- `size` (str | None): Size string to filter by, case-insensitive (e.g., "M"). None = no size filter.
- `max_price` (float | None): Maximum price inclusive. None = no price filter.

**Returns:** `list[dict]` — list of listing dicts sorted by relevance score (keyword overlap), highest first. Each dict has: id, title, description, category, style_tags (list), size, condition, price (float), colors (list), brand, platform. Returns `[]` on no match — never raises.

**Failure mode:** Returns `[]`. The planning loop checks for empty results and returns an error message to the user before calling any other tool.

---

## Tool 2: suggest_outfit

**What it does:** Given a specific listing and the user's wardrobe, suggests 1–2 complete outfit combinations using the LLM.

**Inputs:**
- `new_item` (dict): A listing dict from search_listings
- `wardrobe` (dict): A wardrobe dict with an `items` key (list of wardrobe item dicts). May be empty.

**Returns:** `str` — non-empty outfit suggestion string. If wardrobe is empty, returns general styling advice for the item rather than raising or returning "".

**Failure mode:** Returns a descriptive error string like "Outfit suggestion unavailable: [reason]". Never raises.

---

## Tool 3: create_fit_card

**What it does:** Generates a 2–3 sentence casual Instagram/TikTok-style caption for a thrifted outfit. Uses high LLM temperature (0.9) to produce varied output each call.

**Inputs:**
- `outfit` (str): The outfit suggestion string from suggest_outfit
- `new_item` (dict): The listing dict for the thrifted item

**Returns:** `str` — caption that sounds like a real OOTD post, mentions item name/price/platform once each. If `outfit` is empty/whitespace, returns a descriptive error string — never raises.

**Failure mode:** Guards against empty outfit string before calling LLM. Returns error string on LLM failure.

---

## Planning Loop

```
User query (str)
    │
    ▼
_parse_query(query)
    │ → parsed: {description, size, max_price}
    │
    ▼
search_listings(description, size, max_price)
    │
    ├─── results == [] ──► set session["error"] = helpful message → RETURN EARLY
    │
    │    results = [item, ...]
    ▼
session["selected_item"] = results[0]
    │
    ▼
suggest_outfit(selected_item, wardrobe)
    │ → session["outfit_suggestion"] = result string
    │
    ▼
create_fit_card(outfit_suggestion, selected_item)
    │ → session["fit_card"] = result string
    │
    ▼
Return session (all fields populated)
```

**Conditional logic in detail:**

After `_parse_query`: always proceeds — parsing never fails, it just returns None for missing fields.

After `search_listings`: check `if not results`. If True: set `session["error"]` to a message that names what filters were applied and suggests what to change (broaden keywords, raise price, remove size). Return `session` immediately. If False: set `session["selected_item"] = results[0]` and continue.

After `suggest_outfit`: always proceeds to `create_fit_card` — even if suggest_outfit returns an error string, create_fit_card handles it gracefully.

After `create_fit_card`: return the complete session.

---

## State Management

All state lives in the `session` dict initialized by `_new_session()`:

| Field | Type | Set when | Used by |
|-------|------|----------|---------|
| `query` | str | init | logging/display |
| `parsed` | dict | after parse step | search_listings call |
| `search_results` | list | after search | error check, selecting item |
| `selected_item` | dict | after search succeeds | suggest_outfit, create_fit_card |
| `wardrobe` | dict | init | suggest_outfit |
| `outfit_suggestion` | str | after suggest_outfit | create_fit_card |
| `fit_card` | str | after create_fit_card | UI display |
| `error` | str\|None | on early termination | UI display, flow control |

State passes forward automatically — `selected_item` set in step 3 is read directly in step 4 without any re-entry from the user.

---

## Error Handling

| Tool | Failure scenario | Agent response |
|------|-----------------|----------------|
| search_listings | No matches | Sets session["error"]: "No listings found for '[description]' with filters ([size], under $[price]). Try broadening your search..." Returns early, no further tools called. |
| search_listings | File load error | Returns [] — same no-results path |
| suggest_outfit | Empty wardrobe | Returns general styling advice string (no crash) |
| suggest_outfit | LLM failure | Returns "Outfit suggestion unavailable: [reason]" string |
| create_fit_card | Empty outfit string | Returns "Could not generate fit card: outfit suggestion was empty." |
| create_fit_card | LLM failure | Returns "Fit card unavailable: [reason]" string |

---

## Architecture

```
User query (str)
      │
      ▼
 ┌────────────────────────────────────────────────────────┐
 │                    Planning Loop                       │
 │  (agent.py: run_agent)                                 │
 │                                                        │
 │  1. _parse_query() ──────────────► session["parsed"]   │
 │         │                                              │
 │  2. search_listings() ──────────► session["search_     │
 │         │                          results"]           │
 │         │                                              │
 │         ├── [] ──► session["error"] ──► RETURN ────────┤
 │         │                                              │
 │         └── [items] ──► session["selected_item"]       │
 │                │                                       │
 │  3. suggest_outfit() ──────────► session["outfit_      │
 │         │   (uses selected_item + wardrobe)  suggestion"]│
 │         │                                              │
 │  4. create_fit_card() ─────────► session["fit_card"]   │
 │         │   (uses outfit_suggestion + selected_item)   │
 │         │                                              │
 │         └──────────────────────────► RETURN session    │
 └────────────────────────────────────────────────────────┘
      │
      ▼
 Gradio UI (app.py: handle_query)
   ├── listing panel  ← selected_item formatted
   ├── outfit panel   ← outfit_suggestion
   └── fit card panel ← fit_card
```

---

## AI Tool Plan

**For tools.py (search_listings):** Used Claude — gave it the Tool 1 spec block (inputs, returns, failure mode) and asked it to implement using `load_listings()`. Verified the generated code filtered all three parameters, returned `[]` on no match, and did not raise. Tested with 3 queries manually.

**For tools.py (suggest_outfit + create_fit_card):** Used Claude — gave it the Tool 2 and Tool 3 spec blocks plus the Groq model name. Generated LLM prompt templates. Adjusted the empty-wardrobe prompt to ask for "general styling advice" instead of a generic fallback, and raised create_fit_card temperature from 0.7 to 0.9 to ensure varied output.

**For agent.py (planning loop):** Used Claude — gave it the Planning Loop section and the architecture diagram. Generated the run_agent() function with correct conditional branching. Verified it checked `if not results` before calling suggest_outfit, and that session fields were set in the right order.

**For app.py (handle_query):** Used Claude — gave it the starter app.py structure and the session dict schema. Generated handle_query(). Added the listing_text formatting (emoji-labeled fields) which the generated version left as a plain dict repr.
