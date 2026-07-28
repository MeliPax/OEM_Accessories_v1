"""
Semantic processing layer for vehicle model search.

Adds translation, classification, and confidence scoring to improve
match accuracy and provide confidence metrics.

This is an optional enhancement layer that wraps core.search.search()
with semantic preprocessing.
"""

# Note: search is imported lazily to avoid circular imports during initialization
# Use: from semantic.search import search

__all__ = []
