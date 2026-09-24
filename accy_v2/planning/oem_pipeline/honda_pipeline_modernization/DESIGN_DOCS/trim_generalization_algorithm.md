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
     
  3. Filter Required Discriminators Only:
     # Classify discriminators: automatic (AWD, FWD, RWD) vs. required (Hybrid, Electric, Coupe)
     # Remove candidates with REQUIRED discriminators NOT in incoming_keywords
     # Keep candidates with AUTOMATIC discriminators (caller will tokenize and pass full keywords to search)
     
     required_discriminators = ["hybrid", "electric", "phev", "fcev", "coupe"]
     automatic_discriminators = ["awd", "fwd", "rwd"]
     filtered_candidates = []
     
     for candidate in family_candidates:
       candidate_tokens = tokenize(candidate).lowercase()  # ["sport", "hybrid"]
       candidate_required = candidate_tokens & required_discriminators
       
       # Check: are there REQUIRED discriminators NOT in incoming_keywords?
       extra_required = candidate_required - incoming_keywords
       
       if extra_required is empty:
          # No extra required discriminators
          # Safe to include - caller will tokenize this candidate fully before search
          filtered_candidates.add(candidate)
     
     return filtered_candidates
```

**Rationale:** 
1. VehicleSearchEngine applies strict AND filtering on all keywords
2. Automatic discriminators (AWD, FWD) don't need pre-filtering—they're just variant indicators  
3. Required discriminators (Hybrid, Electric) DO need filtering—they change engine type fundamentally
4. When caller searches, it should tokenize each family_trim to get full keywords (e.g., "Sport AWD" → ["sport", "awd"]) and pass those to search()
5. This ensures: Sport AWD passes filter → caller tokenizes → search(["cr-v", "sport", "awd"]) → accepted

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
      → ["Sport", "Sport AWD", "Sport FWD"]  (automatic discriminators OK, no required discriminators)
      
      extract_trim_family("Sport", "CR-V", 2026, incoming_keywords=["cr-v", "sport", "hybrid"])
      → ["Sport", "Sport AWD", "Sport FWD", "Sport Hybrid"]  (hybrid keyword present, so include hybrid variant)
      
      extract_trim_family("Sport", "CR-V", 2026, incoming_keywords=["cr-v", "sport", "awd"])
      → ["Sport", "Sport AWD", "Sport FWD"]  (awd in keywords but it's automatic, fwd also returned)
    
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
    incoming_keywords = ["cr-v", "sport", ...]  # May include required discriminators like "hybrid"
    
    # Get family variants, filtered to exclude required discriminators not in keywords
    family_trims = extract_trim_family(
        trim_name=trim, 
        model_name=model_name, 
        model_year=year,
        incoming_keywords=incoming_keywords
    )
    # Returns: ["Sport", "Sport AWD", "Sport FWD"] if no "hybrid" in incoming_keywords
    # Returns: ["Sport", "Sport AWD", "Sport FWD", "Sport Hybrid"] if "hybrid" in incoming_keywords
    
    # Search for each family variant
    all_results = []
    for family_trim in family_trims:
        # CRITICAL: Tokenize each family_trim to get full keywords
        # "Sport AWD" → ["cr-v", "sport", "awd"]
        # "Sport Hybrid" → ["cr-v", "sport", "hybrid"]
        family_keywords = tokenize_and_classify(family_trim, make="Honda")
        
        result = VehicleSearchEngine.search(
            make="Honda",
            year=year,
            keywords=family_keywords  # Pass FULL keywords for this family variant
        )
        if result:
            all_results.append(result)
    
    # Store results (may be multiple per trim if family match)
    model_mapping[trim] = all_results
```

**Key Insight:** The `incoming_keywords` parameter to `extract_trim_family()` filters out REQUIRED discriminators only:
1. `extract_trim_family()` - filters to remove required discriminators (Hybrid, Electric) not in keywords; keeps automatic discriminators (AWD, FWD)
2. **Caller responsibility** - tokenize each family_trim candidate to get its FULL keywords before calling search()
3. `VehicleSearchEngine.search()` - receives full keywords and matches accordingly

This ensures consistency while avoiding silent failures: candidates with automatic discriminators can be included because the caller will tokenize them fully before search.

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

