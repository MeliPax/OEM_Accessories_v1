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
- **Filter results:** Remove any results with trim discriminator keywords (AWD, FWD, Hybrid, etc.) NOT present in incoming keywords
  - Example: If search keywords = ["sport"] only, remove "Sport Hybrid", "Sport AWD", "Sport FWD" from results
  - Example: If search keywords = ["sport", "hybrid"], keep only "Sport Hybrid"
- Return filtered alternatives for model lookup

### Pseudocode

```
extract_trim_family(trim_name, model_name, model_year, incoming_keywords):
  
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
     if family_candidates empty:
        return []
     
  3. Filter Discriminator Keywords:
     # Remove candidates with trim discriminator keywords NOT in incoming_keywords
     # This ensures downstream VehicleSearchEngine.search() won't reject them
     trim_discriminators = ["AWD", "FWD", "Hybrid", "Coupe", ...]
     filtered_candidates = []
     
     for candidate in family_candidates:
       candidate_tokens = tokenize(candidate)  # ["Sport", "Hybrid"]
       candidate_discriminators = candidate_tokens & trim_discriminators
       
       # Check: are there discriminators in candidate NOT in incoming_keywords?
       extra_discriminators = candidate_discriminators - incoming_keywords
       
       if extra_discriminators is empty:
          # All candidate's discriminators are in incoming keywords
          # Safe to include - downstream search won't reject it
          filtered_candidates.add(candidate)
     
     return filtered_candidates
```

**Rationale:** VehicleSearchEngine.search() applies strict AND filtering. It rejects candidates with trim discriminator keywords not present in the search keywords. By pre-filtering here, we ensure only viable candidates reach the downstream search.

---

## Implementation Details

### Function Signature

```python
def extract_trim_family(
    trim_name: str,
    model_name: str,
    model_year: int,
    incoming_keywords: List[str],
    db: Optional[Any] = None,
    config: Optional[Dict] = None
) -> List[str]:
    """
    Extract database trim variants matching a general trim name.
    Filters results to respect incoming search keywords (VehicleSearchEngine architecture).
    
    Examples:
      extract_trim_family("Sport", "CR-V", 2026, incoming_keywords=["cr-v", "sport"])
      → ["Sport", "Sport AWD", "Sport FWD", "Sport Hybrid"]  (all prefix matches, no extra discriminators)
      
      extract_trim_family("Sport", "CR-V", 2026, incoming_keywords=["cr-v", "sport", "hybrid"])
      → ["Sport Hybrid"]  (only results where all discriminators are in incoming_keywords)
      
      extract_trim_family("Sport", "CR-V", 2026, incoming_keywords=["cr-v", "sport", "awd"])
      → ["Sport AWD"]  (only results where all discriminators are in incoming_keywords)
    
    Args:
        trim_name: General trim name (may be prefix)
        model_name: Model name (e.g., "CR-V", "Accord")
        model_year: Vehicle year
        incoming_keywords: Keywords from Step 4.5 model lookup (already classified)
                          Used to filter results to match downstream VehicleSearchEngine behavior
        db: Optional database connection/service
        config: Optional config with matching rules (trim_discriminators, etc.)
    
    Returns:
        List of database trim names matching the family and incoming keywords
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
    # Classify incoming keywords (already done by tokenizer/classifier)
    incoming_keywords = ["cr-v", "sport", ...]  # May include discriminators like "hybrid", "awd"
    
    # Get family variants, filtered by incoming keywords
    family_trims = extract_trim_family(
        trim_name=trim, 
        model_name=model_name, 
        model_year=year,
        incoming_keywords=incoming_keywords
    )
    
    # Search for each family variant
    # NOTE: family_trims now only contains candidates that won't be rejected
    # by VehicleSearchEngine's discriminator post-filter
    all_results = []
    for family_trim in family_trims:
        result = VehicleSearchEngine.search(
            make="Honda",
            year=year,
            keywords=incoming_keywords  # Pass full keyword set, not just family_trim
        )
        if result:
            all_results.append(result)
    
    # Store results (may be multiple per trim if family match)
    model_mapping[trim] = all_results
```

**Key Insight:** The `incoming_keywords` parameter is passed both to:
1. `extract_trim_family()` - to filter candidates upfront
2. `VehicleSearchEngine.search()` - the actual search (unchanged)

This ensures consistency: candidates filtered by `extract_trim_family()` will not be rejected by VehicleSearchEngine's discriminator post-filter.

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

### Decision 5: Respect VehicleSearchEngine Discriminator Filtering

**Rule:** Pre-filter prefix matches to respect incoming keywords. Remove candidates with trim discriminator keywords (AWD, FWD, Hybrid, etc.) NOT present in incoming_keywords.

**Rationale:**
- VehicleSearchEngine.search() applies strict AND filtering AND post-filter discriminator validation
- Discriminator post-filter excludes rows with extra trim keywords not in the search
- Example: search(keywords=["sport"]) will REJECT "Sport Hybrid" because "hybrid" is not in keywords
- Pre-filtering here ensures only viable candidates reach downstream search
- Maintains architectural consistency: trim family matching respects same rules as keyword-based search

