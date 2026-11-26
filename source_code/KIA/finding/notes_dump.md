# Kia accessories: data quality findings (notes dump)

Source: `datasets/KIA 202604 Accessories Application Chart.xlsx`, sheet `Accy List` (2,462 records), and `datasets/kia_models_catalogue.csv` (1,736 rows).
`xl_row` is the row number in Excel (the header is row 1), so each example can be found in the workbook.

Each finding gives what it is, how many, real example records (up to 8–13 shown), and the decision or rule it needs.

## Summary

| # | Finding | How many |
|---|---|---|
| A1 | Missing labour hours | 310 rows, 20 part numbers |
| A2 | Same part, different labour hours on different models | 29 part numbers |
| A3 | Labour hours outlier | 1 row |
| A4 | Orphaned records (no trim applies) | 8 rows, 4 part numbers |
| A5 | Placeholder part number `TBD` | 5 rows |
| A6 | Part numbers read as numbers | 36 rows, 6 part numbers |
| A7 | Unusual part number formats | 5 part numbers |
| A8 | Year range reversed | 1 row |
| A9 | Model / year not plausible | 1 row |
| A10 | Same trim listed twice in one record | 3 rows |
| A11 | Same part, same vehicle, two records | 2 rows (1 part) |
| B1 | Same part, different English descriptions | 45 part numbers |
| B2 | Same English description, different French translations | 37 English descriptions |
| B3 | French description missing | 1 row |
| B4 | Category / group translation not one-to-one | 1 group each way |
| B5 | Text formatting | see counts |
| C1 | Same trim written different ways | 5 variant groups |
| C2 | Trims used only once for a model | 2 model/trim pairs |
| C3 | Packages in the trim columns | 10 model/package pairs |
| C4 | `+` trims are real trims (not an issue) | 1204 trim cells |
| D1 | Fitment rules written in the comments | 59 rows |
| E1 | Outgoing parts | 123 rows |
| E2 | New parts flag | 65 rows |
| E3 | Bundles (`PKG Code`) | 689 rows |
| E4 | Blank written two ways | 2,190 rows |
| E5 | `#N/A` formula errors | 63 rows |
| E6 | Q3 price change list doesn't match the Accy List | 17 of 18 parts |
| E7 | `Notes` sheet is a change log | 4 entries |
| E8 | Excel filter covers only part of the sheet | sheet-level |
| E9 | Other sheets | 14 sheets |
| F1 | Catalogue has exact duplicate rows | 868 duplicate rows of 1736 |
| F2 | Catalogue: model name only inside Description | 1736 rows |
| F3 | Catalogue model names: typos, case, spelling | 8 variants shown |
| F4 | Partial matching assigns wrong vehicles | 68 partial matches to review |
| F5 | Year coverage differs | 7 accessory model/year pairs |

## A. Record-level data quality issues

### A1. Missing labour hours

`Suggested Labour Hours` is blank.

**How many:** 310 rows, 20 part numbers

| xl_row | part | model | from | to | desc_en | labour |
|---|---|---|---|---|---|---|
| 31 | 000AM472010 | K5 | 2021 | 2024 | WARMUP KIT 1200W |  |
| 32 | 000AM472007 | K5 | 2021 | 2024 | WARMUP KIT 1200W - BT |  |
| 55 | 000AK17MP01 | K5 | 2021 | 2024 | ALLOY WHEEL 17 x 7 |  |
| 56 | 000AK18MP01 | K5 | 2021 | 2024 | ALLOY WHEEL 18 x 7.5 |  |
| 57 | 000AK18MP02 | K5 | 2021 | 2024 | ALLOY WHEEL 18 x 7.5 |  |
| 58 | 000AK18MP03 | K5 | 2021 | 2024 | ALLOY WHEEL 18 x 7.5 |  |
| 68 | AMH40AP016B | K5 | 2021 | 2024 | STEEL WHEEL 16 x 6.5  |  |
| 69 | AMH40AP016BP | K5 | 2021 | 2024 | STEEL WHEEL 16 x 6.5  |  |

**Decision / rule needed:** Blank is not 0. Get the hours from Kia, or fill only from the same part **on the same model** (see A2). Tag every fill.


### A2. Same part, different labour hours on different models

The notebook's fill rule assumes one part = one labour value. Not true: hours depend on the vehicle.

**How many:** 29 part numbers

