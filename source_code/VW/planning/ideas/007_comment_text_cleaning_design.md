# 007 — Comment Text Cleaning: Design

**Status:** Idea — all decisions (C1–C8) approved 2026-10-27; next: plan
**Applies to:** the accessory pipeline (plan 003), the `comments` column (`dealerNotes` in the file)
**Asked for:**
- remove HTML (`<p>`, `<b>`, `<br/>`);
- remove leading / trailing `|`, and turn the `||` separators into readable sentences;
- tidy spaces;
- replace links that don't work with directions to the manufacturer's site.

Everything is defined in config, so it's easy to maintain.

## What the data shows (2026-10-27)

654 rows have a comment, but there are only **62 distinct comment texts**.

| Pattern | Distinct texts | Example |
|---|---|---|
| HTML tags | `<p>` 87, `</p>` 86, `<br>` 4, `<br/>` 3, `<b>`/`</b>` 1 | `<p>Only for vehicles with pre-wiring ... 9TL</p>Always install the product ...` |
| `\|` at the start | 8 | `\|Before installing your license plate frame, ...` |
| `\|\|` between lines | 8 | `...under hat shelf. \|\|Weight limit 10 lbs. (5kg)\|\|Not for vehicles with Fender Amplifier\|\|...` |
| `\|` at the end | 0 | (handled anyway) |
| HTML entities (`&amp;`) | 0 | (handled anyway) |
| Non-breaking space | 1 | |
| Space before punctuation | some | `... THULE's warranty claim process .` |
| Links | 1 Salsify, 3 vwhub.com | `Visit https://app.salsify.com/catalogs/fde773be-... for additional product information ...` |

Notes:
- The `||` pattern is a line break (each piece is its own sentence), not an empty value.
- `</p>Always install...` runs two sentences together with no space or full stop.

## The idea: split into sentences, clean each, join

One model handles the tags, the pipes and the spaces: **separators** (pipes, paragraph and line-break tags) split the text into **segments**. Each segment is trimmed and given a full stop if it has none, and the segments are joined back with a space.

```
raw comment
  1. decode HTML entities              &amp; -> &          (none today)
  2. normalize spaces                  non-breaking space -> space
  3. replace links                     link rules (config) -> "Thule.com"
  4. separators -> split               | || <p> </p> <br> <br/>  -> segments
  5. remove other tags                 <b> </b> (inline: removed, text kept)
  6. clean each segment                trim; drop empty; add "." when it has no ending punctuation
  7. join + tidy                       segments joined with " "; collapse spaces; "process ." -> "process."
clean comment                          ("" -> empty)
```

Order matters: links are replaced before splitting, so a URL is never cut apart, and tags are handled before spaces are tidied.

### Before → after (today's data)

| Before | After |
|---|---|
| `\|Installs in top left of trunk under hat shelf. \|\|Weight limit 10 lbs. (5kg)\|\|Not for vehicles with Fender Amplifier\|\|WARNING Do not use the shopping bag hook as a tie down.\|\|Requires 2x ...` | `Installs in top left of trunk under hat shelf. Weight limit 10 lbs. (5kg). Not for vehicles with Fender Amplifier. WARNING Do not use the shopping bag hook as a tie down. Requires 2x ...` |
| `<p>Only for vehicles with pre-wiring ... PR Code 9TG, 9TJ, 9TL</p>Always install the product according to ...` | `Only for vehicles with pre-wiring ... PR Code 9TG, 9TJ, 9TL. Always install the product according to ...` |
| `<p>Visit https://app.salsify.com/catalogs/fde773be-fbbd-410b-99ab-5178d20956b6 for additional product information, information on spare parts, and THULE's warranty claim process.</p>` | `Visit Thule.com for additional product information, information on spare parts, and THULE's warranty claim process.` |
| `<p>Visit Thule.com for additional product information, ... and THULE’s warranty claim process .</p><p>Always install ...` | `Visit Thule.com for additional product information, ... and THULE’s warranty claim process. Always install ...` |

The last row shows the Salsify replacement matching the wording VW already uses on other Thule parts.

## Config: a `text_cleaning:` block in `accessories.yaml`

