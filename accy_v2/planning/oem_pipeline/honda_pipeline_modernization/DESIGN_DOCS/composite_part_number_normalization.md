# Composite Part Number Normalization

**Status:** Design Document (Phase 2)  
**Used By:** Step 4 (Transformation & EN/FR Reconciliation)  
**Utility:** `accy_v2/core/helpers/composite_part_number.py`

---

## Problem Statement

Honda part numbers sometimes have multiple alternatives listed, especially for direct fit or interchangeable options:

**English Example:**
```
50977-565-45BH or 50977-565-45SH
```

**French Example:**
```
50977-565-45BH ou 50977-565-45SH
```

These represent the same part with two valid OEM codes. For database alignment and EN/FR reconciliation, we need to normalize these to a single canonical part number.

---

## Algorithm

### Strategy: Left-Priority

**Rule:** Keep the **left side** of the "or"/"ou" separator, as it is the primary/preferred part number.

### Pseudocode

```
normalize_composite_part_number(part_num, language):
  
  1. Identify separator based on language:
     - EN: "or"
     - FR: "ou"
  
  2. Split on separator (case-insensitive):
     left_part, right_part = part_num.split(separator, maxsplit=1)
  
  3. Strip whitespace and trim characters:
     left_part = left_part.strip()
     right_part = right_part.strip()
  
  4. Validate left part:
     if left_part is not empty and not null:
        return left_part
     elif right_part is not empty and not null:
        return right_part
     else:
        return part_num (unchanged if both empty)
```

---

## Implementation Details

### Function Signature

```python
def normalize_composite_part_number(
    part_num: Optional[str],
    language: str = "EN"
) -> Optional[str]:
    """
    Normalize composite part numbers with left-priority strategy.
    
    Converts "50977-565-45BH or 50977-565-45SH" → "50977-565-45BH"
    Works for both EN ("or") and FR ("ou") variants.
    
    Args:
        part_num: Raw part number (may contain "or"/"ou" separator)
        language: "EN" (default) or "FR"
    
    Returns:
        Normalized part number (single value), or None if input is None
    
    Raises:
        ValueError: If language is not "EN" or "FR"
    """
```

### Edge Cases & Handling

| Input | Language | Output | Reason |
|-------|----------|--------|--------|
| `None` | EN | `None` | Null input → null output |
| `""` | EN | `None` or `""` | Empty input → empty output |
| `"50977-565-45BH"` | EN | `"50977-565-45BH"` | No separator → unchanged |
| `"50977-565-45BH or 50977-565-45SH"` | EN | `"50977-565-45BH"` | Normal case |
| `"50977-565-45BH or "` | EN | `"50977-565-45BH"` | Right side empty → use left |
| `" or 50977-565-45SH"` | EN | `"50977-565-45SH"` | Left side empty → use right |
| `" or "` | EN | `None` or `""` | Both sides empty → null/empty |
| `"50977-565-45BH ou 50977-565-45SH"` | FR | `"50977-565-45BH"` | FR separator |
| `"Part with OR text"` | EN | `"Part with OR text"` | Uppercase "OR" not treated as separator (case-insensitive matching only) |

---

## Unit Test Cases

### Test Class: `TestCompositePartNumberNormalization`

#### Basic Cases

```python
def test_normalize_single_part_number():
    """No separator → unchanged."""
    assert normalize("50977-565-45BH", "EN") == "50977-565-45BH"

def test_normalize_with_or_separator():
    """EN "or" separator → left side."""
    assert normalize("50977-565-45BH or 50977-565-45SH", "EN") == "50977-565-45BH"

def test_normalize_with_ou_separator():
    """FR "ou" separator → left side."""
    assert normalize("50977-565-45BH ou 50977-565-45SH", "FR") == "50977-565-45BH"
```

#### Edge Cases

