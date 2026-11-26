"""Build finding/notes_dump.md: every DQ finding in the Kia workbook, with real example records.
Run from source_code/KIA. Read-only on the data files."""
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
F = "datasets/KIA 202604 Accessories Application Chart.xlsx"
OUT = Path("finding/notes_dump.md")
xls = pd.ExcelFile(F)
raw = pd.read_excel(xls, sheet_name="Accy List", dtype={"Part\nNumber": str})
default_read = pd.read_excel(xls, sheet_name="Accy List")  # default read, to show the number problem

df = raw.copy()
df.columns = (df.columns.str.replace("\n", " ").str.strip().str.lower().str.replace(r"\s+", "_", regex=True)
              .str.replace("_/_", "_").str.replace(r"_+", "_", regex=True))
df = df.rename(columns={"accessory_description_(en)": "desc_en", "accessory_description_(fr)": "desc_fr",
                        "comments/notes_(en)": "comments_en", "suggested_base_retail_price": "msrp",
                        "suggested_labour_hours": "labour", "model_year_from": "from", "model_year_to": "to",
                        "part_number": "part"})
df["part"] = df["part"].astype(str).str.strip()
df.insert(0, "xl_row", df.index + 2)          # row number in Excel (header is row 1)
trims = [c for c in df.columns if c.startswith("trim_")]
df["trims"] = df[trims].apply(lambda r: ", ".join(str(v).strip() for v in r if pd.notna(v)), axis=1)


def cell(v):
    if pd.isna(v):
        return ""
    s = str(v).replace("|", "\\|").replace("\n", " ⏎ ").replace("\xa0", "⍽")
    return s if len(s) <= 70 else s[:67] + "..."


def table(d, cols, n=8):
    d = d[cols].head(n)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(cell(v) for v in r) + " |" for r in d.itertuples(index=False)]
    return "\n".join(out)


BASE = ["xl_row", "part", "model", "from", "to"]
S = []


def sec(title, what, count, d=None, cols=None, n=8, decide=None, note=None):
    S.append((title, what, count, None if d is None else table(d, cols, n), decide, note))


# ---------- A. Record-level DQ issues ----------
m = df["labour"].isna()
sec("A1. Missing labour hours", "`Suggested Labour Hours` is blank.",
    f"{m.sum()} rows, {df.loc[m, 'part'].nunique()} part numbers", df[m], BASE + ["desc_en", "labour"],
    decide="Blank is not 0. Get the hours from Kia, or fill only from the same part **on the same model** (see A2). Tag every fill.")

g = df.dropna(subset=["labour"]).groupby("part")["labour"].nunique()
sec("A2. Same part, different labour hours on different models",
    "The notebook's fill rule assumes one part = one labour value. Not true: hours depend on the vehicle.",
    f"{(g > 1).sum()} part numbers", df[df.part == "000AM481003"].sort_values("labour"), BASE + ["desc_en", "labour"], n=13,
    decide="Labour is per **part + model**, not per part. Fill rule: same part, same model (or model family), else ask Kia.",
    note="Also: wheels `000AK16B253`, `000AK17B244`, `000AK18HY002` are 0.3 h on most models but 0.2 h on K4 / K4 Hatchback / EV4.")

d = df[df.labour >= 2]
sec("A3. Labour hours outlier", "One value far above the rest (median 0; every other value is 1.5 h or less).", f"{len(d)} row",
    d, BASE + ["desc_en", "labour"],
    decide="Confirm with Kia: 4.0 h for a mat set looks like a typo (0.4?). Add a range check (e.g. warn above 2 h).")

m = df[trims].isna().all(axis=1)
sec("A4. Orphaned records (no trim applies)", "All trim columns blank: the accessory is attached to no vehicle.",
    f"{m.sum()} rows, {df.loc[m, 'part'].nunique()} part numbers", df[m], BASE + ["desc_en", "comments_en"],
    decide="Define: does no trim mean *all trims* of the model, *not yet known* (in development), or an error? Same rule for every OEM.")

m = df.part.str.fullmatch(r"TBD", case=False)
sec("A5. Placeholder part number `TBD`",
    "5 different products share the part number `TBD` (K4 Hatchback 2026, \"In development\"). 3 have trims, "
    "so they pass the orphan check and **would be uploaded as part `TBD`**.",
    f"{m.sum()} rows", df[m], BASE + ["trims", "desc_en", "comments_en", "msrp"],
    decide="Placeholder part numbers (TBD, blank, N/A) are never output. Hold them as *in development* until Kia gives a real number.")

