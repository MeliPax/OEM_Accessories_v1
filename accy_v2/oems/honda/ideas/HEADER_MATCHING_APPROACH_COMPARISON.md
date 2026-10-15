# Header Matching Approach: Hyundai vs Honda Analysis

**Created:** 2026-10-14  
**Purpose:** Compare existing OEM patterns with Honda requirements

---

## Current OEM Approaches

### Hyundai/Genesis/Mitsubishi/Mazda: Keyword-Based Substring Matching

**How it works:**
```yaml
part_number:
  key_words:
    must_have:
      - part
      - number
    must_have_one_of: []
    not_have: []
```

**Matching logic (from `core/helpers/column_mapper.py`):**
```python
def column_type_finder(col_name: str, column_definition: dict):
    col_lower = col_name.lower()
    
    for mapped_name, spec in column_definition.items():
        kw = spec["key_words"]
        not_have = [k.lower() for k in kw.get("must_not_have", [])]
        must_have = [k.lower() for k in kw.get("must_have", [])]
        must_have_one_of = [k.lower() for k in kw.get("must_have_one_of", [])]

        # Rule 1: If ANY must_not_have keyword is present, skip
        if any(k in col_lower for k in not_have):
            continue
        
        # Rule 2: ALL must_have keywords must be present
        if not all(k in col_lower for k in must_have):
            continue
        
        # Rule 3: At least ONE must_have_one_of keyword must be present
        if must_have_one_of and not any(k in col_lower for k in must_have_one_of):
            continue

        return {col_name: mapped_name}  # ✅ MATCH FOUND
    
    return {col_name: None}  # ❌ NO MATCH
```

