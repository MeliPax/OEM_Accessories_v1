# Design Due Diligence: Hyundai/Genesis Separation

**Purpose:** Identify where this design might fail, deviate from established patterns, or have edge cases that need careful handling during implementation.

---

## Alignment with Existing Architecture ✓

### 1. OEM Pipeline Pattern Consistency

**Finding:** Genesis-as-sibling-OEM matches the existing Mitsubishi/Mazda/Honda pattern exactly.

- All three use identical `OEM_NAME` class constant → auto-routes to config dir, output dir, DQ dir, log dir.
- All three override `load_file()` and delegate steps 1-5 to module functions.
- All three have their own `run_*.py` entry script with the same structure (CONFIG_DIR, DEFAULT_DATA_DIR, auto-discovery, error handling).
- Mitsubishi's `load_file()` doesn't need `source_sheet` config because it reads **all** sheets
  and filters post-parse. Genesis will be first to use pre-parse sheet filtering, but this is an
  *extension* of the pattern, not a deviation.

**Risk:** None. Design follows established convention.

---

## Known Gap: Missing Genesis Standardization Config

**Finding:** `accy_v2/model_lookup/configs/genesis/` is incomplete.

**Current state:**
- ✓ `translator.yaml` exists
- ✓ `classification.yaml` exists
- ✗ `standardization.yaml` does NOT exist
- ✓ `keywords.yaml` exists (undocumented side file, not in config refs)

**Reference:** Hyundai's `enrichment.yaml:90` declares:
```yaml
standardization_config: "${MODEL_LOOKUP_CONFIGS}/genesis/standardization.yaml"
```

**Investigation needed before implementation:**
1. Check whether Hyundai's pipeline actually loads/uses `standardization_config` or if it's
   optional/silently-skipped if missing.
