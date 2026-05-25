# db/queries/manufacturer.py
from sqlalchemy import text

GET_BY_NAME = text("""
    SELECT TOP 10 *
    FROM Manufacturer
    WHERE ManufacturerStatus = 0 
    AND ManufacturerName = :make
""")

GET_ALL = text("""
    SELECT *
    FROM Manufacturer
    WHERE ManufacturerStatus = 0
""")
