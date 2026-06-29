"""
Semantic processing layer for vehicle model search.

Adds translation, classification, and confidence scoring to improve
match accuracy and provide confidence metrics.

This is an optional enhancement layer that wraps core.search.search()
with semantic preprocessing.
"""

from .search import search

__all__ = ["search"]
