# Volkswagen Vehicle Keyword Taxonomy & Normalization Guide

**Purpose:**This document provides a standardized taxonomy for Volkswagen vehicle naming conventions, trims, powertrains, editions, and inventory metadata. It is intended for:

- Vehicle title parsing
- Inventory normalization
- Product analytics
- VIN-decoding enrichment
- Vehicle deduplication
- Reporting and dashboarding
- Data engineering pipelines

---

# Recommended Taxonomy

```text
Vehicle
├── Model
├── Model Variant
├── Trim Level
├── Special Edition
├── Appearance Package
├── Technology Package
├── Engine / Powertrain
├── Transmission
├── Drivetrain
├── Body Style
├── EV Battery Supplier
└── Inventory Metadata
```

---

# 1. Trim Levels

Core trim hierarchy used by Volkswagen Canada and North America.

| Keyword     | Normalized Value | Description                                                       |
| ----------- | ---------------- | ----------------------------------------------------------------- |
| Trendline   | Trendline        | Entry-level trim                                                  |
| Comfortline | Comfortline      | Mid-level trim with additional comfort and convenience features   |
| Highline    | Highline         | Premium trim level                                                |
| Execline    | Execline         | Highest mainstream trim on many VW SUVs                           |
| Autobahn    | Autobahn         | Premium sport-oriented trim used primarily on GTI and Golf models |
| S           | S                | Entry trim level on several VW models including ID.4              |
| PRO         | Pro              | EV trim designation for ID.4 lineup                               |

### Examples

```text
Atlas Trendline 3.6 FSI 4MOTION
Atlas Comfortline 2.0 TSI 4MOTION
Atlas Highline 3.6 FSI 4MOTION
Atlas Execline 3.6 FSI 4MOTION

ID.4 S
ID.4 PRO S AWD
```

---

# 2. Special Editions

Limited-production, commemorative, or launch-edition vehicles.

| Keyword     | Normalized Value    | Description                                         |
| ----------- | ------------------- | --------------------------------------------------- |
| Edition     | Edition             | Generic special-edition designation                 |
| Wolfsburg   | Wolfsburg Edition   | Special factory edition named after VW headquarters |
| Rabbit      | Rabbit Edition      | GTI Rabbit special edition                          |
| Peak        | Peak Edition        | Atlas Peak Edition                                  |
| United      | United Edition      | Market-specific special edition                     |
| 1st         | 1st Edition         | Launch-year special edition                         |
| Anniversary | Anniversary Edition | Commemorative edition indicator                     |
| 20th        | 20th Anniversary    | GTI 20th Anniversary Edition                        |
| 35th        | 35th Edition        | Anniversary model designation                       |
| 40th        | 40th Anniversary    | Anniversary model designation                       |

### Examples

```text
GTI 20th Anniversary
GTI 40th Anniversary
Atlas Peak Edition
Golf Rabbit Edition
```

---

# 3. Appearance & Sport Packages

Styling-focused packages rather than true trim levels.

| Keyword | Normalized Value | Description                       |
| ------- | ---------------- | --------------------------------- |
| R-Line  | R-Line           | Sport appearance package          |
| Black   | Black Edition    | Black exterior and trim treatment |

### Examples

```text
Tiguan Highline R-Line
Taos Black Edition
```

---

# 4. Drivetrain

Specifies how power is delivered to the wheels.

| Keyword | Normalized Value | Description                       |
| ------- | ---------------- | --------------------------------- |
| 4MOTION | AWD              | Volkswagen all-wheel-drive system |
| AWD     | AWD              | All-wheel drive                   |
| FWD     | FWD              | Front-wheel drive                 |
| RWD     | RWD              | Rear-wheel drive                  |

### Examples

```text
Atlas Execline 4MOTION
ID.4 Pro AWD
ID.4 Pro RWD
```

---

# 5. Engine & Powertrain

Engine displacements, fuel systems, forced induction technologies, and EV indicators.

| Keyword | Normalized Value | Description                                 |
| ------- | ---------------- | ------------------------------------------- |
| 2.0     | 2.0L Engine      | Typically a turbocharged 2.0L four-cylinder |
| 3.6     | 3.6L VR6         | VR6 gasoline engine                         |
| TSI     | TSI              | Turbocharged Stratified Injection           |
| FSI     | FSI              | Fuel Stratified Injection                   |
| Turbo   | Turbocharged     | Forced induction engine                     |
| Battery | Battery          | Electric vehicle battery designation        |

### Examples

```text
Atlas Comfortline 2.0 TSI
Atlas Execline 3.6 FSI

Taos Trendline Turbo
```

---

# 6. Transmission

Transmission configuration.

| Keyword | Normalized Value | Description                                  |
| ------- | ---------------- | -------------------------------------------- |
| Auto    | Automatic        | Automatic transmission                       |
| Manual  | Manual           | Manual transmission                          |
| DSG     | DSG              | Direct Shift Gearbox (dual-clutch automatic) |

### Examples

```text
Golf GTI DSG
Golf GTI Manual
```

---

# 7. Body Style

Vehicle body configuration.

| Keyword    | Normalized Value | Description                  |
| ---------- | ---------------- | ---------------------------- |
| 5-door     | 5-Door           | Five-door hatchback or wagon |
| 5dr        | 5-Door           | Abbreviated form of 5-door   |
| HB         | Hatchback        | Hatchback body style         |
| SportWagen | SportWagen       | Volkswagen wagon variant     |

### Examples

```text
Golf 5dr HB
Golf SportWagen Comfortline
```

---

# 8. Models & Model Variants

Nameplate-specific identifiers.