pcol = [c for c in default_read.columns if "Part" in c][0]
isnum = default_read[pcol].map(lambda v: isinstance(v, (int, float)) and not pd.isna(v))
d = df[isnum.values].drop_duplicates("part")
sec("A6. Part numbers read as numbers",
    "With a default read, these cells load as integers, mixed with text. Sorting and joins break, and leading zeros would be lost.",
    f"{int(isnum.sum())} rows, {d.part.nunique()} part numbers", d, BASE + ["desc_en"],
    decide="Always read Part Number as text (`dtype=str`).",
    note="They all start `9999` (wheel locks, tents): looks like dealer/aftermarket numbering. Confirm with Kia.")

odd = df[df.part.str.contains("-") | (df.part.str.len() >= 14)].drop_duplicates("part")
lens = df.part.str.len().value_counts().sort_index().to_dict()
sec("A7. Unusual part number formats", f"Part number lengths seen (length: rows): {lens}. Suffixes and kit numbers below.",
    f"{len(odd)} part numbers", odd, BASE + ["desc_en"],
    decide="Agree a valid pattern (letters/digits, 9 to 14 characters, allowed suffixes like `-C`, `KIT`). Anything else is an issue.")

m = df["from"] > df["to"]
sec("A8. Year range reversed", "`Model Year From` is after `Model Year To`.", f"{m.sum()} row", df[m], BASE + ["trims", "desc_en"],
    decide="Approved fix: swap and tag (`fix_swapped_years`). Keep the check so the next one is caught.",
    note="Checked against the same part on other models: the range is 2023 to 2025, so it's a typo.")

d = df[(df.model == "Sorento PE") & (df["from"] < 2024)]
sec("A9. Model / year not plausible",
    "A PE (facelift) model with years before the facelift. Base `Sorento` runs 2021 to 2023 and the other `Sorento PE` rows start 2024, so 2021 looks wrong.",
    f"{len(d)} row", d, BASE + ["desc_en"],
    decide="Check year ranges per model against the vehicle catalogue (PE models included). Confirm with Kia: should it be 2024 to 2025?")

dup_rows = []
for i, r in df.iterrows():
    vals = [str(v).strip().casefold() for v in r[trims] if pd.notna(v)]
    if len(vals) != len(set(vals)):
        dup_rows.append(i)
sec("A10. Same trim listed twice in one record", "A trim appears in two trim columns of the same row.", f"{len(dup_rows)} rows",
    df.loc[dup_rows], BASE + ["trims", "desc_en"],
    decide="Treat as a copy error: keep one (tagged). Ask Kia whether a different trim was meant (e.g. `LX` twice on Rio).")

d = df[df.duplicated(["part", "model", "from", "to"], keep=False) & df.part.ne("TBD")]
sec("A11. Same part, same vehicle, two records", "Two rows give the same part / model / years / trims; only the description differs.",
    f"{len(d)} rows ({d.part.nunique()} part)", d, BASE + ["trims", "desc_en", "msrp", "labour"],
    decide="Keep one record per part + model + year + trim. Which description wins? (`COMPLETE ASSY-` may be the newer name.)",
    note="Checked for any other part + model with overlapping year ranges in different rows (which would also create duplicate "
         "fitments after year expansion): none, apart from the `TBD` rows (A5), which only share the placeholder. Keep the overlap check as a rule.")

# ---------- B. Descriptions & translation ----------
g = df.groupby("part")["desc_en"].nunique()
d = df[df.part.isin(["000AK17B244", "000AM29152", "000AM29165"])].drop_duplicates(["part", "desc_en"])
sec("B1. Same part, different English descriptions",
    "One part number, several descriptions across models (generic vs detailed, or model-specific notes in the name).",
    f"{(g > 1).sum()} part numbers", d, ["xl_row", "part", "model", "desc_en"], n=10,
    decide="Is the description per part, or per part + model? If per part, pick a master description (e.g. from Kia's part master).")