**Implementation:** See pseudocode section (Step 3: Filter Discriminator Keywords)

**Example:**
- Input: trim="Sport", incoming_keywords=["cr-v", "sport"]
  - Prefix match finds: ["Sport AWD", "Sport FWD", "Sport Hybrid"]
  - Filter: all have extra discriminators (AWD, FWD, Hybrid) → remove all
  - Return: []
- Input: trim="Sport", incoming_keywords=["cr-v", "sport", "hybrid"]
  - Prefix match finds: ["Sport AWD", "Sport FWD", "Sport Hybrid"]
  - Filter: only "Sport Hybrid" has all discriminators in keywords → keep it
  - Return: ["Sport Hybrid"]

---

## Unit Test Cases

### Test Class: `TestTrimGeneralizationAlgorithm`

#### Exact Match Cases

```python
def test_extract_exact_match():
    """Exact trim exists in database → return exact."""
    # Mock database with "EX-L"
    result = extract_trim_family("EX-L", "Accord", 2026, ["accord", "ex-l"])
    assert result == ["EX-L"]

def test_extract_no_expansion_on_exact():
    """Even if family exists, return only exact if exact matches."""
    # Mock database with "Touring" and "Touring AWD", "Touring Hybrid"
    result = extract_trim_family("Touring", "CR-V", 2026, ["cr-v", "touring"])
    assert result == ["Touring"]  # Only exact, not family
```

#### Family/Prefix Match Cases (Respecting Incoming Keywords)

```python
def test_extract_family_prefix_match_no_discriminators():
    """No exact match → return prefix matches (no extra discriminators in keywords)."""
    # Mock database with "Sport AWD", "Sport FWD" (no exact "Sport")
    # Incoming keywords don't have "awd" or "fwd", so exclude those
    result = extract_trim_family("Sport", "CR-V", 2026, ["cr-v", "sport"])
    assert result == []  # Both "Sport AWD" and "Sport FWD" have extra discriminators

def test_extract_family_prefix_match_with_discriminators():
    """Prefix match + incoming keywords include discriminators."""
    # Mock database with "Sport AWD", "Sport FWD" (no exact "Sport")
    # Incoming keywords include "awd", so keep "Sport AWD" only
    result = extract_trim_family("Sport", "CR-V", 2026, ["cr-v", "sport", "awd"])
    assert result == ["Sport AWD"]

def test_extract_family_multiple_variants():
    """Return family variants filtered by incoming keywords."""
    # Mock database with "Sport", "Sport AWD", "Sport FWD", "Sport Hybrid"
    # No exact "Sport" exists for 2027
    result = extract_trim_family("Sport", "CR-V", 2027, ["cr-v", "sport"])
    # No incoming discriminators → all variants with discriminators filtered out
    assert result == []
    
    # With "hybrid" keyword
    result = extract_trim_family("Sport", "CR-V", 2027, ["cr-v", "sport", "hybrid"])
    assert result == ["Sport Hybrid"]  # Only hybrid variant passes filter
    
    # With multiple discriminators
    result = extract_trim_family("Sport", "CR-V", 2027, ["cr-v", "sport", "awd", "fwd", "hybrid"])
    assert set(result) == {"Sport AWD", "Sport FWD", "Sport Hybrid"}  # All pass filter
```

#### Edge Cases

```python
def test_extract_no_match():
    """No exact or family match → empty list."""
    result = extract_trim_family("NonExistent", "Accord", 2026, ["accord"])
    assert result == []

def test_extract_case_insensitive():
    """Case-insensitive prefix match, respecting incoming keywords."""
    # Database has "Sport AWD" (capitalized)
    # Without "awd" keyword, filtered out
    result = extract_trim_family("sport", "CR-V", 2026, ["cr-v", "sport"])
    assert result == []  # "Sport AWD" has extra discriminator
    
    # With "awd" keyword
    result = extract_trim_family("sport", "CR-V", 2026, ["cr-v", "sport", "awd"])
    assert "Sport AWD" in result

def test_extract_whitespace_normalization():
    """Whitespace normalized before match."""
    # Input has extra spaces
    # With "awd" keyword
    result = extract_trim_family("  Sport  ", "CR-V", 2026, ["cr-v", "sport", "awd"])
    assert "Sport AWD" in result  # Still finds and returns "Sport AWD"
```

---

## Phase 2 vs. Phase 5 Implementation

### Phase 2 Scope

**Deliverable:** Stub function with signature and basic tests

```python
def extract_trim_family(trim_name, model_name, model_year, incoming_keywords, db=None, config=None):
    """Phase 2 stub: return empty list."""
    # Full implementation in Phase 5
    # incoming_keywords parameter ensures architecture alignment early
    return []
```

**Reason:**
- Requires VehicleSearchEngine integration (Phase 5 dependency)
- Requires actual database access patterns (Phase 5 context)
- Design document establishes algorithm; implementation deferred
- **CRITICAL:** incoming_keywords parameter signature established now to ensure Phase 5 implementation respects VehicleSearchEngine's discriminator filtering

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
