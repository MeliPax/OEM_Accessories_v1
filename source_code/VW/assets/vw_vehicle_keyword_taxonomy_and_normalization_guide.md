# Volkswagen Vehicle Catalog Taxonomy & Normalization Framework

## Purpose

This framework is designed for:

- Vehicle catalog management
- Vehicle identification and classification
- Inventory normalization
- Search and filtering
- Dealership inventory analytics
- Data quality and deduplication
- Master Data Management (MDM)

The objective is to separate:

- Vehicle attributes
- Product hierarchy
- Inventory metadata

into a structure that remains scalable as additional Volkswagen Group brands (Audi, Porsche, Bentley, Lamborghini, Skoda, SEAT) and competing OEMs are added.

---

# Recommended Vehicle Hierarchy

```text
Make
├── Model
├── Series (Optional)
├── Submodel
├── Trim
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

# Hierarchy Definitions

| Level    | Purpose                                  |
| -------- | ---------------------------------------- |
| Make     | Manufacturer                             |
| Model    | Primary vehicle nameplate                |
| Series   | Performance or lifestyle family grouping |
| Submodel | Distinct derivative of a model           |
| Trim     | Feature/content level                    |
| Package  | Optional feature package                 |
| Edition  | Limited or commemorative version         |

---

# 1. Make

Examples:

```text
Volkswagen
Audi
Porsche
```

---

# 2. Model

A model represents the primary vehicle nameplate.

## Examples

| Model  |
| ------ |
| Atlas  |
| Golf   |
| Jetta  |
| Passat |
| Taos   |
| Tiguan |
| Arteon |
| Beetle |
| ID.4   |

### Examples

```text
Atlas Comfortline
Golf Highline
ID.4 Pro AWD
```

---

# 3. Series (Optional)

A series groups multiple submodels into a common product family.

Series should only be used when it creates meaningful business value.

## Why Series Exists

Series allows vehicles to be grouped at a level above Submodel.

### Example

Without Series:

```text
Golf
├── GTI
├── R
├── Alltrack
└── Base Golf
```

With Series:

```text
Golf
├── Standard Series
│   └── Golf
│
├── Adventure Series
│   └── Alltrack
│
└── Performance Series
    ├── GTI
    └── R
```

---

## Example: Golf GTI Autobahn DSG

```json
{
  "make": "Volkswagen",
  "model": "Golf",
  "series": "Performance",
  "submodel": "GTI",
  "trim": "Autobahn",
  "transmission": "DSG"
}
```

---

## Example: Golf R

```json
{
  "make": "Volkswagen",
  "model": "Golf",
  "series": "Performance",
  "submodel": "R"
}
```

---

## Example: Golf Alltrack Highline

```json
{
  "make": "Volkswagen",
  "model": "Golf",
  "series": "Adventure",
  "submodel": "Alltrack",
  "trim": "Highline"
}
```

---

## Implementation Recommendation

For Volkswagen:

```text
Series = Nullable
```

Only populate it when it materially improves catalog organization.

---

# 4. Submodel

A Submodel is a distinct vehicle derivative with its own positioning, engineering characteristics, or marketing identity.

Submodels are NOT trims.

## Volkswagen Examples

| Submodel    | Parent Model |
| ----------- | ------------ |
| Alltrack    | Golf         |
| SportWagen  | Golf         |
| GTI         | Golf         |
| R           | Golf         |
| Cross Sport | Atlas        |
| GLI         | Jetta        |

---

## Example

### Input

```text
Golf Alltrack Execline DSG
```

### Output

```json
{
  "model": "Golf",
  "submodel": "Alltrack",
  "trim": "Execline",
  "transmission": "DSG"
}
```

---

## Example

### Input

```text
Atlas Cross Sport Highline
```

### Output

```json
{
  "model": "Atlas",
  "submodel": "Cross Sport",
  "trim": "Highline"
}
```

---

# 5. Trim

Trims represent equipment and feature hierarchy.

## Keywords

| Keyword     |
| ----------- |
| Trendline   |
| Comfortline |
| Highline    |
| Execline    |
| Autobahn    |
| S           |
| PRO         |

---

## Examples

```text
Atlas Trendline
Atlas Comfortline
Atlas Execline

