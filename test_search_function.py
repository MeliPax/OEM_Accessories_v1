import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "accy_v2"))

from accy_v2.model_lookup.models.manufacture_module import search_models_by_description

# Test the search function
keywords = ['rvr', 'es']
result = search_models_by_description(
    make='Mitsubishi',
    year=2026,
    keywords=keywords,
    csv_path='accy_v2/model_lookup/db/db_vehicle_models.csv'
)

print(f'Searching for: {keywords}')
print(f'Results: {len(result)} found')
print(result[['ModelNumber', 'Description']])
