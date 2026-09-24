# Trim Generalization & Multi-Identification Algorithm

**Status:** Design Document (Phase 2)  
**Used By:** Step 4.5 (Model Lookup Enrichment)  
**Utility:** `accy_v2/core/helpers/trim_helpers.py`

---

## Problem Statement

Honda trim names are sometimes "general" categories that correspond to multiple database variants:

**Example:** 2026 CR-V "Sport" trim

- Input: Trim name = "Sport"
- Database records:
  - `Sport AWD` (model_number = XX001)
  - `Sport FWD` (model_number = XX002)
  - `Sport Hybrid` (model_number = XX003)

**Challenge:** A single trim "Sport" should match all three database records (or allow selection via additional keywords like "AWD", "Hybrid").

---

## Algorithm: Prefix Matching + Family Grouping

### High-Level Strategy

**Goal:** When a general trim name is encountered, find all database records that share that trim as a prefix or family name.

### Two Tiers

**Tier 1: Exact Match (current behavior)**
- Try exact database lookup: "Sport" → search for exact "Sport" in database
- If found: return match

**Tier 2: Family/Prefix Match (new, Phase 2 stubs)**
- If exact match fails: search for records starting with "Sport"
- Match all: "Sport AWD", "Sport FWD", "Sport Hybrid"
- Return as alternatives for model lookup

### Pseudocode

```
extract_trim_family(trim_name, model_name, model_year):
  
  1. Exact Match (fast path):
     candidates = db.search(
       model_name = model_name,
       year = model_year,
       trim_name = trim_name (exact)
     )
     if candidates not empty:
        return candidates
  
  2. Family/Prefix Match (fallback):
     family_candidates = db.search(
       model_name = model_name,
       year = model_year,
       trim_name LIKE trim_name + "%"  # STARTS WITH
     )
     if family_candidates not empty:
        return family_candidates
  
  3. No Match:
     return []
```

---

## Implementation Details

### Function Signature

```python
def extract_trim_family(
    trim_name: str,
    model_name: str,
    model_year: int,
    db: Optional[Any] = None,
    config: Optional[Dict] = None
) -> List[str]:
    """
    Extract all database trim variants matching a general trim name.
    
    Example:
      extract_trim_family("Sport", "CR-V", 2026)
      → ["Sport", "Sport AWD", "Sport FWD", "Sport Hybrid"]
    
    Args:
        trim_name: General trim name (may be prefix)
        model_name: Model name (e.g., "CR-V", "Accord")
        model_year: Vehicle year
        db: Optional database connection/service
        config: Optional config with matching rules
    
    Returns:
        List of database trim names matching the family
        (empty list if no matches)
    """
```

---

## Use Cases & Examples

### Case 1: Exact Match (No Generalization Needed)

**Input:** Trim = "EX-L", Model = "Accord", Year = 2026

**Database records:**
- `EX-L` (model_number = AC001)

**Behavior:**
- Exact match found → return ["EX-L"]
- No family expansion needed

### Case 2: General Trim (Family Match)

**Input:** Trim = "Sport", Model = "CR-V", Year = 2026

