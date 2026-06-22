import pandas as pd

file = r'c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\accy_v2\output\ready_to_upload\mitsubishi\mitsubishi_7f1606c4_20260622_220308.xlsx'

excel = pd.ExcelFile(file)
for sheet in sorted(excel.sheet_names):
    if '2026' in sheet:
        df = pd.read_excel(file, sheet_name=sheet)
        if len(df) > 0:
            print(f'{sheet}: {len(df)} rows WITH DATA!')
            if 'model_number' in df.columns:
                examples = df['model_number'].head(3).tolist()
                print(f'  model_number examples: {examples}')
        else:
            print(f'{sheet}: EMPTY')
