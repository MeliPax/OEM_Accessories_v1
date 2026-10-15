# FR Header Encoding & Typo Resilience Strategy

**Status:** Proposed  
**Priority:** High (Blocks FR sheet processing)  
**Created:** 2026-10-14  

---

## Problem Statement

The Honda FR (French) sheet column headers use Unicode characters (accented letters: é, è) that are causing exact-match failures in the current config-based normalization approach:

- Excel file: `'Numéro de pièce'` (UTF-8: `b'Num\xc3\xa9ro de pi\xc3\xa8ce'`)
- Config has: `'numéro de pièce'` (might differ at byte level)
- Result: Columns not normalizing → 118 defects flagged instead of ~20 expected

**Root Causes:**
1. Byte-exact string matching fails when Unicode encoding differs slightly
2. No fallback mechanism if exact variant isn't in config list
3. Typos in source files (future risk) not handled
4. Language/region variants scattered across config without pattern

---

## Strategic Solution: Hybrid Approach (Phase 1 + Phase 2)

### Phase 1: Position-Based Hints + Fuzzy Matching (Immediate Fix)

**What:** Enhance header normalization to:
1. Use expected column positions as primary hint
2. Fall back to fuzzy string matching for robustness
3. Log confidence scores for audit trail

**Config Changes:**
```yaml
column_definitions:
  part_number:
    expected_position: 3  # Usually column 3 after Description
    aliases:
      - 'part number'
      - 'part#'
      - 'part num'
      - 'numéro de pièce'
      - 'pièce'
      - 'numero'
    fuzzy_threshold: 0.85  # Match if similarity > 85%
    
  description:
    expected_position: 2
    aliases:
      - 'description'
      - 'la description'
      - 'product'
      - 'nom du produit'
    fuzzy_threshold: 0.85
    
  installed_price:
    expected_position: 7
    aliases:
      - 'installed price'
      - 'prix installé'
      - 'prix install'
      - 'coût d\'installation'
    fuzzy_threshold: 0.85
```

**Code Changes:**
Update `step2_header_normalization.py`:
```python
def _normalize_header_names(raw_names, detection_config, ...):
    """
    Enhanced normalization with position hints + fuzzy matching fallback
    """
    column_definitions = detection_config.get("column_definitions", {})
    norm_mapping = {}
    
    # Build reverse mapping from aliases
    reverse_mapping = {}
    position_hints = {}
    
    for norm_name, definition in column_definitions.items():
        position_hints[norm_name] = definition.get("expected_position")
        for alias in definition.get("aliases", []):
            reverse_mapping[alias.lower()] = norm_name
    
    # Normalize each column
    for col_idx, raw_name in enumerate(raw_names):
        raw_lower = raw_name.lower()
        
        # Try 1: Exact match in aliases
        if raw_lower in reverse_mapping:
            norm_mapping[col_idx] = {
                'normalized': reverse_mapping[raw_lower],
                'confidence': 1.0,
                'method': 'exact_match'
            }
            continue
        
        # Try 2: Position hint + fuzzy match
        best_match = None
        best_score = 0
        
        for norm_name, position_hint in position_hints.items():
            if position_hint == col_idx:
                # Position matches; fuzzy-match the header text
                definition = column_definitions[norm_name]
                aliases = definition.get("aliases", [])
                
                for alias in aliases:
                    score = difflib.SequenceMatcher(
                        None, 
                        raw_lower, 
                        alias.lower()
                    ).ratio()
                    
                    if score > best_score:
                        best_score = score
                        best_match = norm_name
        
        if best_match and best_score >= 0.85:
            norm_mapping[col_idx] = {
                'normalized': best_match,
                'confidence': best_score,
                'method': 'position_hint_fuzzy'
            }
            continue
        
        # Try 3: Fuzzy match anywhere (no position hint)
        for norm_name, definition in column_definitions.items():
            aliases = definition.get("aliases", [])
            
            for alias in aliases:
                score = difflib.SequenceMatcher(
                    None, 
                    raw_lower, 
                    alias.lower()
                ).ratio()
                
                if score > best_score:
                    best_score = score
                    best_match = norm_name
        
        if best_match and best_score >= 0.85:
            norm_mapping[col_idx] = {
                'normalized': best_match,
                'confidence': best_score,
                'method': 'fuzzy_match'
            }
        else:
            # No match found; keep raw name and log
            norm_mapping[col_idx] = {
                'normalized': raw_name,
                'confidence': 0.0,
                'method': 'unmapped'
            }
            dq_logger.log_warning(
                rule_violated="column_name_unmapped_rule",
                issue_description=f"Column not recognized: {raw_name}"
            )
    
    return norm_mapping
```

