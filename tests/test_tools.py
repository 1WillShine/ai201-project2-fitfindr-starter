"""
tests/test_tools.py
Run with: pytest tests/
"""
import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings tests ─────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)

def test_search_size_filter():
    results = search_listings("top", size="M", max_price=None)
    for item in results:
        assert "M" in (item.get("size") or "").upper()

def test_search_no_exception_on_impossible_query():
    # Should return [] not raise
    results = search_listings("xyzabc123impossible", size=None, max_price=None)
    assert isinstance(results, list)


# ── suggest_outfit tests ──────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    suggestion = suggest_outfit(results[0], get_example_wardrobe())
    assert isinstance(suggestion, str)
    assert len(suggestion) > 10

def test_suggest_outfit_empty_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    suggestion = suggest_outfit(results[0], get_empty_wardrobe())
    # Should return general advice, not crash
    assert isinstance(suggestion, str)
    assert len(suggestion) > 10


# ── create_fit_card tests ─────────────────────────────────────────────────────

def test_create_fit_card_normal():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    card = create_fit_card("Pair with wide-leg jeans and chunky sneakers for a 90s vibe.", results[0])
    assert isinstance(card, str)
    assert len(card) > 10

def test_create_fit_card_empty_outfit():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    card = create_fit_card("", results[0])
    # Must return error string, not raise
    assert isinstance(card, str)
    assert len(card) > 0