2. Determine if Genesis is intended to have standardization rules or if it can reuse Hyundai's.
3. Either: create a Genesis `standardization.yaml` (copy of Hyundai's if identical structure),
   or remove the path declaration from Genesis's `enrichment.yaml` if not used.

**Action:** Before implementation, run Hyundai pipeline with the real `enrichment.yaml` against
test data, inspect logs/code for any reference to standardization_config loading/failure. If it's
optional, document that. If required, create the missing file.

**Risk Level:** **Medium** — silently skipping a config path could mask future bugs, or loading a
nonexistent path could cause a cryptic error. Must be verified.

---

## Step Module Duplication: Maintenance Risk

**Finding:** Full standalone duplication of 7 step modules (step1-5, step4_5, step5) means
future bug fixes must be applied twice.

**Concrete scenario:**
1. Fix a bug in Hyundai's `step3_standardization.py`.
2. Genesis's copy silently remains broken until someone remembers to port the fix.
3. Two pipelines diverge, creating subtle behavioral differences.

**Mitigation implemented in plan:**
- Documented as an explicit trade-off: "zero coupling in exchange for manual dual-porting."
- Flag this in setup/maintenance documentation so future maintainers understand the cost.
- Consider adding a comment block at the top of Genesis's step modules: "This is a standalone
  copy of hyundai/pipeline/step*.py. Any bug fixes must be ported to both."

**Risk Level:** **Low-to-Medium.** Documented, but requires discipline. Could be mitigated in
future by refactoring into a `_shared` package, but that's explicitly deferred per user's
duplication choice.

---

## Sheet-Name Validation Edge Cases

**Finding:** The `_resolve_sheet()` helper uses case-insensitive matching, which is good for
robustness, but introduces one subtle edge case.

**Scenario:** If a workbook has two sheets that differ only in case (e.g., "Hyundai" and
"hyundai"), the `next()` call returns whichever matches first in `excel.sheet_names` iteration
order. Excel typically preserves insertion order, so this is predictable, but fragile.

**Mitigation:** Accept this as a known limitation. In practice, Excel files from data providers
follow consistent casing, so the risk is low. If a problem arises, the error message ("Found
sheets: [...]") makes debugging obvious.

**Risk Level:** **Low.** Unlikely in practice, documented in error message if it occurs.

---

## Config Loader Double-Instantiation in load_file()

**Finding:** Hyundai's orchestrator currently instantiates `ModularConfigLoader` twice:
1. In `load_file()` to read `enrichment_config` (lines 68-70).
2. In `BasePipeline.run()` at line 155, which reads the full modular config.

**New issue with this plan:** The new code will instantiate a *third* time to read just the
`pipeline.yaml` for the `source_sheet` value:

```python
loader = ModularConfigLoader(self.OEM_NAME, config_root)
pipeline_config = loader.load_pipeline_config()
```

**Why this happened:** `BasePipeline.run()` doesn't pass the already-loaded config into
`load_file()` — the method signature is `load_file(self, file_path: str)` with no config param.
So every orchestrator that needs pre-parse config re-instantiates the loader.

**Is this a problem?**
- **Performance:** Minor. `ModularConfigLoader.__init__` reads ~6 YAML files. Three instantiations
  is redundant but not a bottleneck (milliseconds, not seconds).
- **Consistency:** Mild risk. If `pipeline.yaml` or `enrichment.yaml` change between runs, the
  three reads could see different versions (extremely unlikely in practice, and would only happen
  if a human is editing files concurrently).

**Mitigation:**
- Accept this as the cost of the current architecture. Refactoring `load_file()` to take config as
  a parameter is out of scope for this change and would require changes to `BasePipeline.run()`.
- Document this as a "potential future optimization" if per-run profiling ever shows config
  loading as a bottleneck (it won't).

**Risk Level:** **Very Low.** Documented, performance is fine, consistency risk is theoretical.

---

## Hyundai's Genesis Brand Block Removal from enrichment.yaml

**Finding:** The plan removes Hyundai's `brands.Genesis` block (lines 55-90 of enrichment.yaml)
and moves it to Genesis's own `enrichment.yaml`.

**Verification needed:**
1. Confirm Hyundai's `load_file()` doesn't read or depend on Genesis brand config (it doesn't,
   per research, but double-check the code).
2. Confirm step4_5's `oem_config = config["model_lookup_rules"][vehicle_make]` lookup handles
   only the Hyundai brand config after the Genesis block is removed (it will, by design).
3. Verify no other part of Hyundai's pipeline references Genesis-specific keys like
   `use_single_char_token_matching` (it doesn't per code search, but worth confirming).

**Risk Level:** **Low.** Research confirms Hyundai doesn't reference Genesis config post-separation,
but implementation should do a final grep for any unexpected references.

---

## Landing Zone Discovery: Same Directory for Both

**Finding:** Both `run_hyundai.py` and `run_genesis.py` will discover files in the same
landing-zone location (`landing_zone/hyundai/`), since the source workbook contains both Hyundai
and Genesis sheets.

**Consequence:**
```bash
python accy_v2/run_hyundai.py   # Auto-finds latest .xlsx in landing_zone/hyundai/
python accy_v2/run_genesis.py   # Auto-finds the SAME latest .xlsx in landing_zone/hyundai/
```

Both point to the same physical file, but each processes a different sheet (`Hyundai` vs.
`Genesis`). This is correct and intentional — no issue here.

**Documentation note:** The `run_genesis.py` docstring should clarify: "Shares the landing zone
with run_hyundai.py; each processes a different sheet from the same source workbook."

**Risk Level:** **Very Low.** Design is intentional, but document it to prevent confusion.

---

## Classification Config Path Edge Case in Step4_5 Fix

**Finding:** The bug fix for `_merge_compound_model_names()` changes from:
```python
classification_path_str = oem_config.get("classification_config_path", "").strip()
```
to:
```python
classification_path = oem_config.get("classifier_config")
if not classification_path:
    return tokens
```

**Verification needed:**
1. Confirm `classifier_config` is always a resolved absolute `Path` (not a string) when loaded
   by `ModularConfigLoader`.
2. Confirm it's never `None` in the `enrichment.yaml` structure.
3. Confirm no OEM's config conditionally omits this key (it's in Hyundai's, Genesis's, and
   Mitsubishi's `enrichment.yaml`).

**Risk Level:** **Very Low.** Config loader research confirms `classifier_config` is always
present and resolved, but implementation should do a final spot-check in the actual config
loader code.

---

## Summary of Pre-Implementation Checks

| Item | Risk | Action |
|------|------|--------|
| Missing Genesis `standardization.yaml` | Medium | Verify if required; create or remove ref |
| Step module duplication maintenance | Low | Document in setup/maintenance guide |
| Config loader triple-instantiation | Very Low | Accept; document as future optimization |
| Hyundai Genesis-block removal | Low | Grep for any unexpected Genesis refs |
| Landing zone shared directory | Very Low | Document in run_genesis.py |
| Classification config path assumptions | Very Low | Verify in config_loader_v2.py |

All risks are either documented, expected, or very low likelihood. Proceed with implementation
confidence; address the "Medium" item (Genesis `standardization.yaml`) before code execution.