g = df.groupby("desc_en")["desc_fr"].nunique()
d = df[df.desc_en.isin(["ACCESSORY HITCH", "ALL WEATHER MATS", "ALL WEATHER LINERS - COMPLETE SET"])].drop_duplicates(["desc_en", "desc_fr"])
sec("B2. Same English description, different French translations",
    "Inconsistent translations, and some are wrong. `ACCESSORY HITCH` → `ACCESSOIRES DE TOIT` means *roof accessories*. "
    "`TOUS LES TAPIS MÉTÉO` is a literal machine translation of \"all weather mats\".",
    f"{(g > 1).sum()} English descriptions", d, ["xl_row", "part", "model", "desc_en", "desc_fr"], n=10,
    decide="French needs a review step; rules can't detect a wrong meaning. Option: an EN→FR glossary for common terms, and flag deviations.")

m = df.desc_en.notna() & df.desc_fr.isna()
sec("B3. French description missing", "English filled, French blank.", f"{m.sum()} row", df[m], BASE + ["desc_en", "desc_fr"],
    decide="Bilingual output needs both: block or flag.")

d = df[df["accessory_group_(en)"].eq("Hitch Accessory")].drop_duplicates(["accessory_group_(en)", "accessory_group_(fr)"])
sec("B4. Category / group translation not one-to-one",
    "`Hitch Accessory` has two French group names; the French group `Attelage de remorque` is used for two English groups.",
    "1 group each way", d, ["xl_row", "part", "model", "accessory_group_(en)", "accessory_group_(fr)"],
    decide="Keep a fixed EN↔FR mapping table for categories and groups; flag anything not in it.")


def count_text(c):
    t = df[c].dropna().astype(str)
    return {"leading/trailing spaces": int((t != t.str.strip()).sum()), "double spaces": int(t.str.contains("  ").sum()),
            "non-breaking spaces": int(t.str.contains("\xa0").sum()), "line breaks": int(t.str.contains("\n").sum())}


stats = {c: count_text(c) for c in ["desc_en", "desc_fr", "comments_en"]}
en, fr = df.desc_en.astype(str), df.desc_fr.astype(str)
d = df[df.desc_en.notna() & (en.str.contains("  ") | (en != en.str.strip()) | fr.str.contains("\xa0"))]
sec("B5. Text formatting",
    "Spaces, non-breaking spaces (shown as ⍽), line breaks (⏎), mixed case (`18 x 7.5` vs `18 X 7.5`), en dashes `–` and curly quotes `’ ”`.\n\n"
    + "\n".join(f"- `{c}`: " + ", ".join(f"{k} {v}" for k, v in s.items()) for c, s in stats.items()),
    "see counts", d, ["xl_row", "part", "desc_en", "desc_fr"],
    decide="Standardize on ingest (trim, collapse spaces, replace NBSP; decide on case, dashes and quotes for the target system). Keep the raw value.")

# ---------- C. Trims ----------
tm = df.melt(id_vars=["xl_row", "part", "model", "from", "to"], value_vars=trims, value_name="trim").dropna()
tm["trim"] = tm.trim.astype(str).str.strip()
variants = {"EX Prem / EX Premium": ["EX Prem", "EX Premium"], "LX Prem / LX Premium": ["LX Prem", "LX Premium"],
            "GTL / GT-Line": ["GTL", "GT-Line"],
            "Pkg / Pack": ["Land AWD GT-Line Pkg", "Land AWD GT-Line Pack", "Land AWD Premium Pkg", "Land AWD Premium Pack"],
            "Pkg. 1 / Pkg.2 / Pkg 1": ["GT-Line Pkg. 1", "GT-Line Pkg.2", "Land AWD GT-Line Pkg 1"]}
rows = []
for label, names in variants.items():
    for nme in names:
        sub = tm[tm.trim == nme]
        if len(sub):
            rows.append({"variant group": label, "trim": nme, "models": ", ".join(sorted(sub.model.unique())),
                         "rows": len(sub), "example xl_row": sub.xl_row.iloc[0]})
sec("C1. Same trim written different ways", "Abbreviations and package spellings vary, so matching to the catalogue will miss them.",
    f"{len(variants)} variant groups", pd.DataFrame(rows), ["variant group", "trim", "models", "rows", "example xl_row"], n=20,
    decide="Build a trim alias table per model (e.g. `EX Prem` → `EX Premium`, `GTL` → `GT-Line`, `Pack`/`Package` → `Pkg`).")

