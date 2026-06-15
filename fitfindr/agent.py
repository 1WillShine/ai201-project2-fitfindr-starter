"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.
"""

import re
from tools import search_listings, suggest_outfit, create_fit_card


def _new_session(query: str, wardrobe: dict) -> dict:
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query
    using regex patterns. No LLM needed for this step.

    Examples:
      "vintage graphic tee under $30, size M"  → {description: "vintage graphic tee", size: "M", max_price: 30.0}
      "flowy midi skirt under $40"             → {description: "flowy midi skirt", size: None, max_price: 40.0}
      "black combat boots size 8"              → {description: "black combat boots", size: "8", max_price: None}
    """
    # Extract max_price: "under $30", "$30", "under 30"
    price_match = re.search(r"(?:under\s+)?\$?(\d+(?:\.\d+)?)", query, re.IGNORECASE)
    max_price = float(price_match.group(1)) if price_match else None

    # Extract size: "size M", "size 8", "in M", "sz M"
    size_match = re.search(
        r"(?:size|in size|sz|in)\s+([XxSsLlMm]{1,3}|\d{1,2}(?:\.\d)?)",
        query, re.IGNORECASE
    )
    size = size_match.group(1).upper() if size_match else None

    # Description: remove price and size fragments, clean up
    description = query
    if price_match:
        description = description[:price_match.start()] + description[price_match.end():]
    if size_match:
        # remove "size X" / "in size X" etc.
        description = re.sub(
            r"(?:,?\s*(?:size|in size|sz|in)\s+[XxSsLlMm]{1,3}|\d{1,2}(?:\.\d)?)",
            "", description, flags=re.IGNORECASE
        )
    # Strip trailing connectors like "under", "in", ","
    description = re.sub(r"\b(under|in|,)\b\s*$", "", description, flags=re.IGNORECASE).strip()
    description = re.sub(r"\s+", " ", description).strip(" ,")

    return {"description": description, "size": size, "max_price": max_price}


def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop and returns
    the completed session dict.

    Planning loop:
    1. Parse query → description, size, max_price
    2. search_listings() → if empty, set error and return early
    3. Select top result → session["selected_item"]
    4. suggest_outfit() → session["outfit_suggestion"]
    5. create_fit_card() → session["fit_card"]
    6. Return session
    """
    session = _new_session(query, wardrobe)

    # Step 1: Parse the query
    if not query or not query.strip():
        session["error"] = "Please enter a search query — try something like 'vintage graphic tee under $30'."
        return session

    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 2: Search listings
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    # Branch: no results → return early with helpful message
    if not results:
        filters = []
        if parsed["size"]:
            filters.append(f"size {parsed['size']}")
        if parsed["max_price"]:
            filters.append(f"under ${parsed['max_price']:.0f}")
        filter_str = f" with filters ({', '.join(filters)})" if filters else ""
        session["error"] = (
            f"No listings found for \"{parsed['description']}\"{filter_str}. "
            f"Try broadening your search — remove the size filter, raise the price, "
            f"or use different keywords (e.g. 'jacket' instead of 'blazer')."
        )
        return session

    # Step 3: Select top result
    session["selected_item"] = results[0]

    # Step 4: Suggest outfit
    outfit = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
    )
    session["outfit_suggestion"] = outfit

    # Step 5: Create fit card
    fit_card = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )
    session["fit_card"] = fit_card

    # Step 6: Return complete session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