**Database records:**
- `Sport` (doesn't exist as exact)
- `Sport AWD` (model_number = CR001)
- `Sport FWD` (model_number = CR002)
- `Sport Hybrid` (model_number = CR003)
- `Touring` (not relevant)

**Behavior:**
- Exact match fails → prefix match
- Find all records LIKE "Sport%"
- Return ["Sport AWD", "Sport FWD", "Sport Hybrid"]
- Model lookup tries all three, returns all matching model numbers

### Case 3: Exact Match Preferred Over Prefix

**Input:** Trim = "Touring", Model = "CR-V", Year = 2026

**Database records:**
- `Touring` (model_number = CR010)
- `Touring AWD` (model_number = CR011)
- `Touring Hybrid` (model_number = CR012)

**Behavior:**
- Exact "Touring" exists → return ["Touring"]
- Ignore prefix variants (only return exact if found)

---

## Integration with VehicleSearchEngine

### Current Behavior (Tier 1: Exact Match)

```python
# Step 4.5: Model Lookup
for trim in unique_trims:
    result = VehicleSearchEngine.search(
        make="Honda",
        year=2026,
        keywords=[model_name, trim]
    )
    model_mapping[trim] = result.model_number
```

### Enhanced Behavior (Phase 2 Stub → Phase 5 Implementation)

```python
# Step 4.5: Model Lookup (Phase 5)
for trim in unique_trims:
    # Get all family variants
    family_trims = extract_trim_family(trim, model_name, year)
    
    # Search for each family variant
    all_results = []
    for family_trim in family_trims:
        result = VehicleSearchEngine.search(
            make="Honda",
            year=year,
            keywords=[model_name, family_trim]
        )
        if result:
            all_results.append(result)
    
    # Store results (may be multiple per trim if family match)
    model_mapping[trim] = all_results
```

---

## Design Decisions

### Decision 1: Exact Match Takes Priority

**Rule:** If exact trim exists in database, use it exclusively (don't expand to family).

**Rationale:**
- User input "Touring" may exist exactly → respect their exact intent
- Don't over-generalize and pollute results with "Touring AWD", "Touring Hybrid" if "Touring" alone is requested

**Trade-off:** May miss legitimate multi-variant cases if exact also exists, but safer default

### Decision 2: Case-Insensitive Prefix Matching

**Rule:** Prefix match ignores case: "Sport", "sport", "SPORT" all match "Sport AWD"

**Rationale:**
- Data quality: database may have inconsistent casing
- User experience: "sport" should still find "Sport AWD"

**Implementation:** `db_trim.lower().startswith(trim_name.lower())`

### Decision 3: Whitespace Normalization

**Rule:** Trim names normalized before matching (strip leading/trailing spaces, collapse internal spaces)

**Rationale:**
- Data quality: input may have accidental whitespace
- Robustness: "Sport  AWD" (double space) should match "Sport AWD"

### Decision 4: No Multi-Word Prefix Expansion (Phase 2)

**Rule:** Only expand single-word prefixes in Phase 2 (e.g., "Sport" → "Sport *")

**Rationale:**
- Reduces false positives: "Touring Premium" doesn't become "Touring Premium *" (too specific)
- Future enhancement (Phase 5): add config-driven multi-word patterns if needed

**Example:**
- ✅ "Sport" → "Sport AWD", "Sport FWD" (expand)
- ✅ "Touring" → "Touring AWD", "Touring Hybrid" (expand)
- ❌ "Sport Premium" → only exact match (don't expand, too specific)

---

## Unit Test Cases

### Test Class: `TestTrimGeneralizationAlgorithm`

#### Exact Match Cases

```python
def test_extract_exact_match():
    """Exact trim exists in database → return exact."""
    # Mock database with "EX-L"
    result = extract_trim_family("EX-L", "Accord", 2026)
    assert result == ["EX-L"]

def test_extract_no_expansion_on_exact():
    """Even if family exists, return only exact if exact matches."""
    # Mock database with "Touring" and "Touring AWD", "Touring Hybrid"
    result = extract_trim_family("Touring", "CR-V", 2026)
    assert result == ["Touring"]  # Only exact, not family
```

#### Family/Prefix Match Cases

```python
def test_extract_family_prefix_match():
    """No exact match → return all prefix matches."""
    # Mock database with "Sport AWD", "Sport FWD" (no exact "Sport")
    result = extract_trim_family("Sport", "CR-V", 2026)
    assert set(result) == {"Sport AWD", "Sport FWD"}

def test_extract_family_multiple_variants():
    """Return all family variants."""
    # Mock database with "Sport", "Sport AWD", "Sport FWD", "Sport Hybrid"
    result = extract_trim_family("Sport", "CR-V", 2026)
    # Exact "Sport" exists → return only it
    assert result == ["Sport"]
    
    # But if exact doesn't exist:
    # (use different mock)
    result = extract_trim_family("Sport", "CR-V", 2027)  # Different year
    assert set(result) == {"Sport AWD", "Sport FWD", "Sport Hybrid"}
```

#### Edge Cases

```python
def test_extract_no_match():
    """No exact or family match → empty list."""
    result = extract_trim_family("NonExistent", "Accord", 2026)
    assert result == []

def test_extract_case_insensitive():
    """Case-insensitive prefix match."""
    # Database has "Sport AWD" (capitalized)
    result = extract_trim_family("sport", "CR-V", 2026)
    assert "Sport AWD" in result

def test_extract_whitespace_normalization():
    """Whitespace normalized before match."""
    # Input has extra spaces
    result = extract_trim_family("  Sport  ", "CR-V", 2026)
    assert "Sport AWD" in result  # Still finds "Sport AWD"
```

---

## Phase 2 vs. Phase 5 Implementation

### Phase 2 Scope

**Deliverable:** Stub function with signature and basic tests

```python
def extract_trim_family(trim_name, model_name, model_year, db=None, config=None):
    """Phase 2 stub: return empty list."""
    # Full implementation in Phase 5
    return []
```

**Reason:**
- Requires VehicleSearchEngine integration (Phase 5 dependency)
- Requires actual database access patterns (Phase 5 context)
- Design document establishes algorithm; implementation deferred

### Phase 5 Scope

**Full implementation:**
- Integrate with actual database/VehicleSearchEngine
- Implement prefix matching logic
- Add DQ logging for family expansion
- Update model mapping to handle multiple variants per trim

---

## Performance Considerations

- **Database Queries:** 2 queries max per trim (exact, then prefix) vs. 1 (current)
- **Optimization:** Cache exact-match results to avoid re-querying

For Honda's typical batch (10–13 files, ~6 trims per file = ~78 trim lookups):
- Expected additional queries: ~40 prefix queries (if ~50% exact misses)
- Impact: Acceptable (database queries still <1s total)

---

## Future Enhancements

1. **Smart expansion rules:** Config-driven (e.g., "Sport" always expands to AWD/FWD variants)
2. **Keyword combination:** "Sport" + "Hybrid" keyword → only "Sport Hybrid" (narrow results)
3. **Model-specific rules:** Some models have different trim hierarchies
4. **Confidence scoring:** Prefer exact match over prefix match with confidence bonus

---

**Status:** Design document (implementation deferred to Phase 5)  
**Utility File:** `accy_v2/core/helpers/trim_helpers.py` (stub in Phase 2)  
**Tests File:** `accy_v2/tests/test_trim_helpers.py` (stub in Phase 2)  
**Full Implementation:** Phase 5 (Model Lookup Enrichment)