ID.4 PRO
ID.4 S
```

---

# 6. Special Editions

Limited-production or commemorative vehicles.

## Keywords

| Keyword     | Normalized Value    |
| ----------- | ------------------- |
| Edition     | Edition             |
| Wolfsburg   | Wolfsburg Edition   |
| Rabbit      | Rabbit Edition      |
| Peak        | Peak Edition        |
| United      | United Edition      |
| Anniversary | Anniversary Edition |
| 1st         | 1st Edition         |
| 20th        | 20th Anniversary    |
| 35th        | 35th Anniversary    |
| 40th        | 40th Anniversary    |

---

## Examples

```text
GTI 40th Anniversary
GTI Rabbit Edition
Atlas Peak Edition
```

---

# 7. Appearance Packages

Visual styling packages.

## Keywords

| Keyword |
| ------- |
| R-Line  |
| Black   |

---

## Examples

```text
Tiguan Highline R-Line
Taos Black Edition
```

---

# 8. Technology Packages

Technology branding and driver assistance systems.

## Keywords

| Raw Token |
| --------- |
| IQ        |
| Drive     |

---

## Normalization

### Input

```text
IQ + Drive
```

### Output

```text
IQ.DRIVE
```

---

## Example

### Input

```text
Taos Highline IQ Drive
```

### Output

```json
{
  "technology_package": "IQ.DRIVE"
}
```

---

# 9. Engine & Powertrain

Engine displacement and propulsion.

## Keywords

| Keyword | Meaning                           |
| ------- | --------------------------------- |
| 2.0     | 2.0L Engine                       |
| 3.6     | 3.6L VR6                          |
| TSI     | Turbocharged Stratified Injection |
| FSI     | Fuel Stratified Injection         |
| Turbo   | Turbocharged                      |
| Battery | Electric Vehicle Battery          |

---

## Examples

```text
Atlas Comfortline 2.0 TSI

Atlas Execline 3.6 FSI
```

---

# 10. Drivetrain

Wheel-drive configuration.

## Keywords

| Keyword | Normalized |
| ------- | ---------- |
| 4MOTION | AWD        |
| AWD     | AWD        |
| FWD     | FWD        |
| RWD     | RWD        |

---

## Examples

```text
Atlas Execline 4MOTION

ID.4 Pro AWD

ID.4 Pro RWD
```

---

# 11. Transmission

Vehicle transmission type.

## Keywords

| Keyword | Normalized      |
| ------- | --------------- |
| Auto    | Automatic       |
| Manual  | Manual          |
| DSG     | DSG Dual-Clutch |

---

## Examples

```text
Golf GTI DSG