| xl_row | part | model | from | to | desc_en | labour |
|---|---|---|---|---|---|---|
| 283 | 000AM481003 | Sorento HEV | 2022 | 2024 | PREMIUM BLOCK HEATER KIT | 1.0 |
| 365 | 000AM481003 | Sorento HEV PE | 2025 | 2026 | PREMIUM BLOCK HEATER KIT | 1.0 |
| 450 | 000AM481003 | Sorento PHEV | 2022 | 2024 | PREMIUM BLOCK HEATER KIT | 1.0 |
| 535 | 000AM481003 | Sorento PHEV PE | 2025 | 2026 | PREMIUM BLOCK HEATER KIT | 1.0 |
| 2355 | 000AM481003 | K4 | 2025 | 2026 | BLOCK HEATER - 2.0L | 1.0 |
| 1928 | 000AM481003 | Forte PE | 2022 | 2024 | PREMIUM BLOCK HEATER 1.6L-T GDI - A/T  | 1.0 |
| 1884 | 000AM481003 | Forte 5 PE | 2022 | 2024 | PREMIUM BLOCK HEATER 1.6L-T GDI - A/T  | 1.0 |
| 1723 | 000AM481003 | Seltos | 2021 | 2026 | PREMIUM BLOCK HEATER KIT (2.0L) | 1.0 |
| 2449 | 000AM481003 | Rio/Rio5 | 2018 | 2023 | PREMIUM BLOCK HEATER KIT - MT | 1.0 |
| 1185 | 000AM481003 | Sportage PHEV PE | 2026 | 2026 | PREMIUM BLOCK HEATER KIT (HEV) | 1.5 |
| 1110 | 000AM481003 | Sportage HEV | 2023 | 2025 | PREMIUM BLOCK HEATER KIT (HEV) | 1.5 |
| 1035 | 000AM481003 | Sportage HEV PE | 2026 | 2026 | PREMIUM BLOCK HEATER KIT (HEV) | 1.5 |
| 1263 | 000AM481003 | Sportage PHEV | 2023 | 2025 | PREMIUM BLOCK HEATER KIT (HEV) | 1.5 |

_Note:_ Also: wheels `000AK16B253`, `000AK17B244`, `000AK18HY002` are 0.3 h on most models but 0.2 h on K4 / K4 Hatchback / EV4.

**Decision / rule needed:** Labour is per **part + model**, not per part. Fill rule: same part, same model (or model family), else ask Kia.


### A3. Labour hours outlier

One value far above the rest (median 0; every other value is 1.5 h or less).

**How many:** 1 row

| xl_row | part | model | from | to | desc_en | labour |
|---|---|---|---|---|---|---|
| 1874 | DL131ADX01 | Forte 5 PE | 2022 | 2024 | ALL WEATHER MAT - COMPLETE ASSY | 4.0 |

**Decision / rule needed:** Confirm with Kia: 4.0 h for a mat set looks like a typo (0.4?). Add a range check (e.g. warn above 2 h).


### A4. Orphaned records (no trim applies)

All trim columns blank: the accessory is attached to no vehicle.

**How many:** 8 rows, 4 part numbers

| xl_row | part | model | from | to | desc_en | comments_en |
|---|---|---|---|---|---|---|
| 1031 | DWH46AP000 | Sportage HEV PE | 2026 | 2026 | MUD FLAPS BY RALLY ARMOR |  |
| 1106 | DWH46AP000 | Sportage HEV | 2023 | 2025 | MUD FLAPS BY RALLY ARMOR |  |
| 1181 | DWH46AP000 | Sportage PHEV PE | 2026 | 2026 | MUD FLAPS BY RALLY ARMOR |  |
| 1259 | DWH46AP000 | Sportage PHEV | 2023 | 2025 | MUD FLAPS BY RALLY ARMOR |  |
| 2273 | TBD | K4 Hatchback | 2026 | 2026 | CARGO TRAY | In development |
| 2293 | TBD | K4 Hatchback | 2026 | 2026 | MUD FLAPS BY RALLY ARMOR | In development |
| 2407 | 000AM481004 | Stinger | 2019 | 2023 | PREMIUM BLOCK HEATER KIT (2.0) |  |
| 2414 | 9999611001 | Stinger | 2018 | 2019 | WHEEL LOCKS |  |

**Decision / rule needed:** Define: does no trim mean *all trims* of the model, *not yet known* (in development), or an error? Same rule for every OEM.


### A5. Placeholder part number `TBD`

5 different products share the part number `TBD` (K4 Hatchback 2026, "In development"). 3 have trims, so they pass the orphan check and **would be uploaded as part `TBD`**.

**How many:** 5 rows

| xl_row | part | model | from | to | trims | desc_en | comments_en | msrp |
|---|---|---|---|---|---|---|---|---|
| 2273 | TBD | K4 Hatchback | 2026 | 2026 |  | CARGO TRAY | In development | 139.99 |
| 2274 | TBD | K4 Hatchback | 2026 | 2026 | LX, EX | CROSS BARS | In development | 969.8 |
| 2289 | TBD | K4 Hatchback | 2026 | 2026 | LX, EX, EX+, EX Prem, GTL, GTL Limited | WINDOW VISOR | In development | 238.49 |
| 2290 | TBD | K4 Hatchback | 2026 | 2026 | LX, EX, EX+, EX Prem | BLOCK HEATER - 2.0L | To be confirmed | 205.61 |
| 2293 | TBD | K4 Hatchback | 2026 | 2026 |  | MUD FLAPS BY RALLY ARMOR | In development | 382.87 |

**Decision / rule needed:** Placeholder part numbers (TBD, blank, N/A) are never output. Hold them as *in development* until Kia gives a real number.