```yaml
text_cleaning:
  columns: [comments]                     # which columns get cleaned (product_description could be added later)
  decode_html_entities: true              # &amp; -> &, &nbsp; -> space
  separators:                             # each one ends a sentence
    pipes: true                           # | and || (and | at the start / end)
    tags: [p, br, li, div]                # <p> </p> <br> <br/> ... (open, close or self-closing)
  remove_tags: any_other                  # any other tag (<b>, <span>, ...) is removed, its text kept; listed in the log
  sentence_end: "."                       # added to a segment without ending punctuation
  ending_punctuation: [".", "!", "?", ":", ";"]
  join_with: " "
  link_rules:                             # a link that doesn't work -> a useful direction (whole URL or a prefix)
    - match: https://app.salsify.com/catalogs/fde773be-fbbd-410b-99ab-5178d20956b6
      match_type: exact                   # exact | prefix
      replace_with: Thule.com
      reason: Salsify catalogue link is not public; Thule.com has the product, spare parts and warranty information
  allowed_link_hosts: [www.vwhub.com]     # links on these hosts are kept as they are (C3: VW dealer portal)
```

Why `link_rules` match the URL and not the whole sentence: the sentence around it ("Visit … for additional product information …") stays as VW wrote it. Only the dead link changes, so one rule fixes every comment that uses that link.

## Governance

| Practice | How |
|---|---|
| No hard-coded text | Separators, tags, punctuation, link rules and allowed hosts are all config; `load_accessory_config` validates them (unknown column, empty `replace_with`, bad `match_type` -> `CONFG_` error) |
| Clean once per distinct text | 62 distinct comments are cleaned once and mapped back to the 654 rows (the lookup pattern from idea 003) |
| Before → after for every change | Change log: one row per distinct comment changed, with the rules that fired (`html_tags`, `pipes`, `link_rule: salsify -> Thule.com`, `space_before_punctuation`) and the row count |
| New links never slip through | A link that matches no `link_rule` and no `allowed_link_hosts` gets `ACCESS_CLEAN_UNREVIEWED_LINK` (warning): the URL, the part, and the fix ("add a link rule, or add the host to allowed_link_hosts") |
| New markup is visible | A tag outside the configured lists is removed and logged (`ACCESS_CLEAN_UNKNOWN_TAG`, info), so the config can be updated |
| Lineage | The dict keeps `comments_source` (raw) next to `comments` (clean); the export shows the clean text |
| Clean before dedupe | Cleaning runs before duplicate removal, so `<p>X</p>` and `X` count as the same comment and don't raise false `ACCESS_STGNG_DUPLICATE_CONFLICT` flags |

## What it gives on today's data (estimate)

| | Count |
|---|---|
| Distinct comments cleaned | 62 (about 40 change) |
| Comments with HTML removed | about 35 |
| Comments with pipes turned into sentences | 8 |
| Links replaced | 1 (Salsify → Thule.com) |
| Links flagged `ACCESS_CLEAN_UNREVIEWED_LINK` | 0 (the 3 vwhub.com links are on an allowed host, C3) |

## Decisions

| # | Question | Proposed |
|---|---|---|
| C1 | One "split into sentences, clean, join" model for pipes and paragraph tags, adding `.` where a sentence has none? | ✅ 2026-10-27: Yes |
| C2 | Link rules replace only the URL (exact or prefix match), keeping the sentence around it? | ✅ 2026-10-27: Yes |
| C3 | The 3 `vwhub.com` links (VW dealer portal, technician references): keep or replace? | ✅ 2026-10-27: **keep**: `allowed_link_hosts: [www.vwhub.com]` |
| C4 | Every link not covered by a rule or an allowed host is flagged for review? | ✅ 2026-10-27: Yes |
| C5 | Clean once per distinct text, before duplicate removal? | ✅ 2026-10-27: Yes |
| C6 | Keep `comments_source` (raw) in the dict; export the clean text? | ✅ 2026-10-27: Yes |
| C7 | Clean `comments` only for now; `product_description` later if needed (`columns:` makes it a one-word change)? | ✅ 2026-10-27: Yes |
| C8 | Normalize curly quotes (`THULE’s` → `THULE's`)? | ✅ 2026-10-27: No for now (cosmetic); can be a config switch later |