Golf GTI Manual
```

---

# 12. Body Style

Physical vehicle configuration.

## Keywords

| Keyword | Normalized |
| ------- | ---------- |
| 5-door  | 5-Door     |
| 5dr     | 5-Door     |
| HB      | Hatchback  |

---

## Important Rule

```text
SportWagen
```

should NOT be treated as a body style.

Instead:

```text
Submodel = SportWagen
```

because Volkswagen marketed it as a distinct product line.

---

# 13. EV Battery Supplier

Applicable primarily to ID.4 inventory.

## Keywords

| Token | Supplier           |
| ----- | ------------------ |
| w/LG  | LG Energy Solution |
| w/SK  | SK On              |
| On    | Component of SK On |

---

## Transformation

### Input

```text
w/SK + On + Battery
```

### Output

```json
{
  "battery_supplier": "SK On"
}
```

---

### Input

```text
w/LG + Battery
```

### Output

```json
{
  "battery_supplier": "LG Energy Solution"
}
```

---

# 14. Inventory Metadata

These are inventory management attributes.

They are NOT vehicle characteristics.

## Keywords

| Keyword | Meaning              |
| ------- | -------------------- |
| Ltd     | Limited Availability |
| Avail   | Available            |

---

## Transformation

### Input

```text
Ltd + Avail
```

### Output

```text
Limited Availability
```

---

## Important

Inventory Metadata should never be used for:

- Vehicle classification
- Catalog hierarchy
- Trim identification
- VIN decoding
- Vehicle matching

Store separately.

---

# Composite Transformations

## IQ.DRIVE

### Input

```text
IQ + Drive
```

### Output

```text
IQ.DRIVE
```

---

## SK On Battery

### Input

```text
w/SK + On + Battery
```

### Output

```text
Battery Supplier = SK On
```

---

## LG Battery

### Input

```text
w/LG + Battery
```

### Output

```text
Battery Supplier = LG Energy Solution
```

---

## Limited Availability

### Input

```text
Ltd + Avail
```

### Output

```text
Limited Availability
```

---

## Anniversary Editions

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

### Input

```text
1st + Edition
```

### Output

```text
1st Edition
```

---

# Classification Reference

| Category            | Keywords                                                     |
| ------------------- | ------------------------------------------------------------ |
| Trim                | Trendline, Comfortline, Highline, Execline, Autobahn, S, PRO |
| Submodel            | Alltrack, SportWagen, GTI, R, Cross Sport, GLI               |
| Special Edition     | Edition, Wolfsburg, Rabbit, Peak, United, Anniversary        |
| Appearance Package  | R-Line, Black                                                |
| Technology Package  | IQ.DRIVE                                                     |
| Engine / Powertrain | 2.0, 3.6, TSI, FSI, Turbo, Battery                           |
| Transmission        | Auto, Manual, DSG                                            |
| Drivetrain          | 4MOTION, AWD, FWD, RWD                                       |
| Body Style          | 5-door, 5dr, HB                                              |
| EV Battery Supplier | LG Energy Solution, SK On                                    |
| Inventory Metadata  | Ltd Avail                                                    |

---

# Recommended Catalog Schema

```json
{
  "make": "",
  "model": "",
  "series": null,
  "submodel": null,
  "trim": null,
  "special_edition": null,
  "appearance_package": null,
  "technology_package": null,
  "engine": null,
  "transmission": null,
  "drivetrain": null,
  "body_style": null,
  "battery_supplier": null,
  "inventory_status": null
}
```

---

# Example Records

## Golf Alltrack Execline DSG

```json
{
  "make": "Volkswagen",
  "model": "Golf",
  "series": "Adventure",
  "submodel": "Alltrack",
  "trim": "Execline",
  "transmission": "DSG"
}
```

---

## Golf GTI Autobahn DSG

```json
{
  "make": "Volkswagen",
  "model": "Golf",
  "series": "Performance",
  "submodel": "GTI",
  "trim": "Autobahn",
  "transmission": "DSG"
}
```

---

## Atlas Cross Sport Execline 4MOTION

```json
{
  "make": "Volkswagen",
  "model": "Atlas",
  "submodel": "Cross Sport",
  "trim": "Execline",
  "drivetrain": "AWD"
}
```

---

## ID.4 Pro AWD w/SK On Battery

```json
{
  "make": "Volkswagen",
  "model": "ID.4",
  "trim": "Pro",
  "drivetrain": "AWD",
  "battery_supplier": "SK On"
}
```

---

# Core Design Principle

A keyword should be classified at the highest level that remains consistently true across all trims and model years.

✅ Correct

```text
Model = Golf
Submodel = Alltrack
Trim = Highline
Transmission = DSG
```

❌ Incorrect

```text
Model = Golf
Trim = Alltrack
```

This principle prevents GTI, R, Alltrack, SportWagen, Cross Sport, GLI, and future performance or lifestyle derivatives from being incorrectly categorized as trims.