### A6. Part numbers read as numbers

With a default read, these cells load as integers, mixed with text. Sorting and joins break, and leading zeros would be lost.

**How many:** 36 rows, 6 part numbers

| xl_row | part | model | from | to | desc_en |
|---|---|---|---|---|---|
| 67 | 9999711002 | K5 | 2021 | 2024 | WHEEL LOCKS |
| 161 | 9999782768 | Sorento | 2021 | 2023 | WHEEL LOCK SET - BLACK |
| 680 | 9999711003 | Carnival | 2021 | 2024 | WHEEL LOCKS |
| 1644 | 9999761000 | Soul | 2020 | 2025 | SPORTZ COVE TENT: S/M |
| 1645 | 9999786000 | Soul | 2020 | 2025 | SPORTZ DOME-TO-GO-TENT |
| 2414 | 9999611001 | Stinger | 2018 | 2019 | WHEEL LOCKS |

_Note:_ They all start `9999` (wheel locks, tents): looks like dealer/aftermarket numbering. Confirm with Kia.

**Decision / rule needed:** Always read Part Number as text (`dtype=str`).


### A7. Unusual part number formats

Part number lengths seen (length: rows): {3: 5, 9: 69, 10: 1425, 11: 744, 12: 178, 13: 11, 14: 30}. Suffixes and kit numbers below.

**How many:** 5 part numbers

| xl_row | part | model | from | to | desc_en |
|---|---|---|---|---|---|
| 49 | 99997TRUNKPRO2 | K5 | 2021 | 2024 | TRUNK REAR BUMPER PROTECTOR LARGE |
| 869 | CHF67AC000-C | Sportage PE | 2026 | 2026 | HITCH WIRING HARNESS |
| 1800 | S920HITCH01KIT | Telluride | 2020 | 2022 | TRAILER HITCH (FULL KIT P/N) 2" |
| 1809 | S920HOODP01KIT | Telluride | 2020 | 2026 | HOOD PROTECTOR W/ BADGE (KIT) |
| 1973 | CVF67AC003-C | EV6 | 2022 | 2023 | HITCH WIRING HARNESS |

**Decision / rule needed:** Agree a valid pattern (letters/digits, 9 to 14 characters, allowed suffixes like `-C`, `KIT`). Anything else is an issue.


### A8. Year range reversed

`Model Year From` is after `Model Year To`.

**How many:** 1 row

| xl_row | part | model | from | to | trims | desc_en |
|---|---|---|---|---|---|---|
| 368 | 000KCPENCR5 | Sorento HEV PE | 2025 | 2023 | LX, EX, SX | T/U PEN CR5 |

_Note:_ Checked against the same part on other models: the range is 2023 to 2025, so it's a typo.

**Decision / rule needed:** Approved fix: swap and tag (`fix_swapped_years`). Keep the check so the next one is caught.


### A9. Model / year not plausible

A PE (facelift) model with years before the facelift. Base `Sorento` runs 2021 to 2023 and the other `Sorento PE` rows start 2024, so 2021 looks wrong.

**How many:** 1 row

| xl_row | part | model | from | to | desc_en |
|---|---|---|---|---|---|
| 183 | R5F03AP400 | Sorento PE | 2021 | 2025 | TRAILER HITCH 2" INCH |

**Decision / rule needed:** Check year ranges per model against the vehicle catalogue (PE models included). Confirm with Kia: should it be 2024 to 2025?


### A10. Same trim listed twice in one record

A trim appears in two trim columns of the same row.

**How many:** 3 rows

| xl_row | part | model | from | to | trims | desc_en |
|---|---|---|---|---|---|---|
| 872 | DWF21ACA00CA | Sportage PE | 2026 | 2026 | X-Line, X-Line Limited, X-Line Limited | CROSS BARS (FLOATING) |
| 949 | DWF21ACA00CA | Sportage | 2023 | 2025 | X-Line, X-Line Limited, X-Line Limited | CROSS BARS (FLOATING) |
| 2426 | H9H22AP100 | Rio/Rio5 | 2018 | 2022 | LX, LX, S | SIDE VISORS - RIO4 |

**Decision / rule needed:** Treat as a copy error: keep one (tagged). Ask Kia whether a different trim was meant (e.g. `LX` twice on Rio).


### A11. Same part, same vehicle, two records

Two rows give the same part / model / years / trims; only the description differs.

**How many:** 2 rows (1 part)

| xl_row | part | model | from | to | trims | desc_en | msrp | labour |
|---|---|---|---|---|---|---|---|---|
| 2147 | DOH14AP100 | EV9 | 2024 | 2026 | Light RWD (Short Range), Wind RWD, Land AWD, Land Plus Package | COMPLETE ASSY-CARPET MATS (7P) | 279.81 | 0.0 |
| 2150 | DOH14AP100 | EV9 | 2024 | 2026 | Light RWD (Short Range), Wind RWD, Land AWD, Land Plus Package | CARPET MATS (7P) | 279.81 | 0.0 |