cnt = tm.groupby(["model", "trim"]).size()
rare = cnt[cnt <= 2].reset_index()[["model", "trim"]]
d = tm.merge(rare, on=["model", "trim"])
sec("C2. Trims used only once for a model", "A trim that appears once for a model is often a typo or a variant of a common one.",
    f"{len(rare)} model/trim pairs", d, ["xl_row", "part", "model", "trim"],
    decide="Flag trims used 2 times or fewer per model for review, and check them against the catalogue's trims.")

pk = tm[tm.trim.str.contains(r"pkg|pack|package", case=False)]
summ = pk.groupby(["model", "trim"]).agg(rows=("xl_row", "size"), example_xl_row=("xl_row", "first")).reset_index()
sec("C3. Packages in the trim columns", "Some trim values are packages on top of a trim, not trims.",
    f"{len(summ)} model/package pairs", summ, ["model", "trim", "rows", "example_xl_row"], n=12,
    decide="Is a package a separate fitment target? If yes, map it to the catalogue's package; if no, map it to its base trim.")

plus = tm[tm.trim.str.contains(r"\+")].groupby("trim").size().reset_index(name="rows")
sec("C4. `+` trims are real trims (not an issue)",
    "`LX+`, `EX+`, `SX+`, `Premium +`, `Wind +` are Kia trim names. The notebook's *possible multiple trims in one cell* check flags them: 3,435 false alarms after expanding by year and trim.",
    f"{plus.rows.sum()} trim cells", plus, ["trim", "rows"], n=10,
    decide="Remove `+` from the multi-trim pattern. Spacing still varies (`Premium +` vs `LX+`), so normalize it.")

# ---------- D. Comments carrying rules ----------
c = df.comments_en.astype(str).str.upper()
m = c.str.contains("ONLY|NOT COMPATIBLE|REQUIRE|DEVELOP|TBD|APPLICABLE")
d = df[m].copy()
d["kind"] = c[m].str.extract(r"(NOT COMPATIBLE|APPLICABLE|ONLY|REQUIRE\w*|DEVELOP\w*|TBD)")[0]
d = d.sort_values("kind").groupby("kind").head(2)
sec("D1. Fitment rules written in the comments",
    "Restrictions and status exist only as free text: `GT ONLY`, `NOT COMPATIBLE WITH GT 2.5T TRIM`, `REQUIRES ...`, `ETA TBD`, `In development`. "
    "Checked: none contradict the trim columns today, but no rule would catch it if one did.",
    f"{int(m.sum())} rows", d, BASE + ["kind", "trims", "comments_en"], n=12,
    decide="Classify comments: *info* (dimensions), *restriction* (only / not compatible), *dependency* (requires), *status* (ETA / in development). Status should become a field.")

# ---------- E. Flags, pricing, other sheets ----------
d = df[df.outgoing_part_flag.eq("Y")]
sec("E1. Outgoing parts", "`Outgoing Part Flag` = Y. 122 of the 123 are also `Sell Down Flag` = Y.", f"{len(d)} rows",
    d, BASE + ["desc_en", "outgoing_part_flag", "sell_down_flag"], n=5,
    decide="Upload outgoing / sell-down parts or not? Show them differently?")

d = df[df.new_or_updated_part.eq("NEW")]
sec("E2. New parts flag", "`New or Updated Part` = NEW.", f"{len(d)} rows", d, BASE + ["desc_en", "new_or_updated_part"], n=5,
    decide="Use it for change tracking between monthly files, and verify it against our own file-to-file comparison.")

d = df[df.pkg_code.notna()].drop_duplicates("pkg_code")
sec("E3. Bundles (`PKG Code`)", "Parts belong to bundles: " + ", ".join(f"{k} ({v})" for k, v in df.pkg_code.value_counts().items()) + ".",
    f"{df.pkg_code.notna().sum()} rows", d, BASE + ["desc_en", "pkg_code"], decide="Are bundles products to upload, or just a grouping?")