| Keyword  | Normalized Value | Description                        |
| -------- | ---------------- | ---------------------------------- |
| Golf     | Golf             | Volkswagen Golf                    |
| Alltrack | Golf Alltrack    | Raised AWD wagon variant           |
| Cross    | Cross Sport      | Atlas Cross Sport naming component |

### Examples

```text
Golf Alltrack
Atlas Cross Sport
```

---

# 9. Technology Packages

Volkswagen driver-assistance and safety branding.

| Keyword | Normalized Value | Description               |
| ------- | ---------------- | ------------------------- |
| IQ      | IQ.DRIVE         | Driver assistance package |
| Drive   | IQ.DRIVE         | Driver assistance package |

### Important Transformation

Raw Tokens:

```text
IQ
Drive
```

Normalized:

```text
IQ.DRIVE
```

### Example

Input:

```text
Taos Highline IQ Drive
```

Output:

```text
Taos Highline IQ.DRIVE
```

---

# 10. EV Battery Supplier Identifiers

Used primarily within ID.4 inventory descriptions.

| Keyword | Normalized Value   | Description                                |
| ------- | ------------------ | ------------------------------------------ |
| w/LG    | LG Energy Solution | LG-supplied battery                        |
| w/SK    | SK On              | SK On battery supplier                     |
| On      | SK On Component    | Component of supplier name, not standalone |

### Examples

```text
ID.4 Pro RWD w/LG Battery
ID.4 Pro AWD w/SK On Battery
```

---

# 11. Inventory & Catalog Metadata

These are inventory-management indicators and should NOT be treated as vehicle features.

| Keyword | Normalized Value     | Description                |
| ------- | -------------------- | -------------------------- |
| Avail   | Available            | Product availability flag  |
| Ltd     | Limited Availability | Inventory/catalog metadata |

### Example

Input:

```text
Atlas Comfortline 2.0 TSI 4MOTION Ltd Avail
```

Meaning:

```text
Vehicle:
Atlas Comfortline 2.0 TSI 4MOTION

Inventory Status:
Limited Availability
```

Not:

```text
Atlas Comfortline Limited Edition
```

---

# Data Transformation Rules

The following transformations should be applied before classification to recover context lost by tokenization.

---

## Rule 1: IQ.DRIVE Reconstruction

### Input

```text
IQ + Drive
```

### Output

```text
IQ.DRIVE
```

### Reason

Volkswagen markets this technology suite as a single branded product.

---

## Rule 2: SK On Battery Reconstruction

### Input

```text
w/SK + On + Battery
```

### Output

```text
Battery Supplier = SK On
```

### Example

Input:

```text
ID.4 Pro AWD w/SK On Battery
```

Output:

```text
Battery Supplier: SK On
```

---

## Rule 3: LG Battery Reconstruction

### Input

```text
w/LG + Battery
```

### Output

```text
Battery Supplier = LG Energy Solution
```

### Example

Input:

```text
ID.4 Pro RWD w/LG Battery
```

Output:

```text
Battery Supplier: LG Energy Solution
```

---

## Rule 4: Limited Availability Reconstruction

### Input

```text
Ltd + Avail
```

### Output

```text
Limited Availability
```

or

```text
Inventory Status = Limited Availability
```

### Reason

This is inventory metadata and not a trim, edition, or package.

---

## Rule 5: Anniversary Edition Reconstruction

### Input

```text
20th + Anniversary
```

### Output

```text
20th Anniversary
```

---

### Input

```text
40th + Anniversary
```

### Output

```text
40th Anniversary
```

---

## Rule 6: First Edition Reconstruction

### Input

```text
1st + Edition
```

### Output

```text
1st Edition
```

---

# Classification Mapping

| Category            | Keywords                                                                     |
| ------------------- | ---------------------------------------------------------------------------- |
| Trim Level          | Trendline, Comfortline, Highline, Execline, Autobahn, S, PRO                 |
| Special Edition     | Edition, Wolfsburg, Rabbit, Peak, United, 1st, 20th, 35th, 40th, Anniversary |
| Appearance Package  | R-Line, Black                                                                |
| Drivetrain          | 4MOTION, AWD, FWD, RWD                                                       |
| Engine / Powertrain | 2.0, 3.6, TSI, FSI, Turbo, Battery                                           |
| Transmission        | Auto, Manual, DSG                                                            |
| Body Style          | 5-door, 5dr, HB, SportWagen                                                  |
| Model Variant       | Golf, Alltrack, Cross                                                        |
| Technology Package  | IQ.DRIVE                                                                     |
| EV Battery Supplier | LG Energy Solution, SK On                                                    |
| Inventory Metadata  | Ltd Avail                                                                    |

---

# Recommended Analytics Output Schema

```json
{
  "model": "",
  "model_variant": "",
  "trim_level": "",
  "special_edition": "",
  "appearance_package": "",
  "technology_package": "",
  "engine": "",
  "transmission": "",
  "drivetrain": "",
  "body_style": "",
  "battery_supplier": "",
  "inventory_status": ""
}
```

### Example

Input:

```text
ID.4 Pro AWD w/SK On Battery
```

Output:

```json
{
  "model": "ID.4",
  "trim_level": "Pro",
  "drivetrain": "AWD",
  "battery_supplier": "SK On"
}
```

### Example

Input:

```text
Atlas Execline 3.6 FSI 4MOTION Ltd Avail
```

Output:

```json
{
  "model": "Atlas",
  "trim_level": "Execline",
  "engine": "3.6L VR6",
  "fuel_system": "FSI",
  "drivetrain": "AWD",
  "inventory_status": "Limited Availability"
}
```