**Key Characteristics:**
- ✅ Deterministic (no probability scores)
- ✅ Case-insensitive substring matching
- ✅ Encoding-agnostic (substring doesn't care about é vs e)
- ✅ Works with typos (partial matching)
- ⚠️ Can match wrong columns if keywords overlap
- ⚠️ Requires careful keyword selection (not too general, not too specific)

**Example from Hyundai Config:**
```yaml
# Distinguish English from French descriptions by keyword rules
english_description:
  key_words:
    must_have:
      - accessory
      - description
    not_have:
      - (fr)

french_description:
  key_words:
    must_have:
      - accessory
      - description
      - (fr)
    not_have: []
```

---

## Honda's Challenge

**Problem:** Exact substring matching fails due to position variability

Hyundai files have **consistent column positions and standardized headers** (part, accessory, model year, etc.). So keyword matching (e.g., "must have 'part' AND 'number'") works perfectly.

**Honda files are different:**
- **Section-based layout** (6 sections, each with its own headers)
- **Within-section position consistency** (Column 3 is always part_number within a section)
- **Encoding variability** (Unicode accents: é, è, ñ)
- **Language-specific headers** (FR headers completely different from EN)
- **Minor variations** ("Numéro de pièce" vs "número de piéce" spelling differences)

---

## Three Possible Solutions for Honda

### Option A: Adopt Hyundai's Keyword Approach (SIMPLE)

Use Hyundai's exact substring matching with `must_have` / `must_have_one_of` / `not_have` rules:

```yaml
column_definitions:
  part_number:
    key_words:
      must_have:
        - part          # Matches "part number", "Part#", etc.
        - number
      must_have_one_of: []
      not_have:
        - description   # Don't match if column also has "description"
  
  description:
    key_words:
      must_have:
        - description
      must_have_one_of: []
      not_have: []
```

**Pros:**
- ✅ Reuses proven existing code (`map_all_columns()`)
- ✅ No new implementation needed
- ✅ Deterministic (no fuzzy scores)
- ✅ Case-insensitive, encoding-agnostic

**Cons:**
- ❌ Keywords must be present in column name
- ❌ Won't work for "Numéro de pièce" (no "part" or "number" keyword!)
- ❌ FR headers require different keyword sets
- ❌ Position information ignored

**Honda Fit: POOR** — FR headers have completely different keywords

---

### Option B: Hybrid Position + Keyword Matching (RECOMMENDED)

Enhance Hyundai's approach with **position hints** as primary, keywords as fallback:

```python
def column_type_finder_with_position(
    col_idx: int,
    col_name: str,
    column_definition: dict,  # Enhanced with expected_position
    expected_positions: dict
):
    """
    Three-layer matching:
    1. Check if position matches expected
    2. If yes, validate with keywords as confirmation
    3. If no, try keyword-only fallback
    """
    
    # Layer 1: Position check
    for norm_name, spec in column_definition.items():
        expected_pos = spec.get("expected_position")
        if expected_pos == col_idx:
            # Position matched; now validate with keywords
            keywords = spec["key_words"]
            col_lower = col_name.lower()
            
            # Keyword validation (same as Hyundai)
            if validate_keywords(col_lower, keywords):
                return {col_name: norm_name, "confidence": "position_match"}
            # Position matched but keywords don't confirm
            # Could be encoding issue; still mark as match
            return {col_name: norm_name, "confidence": "position_only"}
    
    # Layer 2: Keyword-only fallback (Hyundai approach)
    result = column_type_finder(col_name, column_definition)
    if result[col_name]:
        return {col_name: result[col_name], "confidence": "keyword_match"}
    
    # Layer 3: No match
    return {col_name: None, "confidence": "unmapped"}
```

**Config Structure:**
```yaml
column_definitions:
  part_number:
    expected_position: 3  # NEW: Position hint (0-indexed within section)
    key_words:
      must_have:
        - part
      must_have_one_of:
        - number
        - numéro          # French variant
        - numero          # Spanish variant
        - pièce           # French synonym
      not_have: []
  
  description:
    expected_position: 2
    key_words:
      must_have:
        - description
      must_have_one_of: []
      not_have: []
```

**Pros:**
- ✅ Position provides 100% confidence (most reliable signal)
- ✅ Keywords provide confirmation
- ✅ Works with FR headers (fuzzy keywords like "pièce" match "Numéro de pièce")
- ✅ Encoding-agnostic (substring matching)
- ✅ Reuses Hyundai infrastructure, minimal new code
- ✅ Deterministic confidence levels

**Cons:**
- ⚠️ Requires knowing expected positions per section (easy for Honda)
- ⚠️ Slight complexity increase (position + keyword validation)

**Honda Fit: EXCELLENT** — Leverages Honda's consistent section structure

---

### Option C: Pure Fuzzy Matching (from FR strategy doc) (PROBABILISTIC)

Use `difflib.SequenceMatcher()` for soft similarity scoring:

```python
def fuzzy_match_columns(col_name, aliases, threshold=0.85):
    best_score = 0
    for alias in aliases:
        score = difflib.SequenceMatcher(None, col_name.lower(), alias.lower()).ratio()
        if score > best_score:
            best_score = score
    
    return best_score > threshold, best_score
```

**Pros:**
- ✅ Handles encoding/typo variations well
- ✅ Simple to understand

**Cons:**
- ❌ Probabilistic (confidence scores feel uncertain)
- ❌ Can match wrong columns if names are similar
- ❌ Doesn't leverage position information
- ❌ Different from established OEM patterns

**Honda Fit: ADEQUATE** — Works, but breaks from OEM convention

---

## Recommendation: Option B (Hybrid Position + Keywords)

### Why?

1. **Aligns with existing OEM pattern** — Reuses Hyundai's proven `column_type_finder()`
2. **100% confidence under expected conditions** — Position alone is sufficient
3. **Minimal new code** — Add position layer on top of existing keyword logic
4. **Section-aware** — Leverages Honda's structured section layout
5. **FR-friendly** — Keywords include language variants ("pièce", "numéro", etc.)
6. **Deterministic** — No probabilistic scoring; explicit confidence levels
7. **Auditable** — Can explain exactly why each column was matched

### Implementation Scope

**Phase 1 (2-3 hours):**
1. Enhance `column_type_finder()` with position parameter (1-2 new functions)
2. Update `map_all_columns()` to pass column index
3. Update Honda config with `expected_position` for each column
4. Add language-variant keywords to `key_words.must_have_one_of`
5. Test with EN and FR sheets

**Phase 2 (Future):**
- If positions become inconsistent, add content validation (data pattern check)
- Build cache of learned header mappings by file

### Config Example

```yaml
# accy_v2/oems/honda/config/detection.yaml

# REPLACES column_normalizations with column_definitions
column_definitions:
  part_number:
    expected_position: 3  # Usually 3rd column after Description
    key_words:
      must_have:
        - part
      must_have_one_of:
        - number
        - numéro
        - numero
        - pièce
        - "#"
      not_have:
        - description
  
  description:
    expected_position: 2
    key_words:
      must_have:
        - description
      must_have_one_of:
        - la
      not_have: []
  
  dealer_net:
    expected_position: 4
    key_words:
      must_have:
        - net
      must_have_one_of:
        - dealer
        - prix
      not_have: []
  
  # ... more columns
```

---

## Migration Path

1. **Week 1:** Implement Option B (hybrid position + keywords)
2. **Week 2:** Test thoroughly with EN and FR sheets
3. **Document** as new best practice for section-based OEMs
4. **Future:** Consider applying to other section-based files (if any)

---

## Decision

**Question:** Should we implement Option B (Hybrid Position + Keywords)?

- **YES** → Proceed with Option B (aligns with OEM patterns, solves FR issue, 100% confidence)
- **NO** → Alternative preference?
- **CLARIFICATION** → Need more analysis first?