d = pd.concat([df[df.sell_down_flag.isna()].head(2), df[df.sell_down_flag.eq(" ")].head(2)])
d = d.assign(sell_down_flag=d.sell_down_flag.map(lambda v: "(blank)" if pd.isna(v) else repr(v)))
sec("E4. Blank written two ways", "`Sell Down Flag` uses a space `' '` for *no* on 2,127 rows and a true blank on 63 rows.", "2,190 rows",
    d, BASE + ["sell_down_flag"], n=4, decide="Treat whitespace-only cells as blank on ingest, in every column.")

d = df[df.mos.isna()]
sec("E5. `#N/A` formula errors",
    "`MOS` and `Rolling 12` (columns AD/AE) contain `#N/A` (failed lookups in the workbook); pandas reads them as blank.",
    f"{len(d)} rows", d, BASE + ["mos", "rolling_12"], n=5,
    decide="Out of scope for upload, but every column read from the file must detect Excel errors (#N/A, #REF!, #VALUE!) and flag them.")

q = pd.read_excel(xls, sheet_name="Q3 Price change list", dtype={"Part Number": str})
mq = q.merge(df[["part", "dealer_cost", "msrp"]].drop_duplicates("part"), left_on="Part Number", right_on="part")
mq["Accy List MSRP is"] = ["= New" if abs(a - n) < .01 else ("= Original" if abs(a - o) < .01 else "neither")
                           for a, n, o in zip(mq.msrp, mq["MSRP - New"], mq["MSRP - Original"])]
mq = mq.rename(columns={"msrp": "Accy List MSRP", "dealer_cost": "Accy List cost"})
sec("E6. Q3 price change list doesn't match the Accy List",
    f"{len(mq)} parts appear in both. The Accy List MSRP equals the Q3 *new* MSRP for {int((mq['Accy List MSRP is'] == '= New').sum())}; "
    f"for {int((mq['Accy List MSRP is'] == 'neither').sum())} it matches neither the original nor the new price, often far lower "
    "(e.g. Rio `H9F57AH000`: Q3 new 897.09, Accy List 73.30).",
    f"{int((mq['Accy List MSRP is'] != '= New').sum())} of {len(mq)} parts", mq,
    ["Part Number", "Model", "MSRP - Original", "MSRP - New", "Accy List MSRP", "Accy List MSRP is", "DNET - New", "Accy List cost", "Category"], n=8,
    decide="**Which sheet is the price source of truth?** Is the Accy List already discounted (overstock / liquidation)? Settle this before automating prices.")

notes = pd.read_excel(xls, sheet_name="Notes")
notes["Date"] = pd.to_datetime(notes["Date"]).dt.date
sec("E7. `Notes` sheet is a change log", "Kia records changes here (price updates, model year added, description updates).", f"{len(notes)} entries",
    notes, list(notes.columns),
    decide="Use it to verify each new file (e.g. `BEH40AKA00` EV6 \"Add MY 2026\": EV6 PE 2025 to 2026 is present ✓).")

sec("E8. Excel filter covers only part of the sheet",
    "`Accy List` has an AutoFilter on `A1:AF1115`, but the data runs to row 2463. No rows are hidden today. If someone filters, rows 1116+ "
    "aren't filtered the same way, and pandas reads hidden/filtered rows anyway.",
    "sheet-level", decide="The script reads all rows whatever the filter/hidden state, and logs hidden rows if any appear.")

sheets = {"Sell Down": "clearance list", "Liquidation Accessoires": "clearance list (French)",
          "To KCA / To KCA (2)": "lists for Kia Canada",
          "Liste française": "French price list (title rows; the header isn't on row 1)",
          "Template": "price-list layout (title rows)",
          "TuxMat Catalog / Remote Starters / Fastco Wheels / Wiper / Wiper Data": "third-party products, **not in the Accy List**"}
S.append(("E9. Other sheets", "The workbook has 15 sheets; only `Accy List` is used.\n\n" + "\n".join(f"- **{k}**: {v}" for k, v in sheets.items()),
          "14 sheets", None,
          "Confirm scope: are third-party products (TuxMat, remote starters, Fastco wheels, wipers) uploaded too? Find the sheet by name each month and fail if it's missing.",
          None))

