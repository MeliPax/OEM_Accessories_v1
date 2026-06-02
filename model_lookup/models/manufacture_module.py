from db_queries.manufacturer import GET_BY_NAME

import pandas as pd
from sqlalchemy import text

"""

    Helpers

"""


import json
from typing import Union, Any


def parse_json_string(json_string: str) -> Union[dict, list]:
    """
    Parse a JSON string into a Python object (dict or list).

    Args:
        json_string (str): A valid JSON string.

    Returns:
        dict or list: Parsed JSON object.

    Raises:
        ValueError: If the input is not valid JSON.
        TypeError: If input is not a string.
    """
    if not isinstance(json_string, str):
        raise TypeError("Input must be a JSON string")

    try:
        return json.loads(json_string)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON string: {exc}") from exc


def get_manufacturer_df(engine, make: str) -> pd.DataFrame:
    query = text("""
        SELECT *
        FROM Manufacturer
        WHERE ManufacturerName = :make
            AND ManufacturerStatus = 0
    """)

    return pd.read_sql(query, engine, params={"make": make})


def get_manufacturer_bulletins_json(engine, make: str) -> pd.DataFrame:

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                    SELECT 
                 top(1)       
                 B.BulletinDetails

                    FROM Bulletin B
                    WHERE B.BulletinManufacturer = (
                        SELECT ManufacturerId
                        FROM Manufacturer
                        WHERE ManufacturerName = :make
                            AND ManufacturerStatus = 0
                    )
                    AND B.BulletinStatus = 1
                    ORDER BY B.BulletinEnd DESC
                """),
            {"make": make},
        )
        return result.mappings().all()


def get_latest_bulletin_by_manufacturer_json(engine, make: str) -> pd.DataFrame:

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                    SELECT 
                        top(1) B.BulletinDetails

                    FROM Bulletin B
                    WHERE B.BulletinManufacturer = (
                        SELECT ManufacturerId
                        FROM Manufacturer
                        WHERE ManufacturerName = :make
                            AND ManufacturerStatus = 0
                    )
                    AND B.BulletinStatus = 1
                    ORDER BY B.BulletinEnd DESC
                """),
            {"make": make},
        )
        return result.mappings().all()


def print_bulletin_details(bull):
    json_ = parse_json_string(bull[0]["BulletinDetails"])

    for idx, values in enumerate(json_):

        ModelYear = json_[idx].get("Year")
        ModelNumber = json_[idx].get("Model")
        Description = json_[idx].get("Description")
        Description2 = json_[idx].get("Description2")
        Package = json_[idx].get("Package")
        Style_ID = json_[idx].get("Style")

        print(
            f"{ModelYear}, {ModelNumber}, { Description}, { Description2}, { Package}, {Style_ID}"
        )


def print_bulletin_details(bull: list[dict[str, Any]]) -> pd.DataFrame:

    json_ = parse_json_string(bull[0]["BulletinDetails"])

    data = pd.DataFrame(
        columns=[
            "ModelYear",
            "ModelNumber",
            "Description",
            "Description2",
            "Package",
            "Style_ID",
        ]
    )

    for idx, values in enumerate(json_):

        ModelYear = json_[idx].get("Year")

        ModelNumber = json_[idx].get("Model")
        Description = json_[idx].get("Description")
        Description2 = json_[idx].get("Description2")
        Package = json_[idx].get("Package")
        Style_ID = json_[idx].get("Style")

        data = data.append(
            {
                "ModelYear": ModelYear,
                "ModelNumber": ModelNumber,
                "Description": Description,
                "Description2": Description2,
                "Package": Package,
                "Style_ID": Style_ID,
            },
            ignore_index=True,
        )

    return data


def get_active_unique_manufacturers(engine) -> pd.DataFrame:
    query = text("""
        SELECT DISTINCT *
        FROM Manufacturer
        WHERE ManufacturerStatus = 0
                 AND ManufacturerName IS NOT NULL
                 AND ManufacturerName not like '%test%'
    """)

    return pd.read_sql(query, engine)
