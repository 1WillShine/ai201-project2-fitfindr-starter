"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.
"""

import os
from dotenv import load_dotenv
from groq import Groq
from utils.data_loader import load_listings

load_dotenv()

GROQ_MODEL = "llama-3.3-70b-versatile"


def _get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set. Add it to a .env file in the project root.")
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Returns an empty list if nothing matches — does NOT raise an exception.
    """
    try:
        listings = load_listings()
    except Exception as e:
        print(f"[search_listings] Failed to load listings: {e}")
        return []

    # Step 1: Filter by price
    if max_price is not None:
        listings = [l for l in listings if l.get("price", 999) <= max_price]

    # Step 2: Filter by size (case-insensitive, partial match)
    if size is not None:
        size_upper = size.upper()
        listings = [
            l for l in listings
            if size_upper in (l.get("size") or "").upper()
        ]

    # Step 3: Score by keyword overlap with description
    keywords = set(description.lower().split())
    # expand with common synonyms
    scored = []
    for item in listings:
        searchable = " ".join([
            item.get("title", ""),
            item.get("description", ""),
            item.get("category", ""),
            " ".join(item.get("style_tags", [])),
            item.get("brand", ""),
        ]).lower()
        score = sum(1 for kw in keywords if kw in searchable)
        if score > 0:
            scored.append((score, item))

    # Step 4: Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1-2 complete outfits.
    If wardrobe is empty, offer general styling advice.
    """
    try:
        client = _get_groq_client()
        wardrobe_items = wardrobe.get("items", [])

        if not wardrobe_items:
            prompt = f"""A user is considering buying this secondhand item:
Item: {new_item.get('title')}
Description: {new_item.get('description')}
Style tags: {', '.join(new_item.get('style_tags', []))}
Colors: {', '.join(new_item.get('colors', []))}
Category: {new_item.get('category')}

They don't have a wardrobe on file yet. Give them 1-2 specific outfit ideas for this item — 
suggest what types of pieces would pair well, what vibe it suits, and how to style it.
Be specific and practical. 2-4 sentences."""
        else:
            wardrobe_text = "\n".join(
                f"- {item.get('name', 'Unknown')} ({item.get('category', '')}, {item.get('color', '')}, {item.get('style', '')})"
                for item in wardrobe_items
            )
            prompt = f"""A user is considering buying this secondhand item:
Item: {new_item.get('title')}
Description: {new_item.get('description')}
Style tags: {', '.join(new_item.get('style_tags', []))}
Colors: {', '.join(new_item.get('colors', []))}
Category: {new_item.get('category')}

Their current wardrobe includes:
{wardrobe_text}

Suggest 1-2 specific complete outfit combinations using the new item and named pieces 
from their wardrobe. Be concrete — name the exact wardrobe pieces, describe the vibe, 
and add one styling tip. 3-5 sentences total."""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=300,
        )
        result = response.choices[0].message.content.strip()
        return result if result else "Could not generate outfit suggestion — try a different item."

    except Exception as e:
        return f"Outfit suggestion unavailable: {str(e)}"


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.
    Returns a descriptive error string if outfit is empty — does NOT raise.
    """
    if not outfit or not outfit.strip():
        return "Could not generate fit card: outfit suggestion was empty. Try searching for a different item."

    try:
        client = _get_groq_client()
        prompt = f"""Write a 2-3 sentence Instagram/TikTok caption for this thrifted outfit.

Thrifted item: {new_item.get('title')}
Price: ${new_item.get('price')}
Platform: {new_item.get('platform')}
Outfit: {outfit}

Rules:
- Sound like a real person posting an OOTD, not a product description
- Mention the item name, price, and platform naturally (once each)
- Capture the specific vibe of the outfit
- Use casual language, maybe 1-2 relevant emojis
- Do NOT use hashtags
- Make it feel authentic and specific to THIS outfit"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,  # higher temp = more variety each time
            max_tokens=150,
        )
        result = response.choices[0].message.content.strip()
        return result if result else "Could not generate fit card."

    except Exception as e:
        return f"Fit card unavailable: {str(e)}"