**Benefits:**
- ✅ Handles Unicode encoding mismatches (fuzzy match is byte-agnostic)
- ✅ Handles typos automatically (fuzzy threshold catches minor errors)
- ✅ Position hints make matching faster and more reliable
- ✅ Single source of truth: one definition per normalized column
- ✅ Audit trail: confidence scores show why each match was made
- ✅ Low complexity: no new services, just enhanced matching logic

---

### Phase 2: HeaderDetector Service (Future Resilience)

**What:** Create a reusable detection service for long-term maintainability

**When:** After Phase 1 proves concept; more sophisticated handling needed

**Components:**
1. `HeaderDetector` class: orchestrates all matching strategies
2. Header mapping cache: remembers learned mappings by OEM/year/file
3. Manual review queue: flags low-confidence matches for human approval
4. Content-based validation: scans actual data to confirm column type
5. DQ reporting: detailed audit trail of header detection

**Benefits:**
- Multiple independent matching strategies
- Machine learning potential (track which matches succeed/fail over time)
- Manual override mechanism
- Reusable across all OEMs
- Long-term solution to header variability problem

---

## Implementation Roadmap

### Phase 1: Immediate (1-2 hours)
- [ ] Rename `column_normalizations` to `column_definitions` in config
- [ ] Add `expected_position` and `fuzzy_threshold` to each column
- [ ] Update `_normalize_header_names()` with fuzzy matching logic
- [ ] Add import: `import difflib`
- [ ] Test with FR sheet → verify 118 defects drop to ~20
- [ ] Update documentation

### Phase 2: Future (if needed)
- [ ] Implement `HeaderDetector` service class
- [ ] Build header mapping cache
- [ ] Add content-based validation
- [ ] Create manual review workflow

---

## Expected Outcomes

**Phase 1 Success Criteria:**
- [ ] FR sheet processes with `<25` defects (currently 118)
- [ ] All main columns normalize: part_number, description, prices, comments
- [ ] Fuzzy matching handles minor typos without false positives
- [ ] Confidence scores show >0.85 for all matched columns
- [ ] No regression in EN sheet processing

**Phase 2 Success Criteria:**
- [ ] HeaderDetector service available for all OEMs
- [ ] Header mappings cached and reused
- [ ] Low-confidence matches logged for review
- [ ] Manual override workflow functional

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| Fuzzy threshold too low, matches wrong columns | Medium | High | Start at 0.85, test with real data, adjust if needed |
| Position hints don't work (columns reordered in future) | Low | Medium | Fallback to pure fuzzy matching (already in code) |
| Performance impact from fuzzy matching | Low | Low | Only used as fallback; exact match is fast path |
| Config validation complexity | Low | Low | Simple validation: check aliases exist, positions reasonable |

---

## Related Issues & Context

- **Primary blocker:** FR sheet has 118 defects, should have ~20
- **Root cause:** Column `'Numéro de pièce'` not normalizing to `'part_number'`
- **Current approach limitation:** Exact string match fails on Unicode/encoding variations
- **Design principle:** All columns defined in config, no hardcoding in code

---

## Approval & Next Steps

**Decision Needed:** Proceed with Phase 1 implementation?

- **YES** → Begin Phase 1 immediately
- **NO** → What alternative approach preferred?
- **LATER** → Schedule for specific date/sprint

Once approved, will:
1. Update detection.yaml config structure
2. Implement fuzzy matching in step2_header_normalization.py
3. Run comprehensive tests
4. Update project tracking documentation