### Decision 5: Respect VehicleSearchEngine Discriminator Filtering (with Discriminator Categories)

**Rule:** Pre-filter prefix matches to exclude REQUIRED discriminators (Hybrid, Electric, etc.) not present in incoming_keywords. Keep AUTOMATIC discriminators (AWD, FWD, RWD) even without explicit keywords.

**Rationale:**
- VehicleSearchEngine.search() applies strict AND filtering with discriminator post-filter validation
- NOT all discriminators are equal:
  - **Automatic discriminators** (AWD, FWD, RWD): just variants of the base trim, don't require explicit keyword
  - **Required discriminators** (Hybrid, Electric, Coupe): fundamental powertrain changes, MUST have explicit keyword
- Example: search(keywords=["sport"]) should INCLUDE "Sport AWD"/"Sport FWD" (auto variants) but EXCLUDE "Sport Hybrid" (required discriminator)
- Pre-filtering ensures only viable candidates reach downstream search
- Caller is responsible for tokenizing each family_trim fully before search()

**Implementation:** See pseudocode section (Step 3: Filter Required Discriminators Only)

**Example:**
- Input: trim="Sport", incoming_keywords=["cr-v", "sport"]
  - Prefix match finds: ["Sport", "Sport AWD", "Sport FWD", "Sport Hybrid"]
  - Filter: "Sport Hybrid" has required discriminator "hybrid" NOT in keywords → remove it
  - Keep: "Sport", "Sport AWD", "Sport FWD" (no required discriminators)
  - Return: ["Sport", "Sport AWD", "Sport FWD"]
  - Note: Caller will tokenize each (e.g., "Sport AWD" → ["cr-v", "sport", "awd"]) before search()

- Input: trim="Sport", incoming_keywords=["cr-v", "sport", "hybrid"]
  - Prefix match finds: ["Sport", "Sport AWD", "Sport FWD", "Sport Hybrid"]
  - Filter: "hybrid" in keywords → keep "Sport Hybrid"
  - Return: ["Sport", "Sport AWD", "Sport FWD", "Sport Hybrid"]

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

#### Family/Prefix Match Cases (Required vs. Automatic Discriminators)

```python
def test_extract_family_automatic_discriminators_included():
    """Automatic discriminators (AWD, FWD) included even without explicit keyword."""
    # Mock database with "Sport", "Sport AWD", "Sport FWD" (no exact "Sport")
    # Incoming keywords: ["cr-v", "sport"] (no awd/fwd)
    # AWD/FWD are automatic → should be included
    result = extract_trim_family("Sport", "CR-V", 2026, ["cr-v", "sport"])
    assert set(result) == {"Sport", "Sport AWD", "Sport FWD"}

def test_extract_family_required_discriminator_excluded():
    """Required discriminators (Hybrid, Electric) excluded without explicit keyword."""
    # Mock database with "Sport", "Sport AWD", "Sport FWD", "Sport Hybrid"
    # Incoming keywords: ["cr-v", "sport"] (no hybrid)
    # Hybrid is required → exclude it
    result = extract_trim_family("Sport", "CR-V", 2026, ["cr-v", "sport"])
    assert set(result) == {"Sport", "Sport AWD", "Sport FWD"}  # Hybrid excluded

def test_extract_family_required_discriminator_included():
    """Required discriminators included when keyword explicitly present."""
    # Mock database with "Sport", "Sport AWD", "Sport Hybrid"
    # Incoming keywords: ["cr-v", "sport", "hybrid"]
    # Hybrid keyword present → include it
    result = extract_trim_family("Sport", "CR-V", 2026, ["cr-v", "sport", "hybrid"])
    assert set(result) == {"Sport", "Sport AWD", "Sport Hybrid"}

def test_extract_family_mixed_discriminators():
    """Automatic and required discriminators handled correctly."""
    # Mock database with "Sport", "Sport AWD", "Sport Hybrid AWD"
    # Incoming keywords: ["cr-v", "sport"]
    # Sport AWD: automatic discriminator → included
    # Sport Hybrid AWD: has required (hybrid) but keyword missing → excluded
    result = extract_trim_family("Sport", "CR-V", 2026, ["cr-v", "sport"])
    assert set(result) == {"Sport", "Sport AWD"}
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