# ---------- F. Vehicle catalogue ----------
cat = pd.read_csv("datasets/kia_models_catalogue.csv", dtype=str)
cat["first"] = cat.Description.str.split().str[0]
d = cat[cat.duplicated(subset=[c for c in cat.columns if c != "first"], keep=False)].sort_values(["ModelNumber", "ModelYear"])
sec("F1. Catalogue has exact duplicate rows", "Each vehicle appears twice.",
    f"{cat.drop(columns='first').duplicated().sum()} duplicate rows of {len(cat)}",
    d, ["Description", "ModelNumber", "ModelYear", "Style_ID"], n=4,
    decide="De-duplicate on load (in the notebook, assign the result of `remove_duplicates`).")

empty = [c for c in cat.columns if cat[c].isna().all()]
sec("F2. Catalogue: model name only inside Description",
    f"Empty columns: {', '.join('`' + c + '`' for c in empty)}. Model, trim and drivetrain are all inside `Description`.",
    f"{len(cat)} rows", cat.drop_duplicates("Description"), ["Description", "ModelNumber", "ModelYear"], n=4,
    decide="Parse Description into model / trim / drivetrain, or get a fuller catalogue (ADS) with ModelName and TrimName filled.")

bad = cat[cat["first"].isin(["Sortento", "NIRO", "SELTOS", "SOUL", "FORTE4", "FORTE5", "Forte5", "Forte4"])].drop_duplicates("first")
sec("F3. Catalogue model names: typos, case, spelling",
    "`Sortento` (typo, 12 rows); upper-case `NIRO` / `SELTOS` / `SOUL` / `FORTE4`; `Forte5` / `Forte4` vs accessory `Forte 5 PE` / `Forte PE`; "
    "hybrids written `Hybrid` / `Plug-In` vs accessory `HEV` / `PHEV`; `PE` never used.",
    f"{len(bad)} variants shown", bad, ["Description", "ModelNumber", "ModelYear"], n=8,
    decide="Model alias table: accessory model name → catalogue model name(s), including PE → year range.")

sor = cat[cat.Description.str.contains(r"^Sorento (Hybrid|Plug)", case=False)].drop_duplicates("Description")
sec("F4. Partial matching assigns wrong vehicles",
    "With partial search, accessory model `Sorento` is found inside `Sorento Hybrid ...` and `Sorento Plug-In ...` descriptions, "
    "so a gas-only accessory would be attached to hybrids. 0 of 110 model/year pairs matched exactly.",
    "68 partial matches to review", sor, ["Description", "ModelYear"], n=4,
    decide="Partial matching is for review only. The output must use the alias table (exact match after mapping).")

sec("F5. Year coverage differs",
    "Catalogue years 2019 to 2027; accessories go back to 2018 (Rio, Stinger). `Style_ID` is blank on 750 of the 1,736 catalogue rows.",
    "7 accessory model/year pairs", df[df["from"] <= 2018].drop_duplicates("model"), BASE + ["desc_en"], n=4,
    decide="Model years missing from the catalogue: out of scope, or fetch the older years?")

# ---------- write ----------
lines = ["# Kia accessories: data quality findings (notes dump)", "",
         f"Source: `datasets/KIA 202604 Accessories Application Chart.xlsx`, sheet `Accy List` ({len(df):,} records), "
         f"and `datasets/kia_models_catalogue.csv` ({len(cat):,} rows).",
         "`xl_row` is the row number in Excel (the header is row 1), so each example can be found in the workbook.", "",
         "Each finding gives what it is, how many, real example records (up to 8–13 shown), and the decision or rule it needs.", "",
         "## Summary", "", "| # | Finding | How many |", "|---|---|---|"]
lines += [f"| {t.split('. ', 1)[0]} | {t.split('. ', 1)[1]} | {c} |" for t, _, c, *_ in S]
groups = {"A": "A. Record-level data quality issues", "B": "B. Descriptions and translation", "C": "C. Trims",
          "D": "D. Rules hidden in comments", "E": "E. Flags, pricing and other sheets", "F": "F. Vehicle catalogue (matching)"}
cur = None
for title, what, count, tbl, decide, note in S:
    if title[0] != cur:
        cur = title[0]
        lines += ["", f"## {groups[cur]}"]
    lines += ["", f"### {title}", "", what, "", f"**How many:** {count}", ""]
    if tbl:
        lines += [tbl, ""]
    if note:
        lines += [f"_Note:_ {note}", ""]
    if decide:
        lines += [f"**Decision / rule needed:** {decide}", ""]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote", OUT, len(lines), "lines,", len(S), "findings")