```python
def test_normalize_left_empty():
    """Right side empty → use left."""
    assert normalize("50977-565-45BH or ", "EN") == "50977-565-45BH"

def test_normalize_right_empty():
    """Left side empty → use right."""
    assert normalize(" or 50977-565-45SH", "EN") == "50977-565-45SH"

def test_normalize_both_empty():
    """Both sides empty → None."""
    assert normalize(" or ", "EN") is None

def test_normalize_null_input():
    """Null input → None."""
    assert normalize(None, "EN") is None

def test_normalize_empty_string():
    """Empty string → None or empty."""
    result = normalize("", "EN")
    assert result is None or result == ""
```

#### Whitespace Handling

```python
def test_normalize_extra_whitespace_left():
    """Left side with leading/trailing whitespace."""
    assert normalize("  50977-565-45BH  or 50977-565-45SH", "EN") == "50977-565-45BH"

def test_normalize_extra_whitespace_right():
    """Right side with extra whitespace."""
    assert normalize("50977-565-45BH or  50977-565-45SH  ", "EN") == "50977-565-45BH"

def test_normalize_multiple_or_separators():
    """Multiple separators → split on first only."""
    assert normalize("A or B or C", "EN") == "A"
```

#### Case Insensitivity

```python
def test_normalize_uppercase_separator():
    """Uppercase "OR" is treated as separator (case-insensitive)."""
    assert normalize("A OR B", "EN") == "A"

def test_normalize_mixed_case_separator():
    """Mixed case "Or" is treated as separator."""
    assert normalize("A Or B", "EN") == "A"
```

#### Language Validation

```python
def test_normalize_invalid_language():
    """Invalid language → ValueError."""
    with pytest.raises(ValueError):
        normalize("A or B", "INVALID")

def test_normalize_case_sensitive_language():
    """Language parameter is case-sensitive ("EN" not "en")."""
    # Could accept both; design choice:
    # Option 1: Strict (only "EN"/"FR")
    # Option 2: Flexible (accept "en"/"fr")
    # Recommendation: Flexible for user convenience
    assert normalize("A or B", "en") == "A"  # Lowercase accepted
```

---

## Integration Points

### Used in Step 4 (Transformation & EN/FR Reconciliation)

```python
# Step 4: Create reconciliation map
df_en_normalized = df_en.copy()
df_en_normalized["part_number"] = df_en["part_number"].apply(
    lambda x: normalize_composite_part_number(x, "EN")
)

df_fr_normalized = df_fr.copy()
df_fr_normalized["part_number"] = df_fr["part_number"].apply(
    lambda x: normalize_composite_part_number(x, "FR")
)

# Now both EN and FR have canonical part numbers for matching
reconciliation_map = create_reconciliation_map(df_en_normalized, df_fr_normalized)
```

---

## Testing Strategy

**Unit Tests:**
- >80% coverage of all branches (including all edge cases above)
- Test fixtures for common part number patterns
- Parametrized tests for multiple languages

**Integration Tests (Phase 4):**
- Verify reconciliation map uses normalized part numbers
- Confirm EN/FR pairs correctly match after normalization

**Regression Tests (Phase 7):**
- No impact on other OEMs (utility is optional, Honda-specific)
- Can be reused if other OEMs adopt in future

---

## Performance Considerations

- **Time Complexity:** O(n) where n = string length (linear scan for separator)
- **Space Complexity:** O(n) (creating split strings)
- **Optimization:** Separator index search is fast (Python str.split is optimized)

For Honda's typical batch (10–13 files, ~4500 parts per file = 58,500 parts total):
- Expected runtime: <100ms for all normalizations
- Not a performance bottleneck

---

## Future Enhancements

1. **Configurable separators:** Allow config to specify "or" alternatives (e.g., "+", "/")
2. **Multiple separator support:** Handle mixed separators in same field
3. **Validation:** Verify normalized part numbers match expected format
4. **Metrics:** Track how many parts were normalized (for DQ reporting)

---

**Status:** Ready for implementation (Phase 2)  
**Utility File:** `accy_v2/core/helpers/composite_part_number.py`  
**Tests File:** `accy_v2/tests/test_composite_part_number.py`