_Note:_ Checked for any other part + model with overlapping year ranges in different rows (which would also create duplicate fitments after year expansion): none, apart from the `TBD` rows (A5), which only share the placeholder. Keep the overlap check as a rule.

**Decision / rule needed:** Keep one record per part + model + year + trim. Which description wins? (`COMPLETE ASSY-` may be the newer name.)


## B. Descriptions and translation

### B1. Same part, different English descriptions

One part number, several descriptions across models (generic vs detailed, or model-specific notes in the name).

**How many:** 45 part numbers

| xl_row | part | model | desc_en |
|---|---|---|---|
| 59 | 000AK17B244 | K5 | B244 ALLOY WHEEL 17 X 7 - 5 X 114.3 |
| 855 | 000AM29152 | Carnival HEV | TPMS KIT 4 PACK |
| 1859 | 000AM29152 | Telluride | TPMS KIT |
| 1887 | 000AM29165 | Forte 5 PE | TPMS  |
| 1932 | 000AM29165 | Forte PE | TPMS (OE PARTS KIT) |
| 2020 | 000AM29152 | EV6 | TPMS KIT 4 PACK - 19" |
| 2235 | 000AK17B244 | EV4 | ALLOY WHEEL - 17" |

**Decision / rule needed:** Is the description per part, or per part + model? If per part, pick a master description (e.g. from Kia's part master).


### B2. Same English description, different French translations

Inconsistent translations, and some are wrong. `ACCESSORY HITCH` → `ACCESSOIRES DE TOIT` means *roof accessories*. `TOUS LES TAPIS MÉTÉO` is a literal machine translation of "all weather mats".

**How many:** 37 English descriptions

| xl_row | part | model | desc_en | desc_fr |
|---|---|---|---|---|
| 2 | L3F03AP000 | K5 | ACCESSORY HITCH | ACCESSOIRES DE TOIT |
| 7 | L2131ADX00 | K5 | ALL WEATHER MATS | TOUS LES TAPIS MÉTÉO |
| 1174 | DWF13AH200 | Sportage PHEV PE | ALL WEATHER LINERS - COMPLETE SET | TAPIS MOULER - ENSEMBLE COMPLET |
| 1326 | ATH03AP000 | Niro HEV | ACCESSORY HITCH | HITCH ACCESSOIRE |
| 1705 | Q5131ADX00 | Seltos | ALL WEATHER MATS | PROTÈGE-MOQUETTES TOUTES SAISONS |
| 2268 | GGF13AU000CA | K4 Hatchback | ALL WEATHER LINERS - COMPLETE SET | LINER TOUT SAISON 4 PORTE |
| 2417 | H8131ADX00RE | Rio/Rio5 | ALL WEATHER MATS | TAPIS DE PLANCHER TOUTES SAISONS |

**Decision / rule needed:** French needs a review step; rules can't detect a wrong meaning. Option: an EN→FR glossary for common terms, and flag deviations.


### B3. French description missing

English filled, French blank.

**How many:** 1 row

| xl_row | part | model | from | to | desc_en | desc_fr |
|---|---|---|---|---|---|---|
| 1859 | 000AM29152 | Telluride | 2024 | 2026 | TPMS KIT |  |

**Decision / rule needed:** Bilingual output needs both: block or flag.


### B4. Category / group translation not one-to-one

`Hitch Accessory` has two French group names; the French group `Attelage de remorque` is used for two English groups.

**How many:** 1 group each way

| xl_row | part | model | accessory_group_(en) | accessory_group_(fr) |
|---|---|---|---|---|
| 24 | 99997CAP114 | K5 | Hitch Accessory | Accessoire d'attelage |
| 137 | 99997CAP002 | Sorento | Hitch Accessory | Attelage de remorque |

**Decision / rule needed:** Keep a fixed EN↔FR mapping table for categories and groups; flag anything not in it.


### B5. Text formatting

Spaces, non-breaking spaces (shown as ⍽), line breaks (⏎), mixed case (`18 x 7.5` vs `18 X 7.5`), en dashes `–` and curly quotes `’ ”`.

- `desc_en`: leading/trailing spaces 123, double spaces 63, non-breaking spaces 0, line breaks 0
- `desc_fr`: leading/trailing spaces 57, double spaces 31, non-breaking spaces 16, line breaks 0
- `comments_en`: leading/trailing spaces 25, double spaces 0, non-breaking spaces 0, line breaks 365

**How many:** see counts

| xl_row | part | desc_en | desc_fr |
|---|---|---|---|
| 5 | L3F17AP001 | ALL WEATHER LINER FRONT (NEW LOGO) | TOUTES SAISONS LINERS -⍽ AVANT (NOUVEAU LOGO) |
| 6 | L3F17AP101 | ALL WEATHER LINER REAR (NEW LOGO) | TOUTES SAISONS LINERS -⍽ ARRIÈRE (NOUVEAU LOGO) |
| 16 | 000AM481010 | PREMIUM BLOCK HEATER KIT- 1.6T | TROUSSE CHAUFFE-BLOC 1RE QUALITÉ (1,6⍽T) |
| 21 | 000KCPENEB | T/U PEN EB  | T/U PEN EB  |
| 68 | AMH40AP016B | STEEL WHEEL 16 x 6.5  | JANTES EN ACIER - 16" x 6.5 |
| 69 | AMH40AP016BP | STEEL WHEEL 16 x 6.5  | JANTES EN ACIER - 16" x 6.5 |
| 70 | AMH40AP017B | STEEL WHEEL 17 x 7  | JANTES EN ACIER - 17" x 7 |
| 71 | AMH40AP017BP | STEEL WHEEL 17 x 7  | JANTES EN ACIER - 17" x 7 |

**Decision / rule needed:** Standardize on ingest (trim, collapse spaces, replace NBSP; decide on case, dashes and quotes for the target system). Keep the raw value.


## C. Trims

### C1. Same trim written different ways

Abbreviations and package spellings vary, so matching to the catalogue will miss them.

**How many:** 5 variant groups

| variant group | trim | models | rows | example xl_row |
|---|---|---|---|---|
| EX Prem / EX Premium | EX Prem | K4, K4 Hatchback | 84 | 2268 |
| EX Prem / EX Premium | EX Premium | Forte PE, Niro HEV, Niro PHEV, Rio/Rio5, Seltos, Soul, Sportage, Sp... | 492 | 1326 |
| LX Prem / LX Premium | LX Prem | Sorento | 1 | 102 |
| LX Prem / LX Premium | LX Premium | Rio/Rio5, Sorento | 131 | 76 |
| GTL / GT-Line | GTL | K4 Hatchback | 34 | 2268 |
| GTL / GT-Line | GT-Line | EV6, Forte PE, K5 | 138 | 2 |
| Pkg / Pack | Land AWD GT-Line Pkg | EV6 PE | 37 | 2095 |
| Pkg / Pack | Land AWD GT-Line Pack | EV9 | 75 | 2144 |
| Pkg / Pack | Land AWD Premium Pkg | EV6 PE | 49 | 2095 |
| Pkg / Pack | Land AWD Premium Pack | EV9 | 75 | 2144 |
| Pkg. 1 / Pkg.2 / Pkg 1 | GT-Line Pkg. 1 | EV6 | 16 | 1969 |
| Pkg. 1 / Pkg.2 / Pkg 1 | GT-Line Pkg.2 | EV6 | 1 | 2021 |
| Pkg. 1 / Pkg.2 / Pkg 1 | Land AWD GT-Line Pkg 1 | EV6 | 61 | 2024 |

**Decision / rule needed:** Build a trim alias table per model (e.g. `EX Prem` → `EX Premium`, `GTL` → `GT-Line`, `Pack`/`Package` → `Pkg`).


### C2. Trims used only once for a model

A trim that appears once for a model is often a typo or a variant of a common one.

**How many:** 2 model/trim pairs

| xl_row | part | model | trim |
|---|---|---|---|
| 102 | 9999786MQ4 | Sorento | LX Prem |
| 2021 | 000AM29171 | EV6 | GT-Line Pkg.2 |

**Decision / rule needed:** Flag trims used 2 times or fewer per model for review, and check them against the catalogue's trims.


### C3. Packages in the trim columns

Some trim values are packages on top of a trim, not trims.

**How many:** 10 model/package pairs

| model | trim | rows | example_xl_row |
|---|---|---|---|
| EV6 | GT-Line Pkg. 1 | 16 | 1969 |
| EV6 | GT-Line Pkg.2 | 1 | 2021 |
| EV6 | Land AWD GT-Line Pkg 1 | 61 | 2024 |
| EV6 | Land AWD GT-Line Pkg 2 | 61 | 2024 |
| EV6 PE | Land AWD GT-Line Limited Pkg | 37 | 2095 |
| EV6 PE | Land AWD GT-Line Pkg | 37 | 2095 |
| EV6 PE | Land AWD Premium Pkg | 49 | 2095 |
| EV9 | Land AWD GT-Line Pack | 75 | 2144 |
| EV9 | Land AWD Premium Pack | 75 | 2144 |
| EV9 | Land Plus Package | 73 | 2144 |

**Decision / rule needed:** Is a package a separate fitment target? If yes, map it to the catalogue's package; if no, map it to its base trim.


### C4. `+` trims are real trims (not an issue)

`LX+`, `EX+`, `SX+`, `Premium +`, `Wind +` are Kia trim names. The notebook's *possible multiple trims in one cell* check flags them: 3,435 false alarms after expanding by year and trim.

**How many:** 1204 trim cells

| trim | rows |
|---|---|
| EX+ | 505 |
| LX+ | 302 |
| LX+ IVT | 43 |
| LX+ MT | 42 |
| Premium + | 73 |
| SX+ | 165 |
| Wind + | 74 |

**Decision / rule needed:** Remove `+` from the multi-trim pattern. Spacing still varies (`Premium +` vs `LX+`), so normalize it.


## D. Rules hidden in comments

### D1. Fitment rules written in the comments

Restrictions and status exist only as free text: `GT ONLY`, `NOT COMPATIBLE WITH GT 2.5T TRIM`, `REQUIRES ...`, `ETA TBD`, `In development`. Checked: none contradict the trim columns today, but no rule would catch it if one did.

**How many:** 59 rows

| xl_row | part | model | from | to | kind | trims | comments_en |
|---|---|---|---|---|---|---|---|
| 2342 | 00AM000896 | K4 | 2025 | 2026 | APPLICABLE | LX, EX | Accommodates kayaks up to 36 in/90 cm wide and 75 lbs/35 kg ⏎ Appli... |
| 2277 | 00AM000896 | K4 Hatchback | 2026 | 2026 | APPLICABLE | LX, EX | Accommodates kayaks up to 36 in/90 cm wide and 75 lbs/35 kg ⏎ Appli... |
| 2289 | TBD | K4 Hatchback | 2026 | 2026 | DEVELOPMENT | LX, EX, EX+, EX Prem, GTL, GTL Limited | In development |
| 2274 | TBD | K4 Hatchback | 2026 | 2026 | DEVELOPMENT | LX, EX | In development |
| 2 | L3F03AP000 | K5 | 2021 | 2024 | NOT COMPATIBLE | LX, EX, GT-Line | NOT COMPATIBLE WITH GT 2.5T TRIM |
| 2044 | 85790G5100WK | EV6 | 2024 | 2024 | ONLY | Wind RWD, Land AWD, Land AWD GT-Line Pkg 1, Land AWD GT-Line Pkg 2,... | FLAT SETTING ONLY |
| 1962 | CVH17AP400 | EV6 | 2022 | 2023 | ONLY | GT | GT Only |
| 1384 | AMH03AQ100 | Niro HEV | 2023 | 2026 | REQUIRES | LX, EX, EX Premium, SX | REQUIRES INSTALLATION OF THE THULE VERTEX 2 OR 4 BIKE HITCH MOUNTED... |
| 1459 | AMH03AQ100 | Niro PHEV | 2023 | 2026 | REQUIRES | LX, EX, EX Premium | REQUIRES INSTALLATION OF THE THULE VERTEX 2 OR 4 BIKE HITCH MOUNTED... |
| 782 | R0F17AP110 | Carnival HEV | 2025 | 2026 | TBD | LX+, EX, SX | ETA TBD |

**Decision / rule needed:** Classify comments: *info* (dimensions), *restriction* (only / not compatible), *dependency* (requires), *status* (ETA / in development). Status should become a field.


## E. Flags, pricing and other sheets

### E1. Outgoing parts

`Outgoing Part Flag` = Y. 122 of the 123 are also `Sell Down Flag` = Y.

**How many:** 123 rows

| xl_row | part | model | from | to | desc_en | outgoing_part_flag | sell_down_flag |
|---|---|---|---|---|---|---|---|
| 3 | L3F12AC400 | K5 | 2021 | 2024 | CARGO TRAY | Y | Y |
| 7 | L2131ADX00 | K5 | 2021 | 2024 | ALL WEATHER MATS | Y | Y |
| 12 | L3F24AP001 | K5 | 2021 | 2024 | HOOD PROTECTOR | Y | Y |
| 14 | L3F22AP000 | K5 | 2021 | 2024 | WINDOW VISOR | Y | Y |
| 83 | R5F21AP100 | Sorento | 2021 | 2023 | CROSS BARS - RAISED RAILS/X-LINE | Y | Y |

**Decision / rule needed:** Upload outgoing / sell-down parts or not? Show them differently?


### E2. New parts flag

`New or Updated Part` = NEW.

**How many:** 65 rows

| xl_row | part | model | from | to | desc_en | new_or_updated_part |
|---|---|---|---|---|---|---|
| 2268 | GGF13AU000CA | K4 Hatchback | 2026 | 2026 | ALL WEATHER LINERS - COMPLETE SET | NEW |
| 2269 | GGH13AP000 | K4 Hatchback | 2026 | 2026 | ALL WEATHER RUBBER MATS | NEW |
| 2270 | GGH14AP000 | K4 Hatchback | 2026 | 2026 | COMPLETE ASSY-CARPET MATS | NEW |
| 2271 | GGH17AP000 | K4 Hatchback | 2026 | 2026 | WEATHERTECH LINERS - FRONT | NEW |
| 2272 | GGH17AP100 | K4 Hatchback | 2026 | 2026 | WEATHERTECH LINERS - REAR | NEW |

**Decision / rule needed:** Use it for change tracking between monthly files, and verify it against our own file-to-file comparison.


### E3. Bundles (`PKG Code`)

Parts belong to bundles: Travel Bundle (222), Adventure Bundle (184), Winter Ready Bundle (167), Appearance Protection Bundle (116).

**How many:** 689 rows

| xl_row | part | model | from | to | desc_en | pkg_code |
|---|---|---|---|---|---|---|
| 3 | L3F12AC400 | K5 | 2021 | 2024 | CARGO TRAY | Winter Ready Bundle |
| 4 | L3F05AK000 | K5 | 2021 | 2024 | SPORT PEDALS (A/T) | Appearance Protection Bundle |
| 27 | 66123ADE01 | K5 | 2021 | 2024 | CARGO ORGANIZER | Travel Bundle |
| 34 | 00AM890000 | K5 | 2021 | 2024 | COMPASS 890000 | Adventure Bundle |

**Decision / rule needed:** Are bundles products to upload, or just a grouping?


### E4. Blank written two ways

`Sell Down Flag` uses a space `' '` for *no* on 2,127 rows and a true blank on 63 rows.

**How many:** 2,190 rows

| xl_row | part | model | from | to | sell_down_flag |
|---|---|---|---|---|---|
| 67 | 9999711002 | K5 | 2021 | 2024 | (blank) |
| 99 | R5F40AP000KIT | Sorento | 2021 | 2023 | (blank) |
| 15 | 000AM481001 | K5 | 2021 | 2024 | ' ' |
| 16 | 000AM481010 | K5 | 2021 | 2024 | ' ' |

**Decision / rule needed:** Treat whitespace-only cells as blank on ingest, in every column.


### E5. `#N/A` formula errors

`MOS` and `Rolling 12` (columns AD/AE) contain `#N/A` (failed lookups in the workbook); pandas reads them as blank.

**How many:** 63 rows

| xl_row | part | model | from | to | mos | rolling_12 |
|---|---|---|---|---|---|---|
| 67 | 9999711002 | K5 | 2021 | 2024 |  |  |
| 99 | R5F40AP000KIT | Sorento | 2021 | 2023 |  |  |
| 161 | 9999782768 | Sorento | 2021 | 2023 |  |  |
| 163 | 9999711002 | Sorento | 2021 | 2023 |  |  |
| 189 | R5F40AP000KIT | Sorento PE | 2024 | 2025 |  |  |

**Decision / rule needed:** Out of scope for upload, but every column read from the file must detect Excel errors (#N/A, #REF!, #VALUE!) and flag them.


### E6. Q3 price change list doesn't match the Accy List

18 parts appear in both. The Accy List MSRP equals the Q3 *new* MSRP for 1; for 17 it matches neither the original nor the new price, often far lower (e.g. Rio `H9F57AH000`: Q3 new 897.09, Accy List 73.30).

**How many:** 17 of 18 parts

| Part Number | Model | MSRP - Original | MSRP - New | Accy List MSRP | Accy List MSRP is | DNET - New | Accy List cost | Category |
|---|---|---|---|---|---|---|---|---|
| J2H17AP300 | Soul EV | 148.75 | 104.13 | 104.13 | = New | 85.0 | 85.0 | Overstock |
| M7H17AP101 | Forte / Forte 5 | 155.97 | 109.18 | 96.36 | neither | 89.39 | 81.91 | Overstock |
| PH9H14AC000 | Rio | 110.75 | 77.53 | 13.85 | neither | 62.03 | 11.08 | Overstock |
| H8131ADX00RE | Rio | 90.42 | 64.84 | 28.99 | neither | 44.37 | 19.84 | Overstock |
| H9H17AP000 | Rio | 222.59 | 155.81 | 67.58 | neither | 106.84 | 46.34 | Overstock |
| H9H17AP100 | Rio | 172.04 | 120.42 | 52.24 | neither | 82.57 | 35.82 | Overstock |
| H9H17AP200 | Rio | 203.9 | 142.73 | 61.91 | neither | 116.51 | 50.54 | Overstock |
| H9H17AP300 | Rio | 148.75 | 104.14 | 43.92 | neither | 85.01 | 35.85 | Overstock |

**Decision / rule needed:** **Which sheet is the price source of truth?** Is the Accy List already discounted (overstock / liquidation)? Settle this before automating prices.


### E7. `Notes` sheet is a change log

Kia records changes here (price updates, model year added, description updates).

**How many:** 4 entries

| Date | Vehicle | PN | PN Name | Comment |
|---|---|---|---|---|
| 2026-03-11 | Carnival | R0F21AP000 | CROSS BARS (RAISED RAILS) | MSRP (MAP) updated |
| 2026-03-11 | K4 | GGH21AP000 | CROSSBARS | MSRP (MAP) updated |
| 2026-03-12 | EV6 | BEH40AKA00 | TPMS | Add MY 2026 |
| 2026-03-24 |  | DWH03AP000 | Trailer Hitch | Description update |

**Decision / rule needed:** Use it to verify each new file (e.g. `BEH40AKA00` EV6 "Add MY 2026": EV6 PE 2025 to 2026 is present ✓).


### E8. Excel filter covers only part of the sheet

`Accy List` has an AutoFilter on `A1:AF1115`, but the data runs to row 2463. No rows are hidden today. If someone filters, rows 1116+ aren't filtered the same way, and pandas reads hidden/filtered rows anyway.

**How many:** sheet-level

**Decision / rule needed:** The script reads all rows whatever the filter/hidden state, and logs hidden rows if any appear.


### E9. Other sheets

The workbook has 15 sheets; only `Accy List` is used.

- **Sell Down**: clearance list
- **Liquidation Accessoires**: clearance list (French)
- **To KCA / To KCA (2)**: lists for Kia Canada
- **Liste française**: French price list (title rows; the header isn't on row 1)
- **Template**: price-list layout (title rows)
- **TuxMat Catalog / Remote Starters / Fastco Wheels / Wiper / Wiper Data**: third-party products, **not in the Accy List**

**How many:** 14 sheets

**Decision / rule needed:** Confirm scope: are third-party products (TuxMat, remote starters, Fastco wheels, wipers) uploaded too? Find the sheet by name each month and fail if it's missing.


## F. Vehicle catalogue (matching)

### F1. Catalogue has exact duplicate rows

Each vehicle appears twice.

**How many:** 868 duplicate rows of 1736

| Description | ModelNumber | ModelYear | Style_ID |
|---|---|---|---|
| Niro LX | 0TW5K9A1TEV1DD013 | 2023 | 435402 |
| Niro LX | 0TW5K9A1TEV1DD013 | 2023 | 435402 |
| NIRO LX | 0TW5K9A1TEV1DD210 | 2024 | 445965 |
| NIRO LX | 0TW5K9A1TEV1DD210 | 2024 | 445965 |

**Decision / rule needed:** De-duplicate on load (in the notebook, assign the result of `remove_duplicates`).


### F2. Catalogue: model name only inside Description

Empty columns: `Drivetrain`, `ModelName`, `Package`, `PassDoors`, `TrimName`, `engine_type`. Model, trim and drivetrain are all inside `Description`.

**How many:** 1736 rows

| Description | ModelNumber | ModelYear |
|---|---|---|
| Cadenza Premium Sedan | F6S4J5A1JGG005 | 2019 |
| Cadenza Limited Sedan | F6S4J5A1JGGAJH | 2019 |
| Forte LX Manual | DLS42G617DD075 | 2019 |
| Forte LX IVT | DLS42G61VDD076 | 2019 |

**Decision / rule needed:** Parse Description into model / trim / drivetrain, or get a fuller catalogue (ADS) with ModelName and TrimName filled.


### F3. Catalogue model names: typos, case, spelling

`Sortento` (typo, 12 rows); upper-case `NIRO` / `SELTOS` / `SOUL` / `FORTE4`; `Forte5` / `Forte4` vs accessory `Forte 5 PE` / `Forte PE`; hybrids written `Hybrid` / `Plug-In` vs accessory `HEV` / `PHEV`; `PE` never used.

**How many:** 8 variants shown

| Description | ModelNumber | ModelYear |
|---|---|---|
| Forte5 EX IVT | DJS62G61VMM017 | 2020 |
| Forte4 LX IVT | DLS42G61VDD186 | 2023 |
| FORTE4 LX IVT | DLS42G61VDD208 | 2024 |
| FORTE5 EX IVT | DJS62G61VMM040 | 2024 |
| SOUL LX | SKW52G61VDD314 | 2024 |
| NIRO LX | 0TW5K9A1TEV1DD210 | 2024 |
| SELTOS LX FWD | THW52G61VDD330 | 2024 |
| Sortento HEV LX AWD | HCW7D5G1GEV1SS001 | 2027 |

**Decision / rule needed:** Model alias table: accessory model name → catalogue model name(s), including PE → year range.


### F4. Partial matching assigns wrong vehicles

With partial search, accessory model `Sorento` is found inside `Sorento Hybrid ...` and `Sorento Plug-In ...` descriptions, so a gas-only accessory would be attached to hybrids. 0 of 110 model/year pairs matched exactly.

**How many:** 68 partial matches to review

| Description | ModelYear |
|---|---|
| Sorento Hybrid LX AWD | 2022 |
| Sorento Hybrid EX AWD | 2022 |
| Sorento Plug-In Hybrid EX AWD | 2022 |
| Sorento Plug-In Hybrid EX+ AWD | 2022 |

**Decision / rule needed:** Partial matching is for review only. The output must use the alias table (exact match after mapping).


### F5. Year coverage differs

Catalogue years 2019 to 2027; accessories go back to 2018 (Rio, Stinger). `Style_ID` is blank on 750 of the 1,736 catalogue rows.

**How many:** 7 accessory model/year pairs

| xl_row | part | model | from | to | desc_en |
|---|---|---|---|---|---|
| 2397 | J5H17AP200 | Stinger | 2018 | 2023 | WEATHERTECH FLOOR LINERS - FRONT |
| 2416 | PH9H14AC000 | Rio/Rio5 | 2018 | 2023 | CARPET FLOOR MATS |

**Decision / rule needed:** Model years missing from the catalogue: out of scope, or fetch the older years?

