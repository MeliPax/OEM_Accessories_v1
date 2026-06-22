import pandas as pd

db_path = r'c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\model_lookup\db\db_vehicle_models.csv'
df = pd.read_csv(db_path)

# Check 2026 RVR ES
mits_2026 = df[(df['Manufacturer'] == 'Mitsubishi') & (df['ModelYear'] == 2026)]
rvr_es = mits_2026[mits_2026['Description'].str.contains('RVR.*ES', case=False, na=False, regex=True)]

print('2026 Mitsubishi RVR ES models in database:')
print(rvr_es[['ModelNumber', 'Description']])
