"""
Script to instrument the Honda notebook with logging calls.
This modifies the notebook to add logging at key pipeline steps.
"""

import json
import uuid
import sys
from pathlib import Path

def instrument_notebook(notebook_path: str):
    """Add logging calls to the Honda processor notebook"""

    nb_path = Path(notebook_path)
    print(f"Instrumenting notebook: {nb_path}\n")

    # Load notebook
    with open(nb_path, 'r', encoding='utf-8', errors='ignore') as f:
        nb = json.load(f)

    print(f"Loaded notebook with {len(nb['cells'])} cells\n")

    # Find key cells to instrument
    cells_to_modify = []

    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'code':
            source_str = ''.join(cell.get('source', []))

            # Find run_pipeline definition
            if 'def run_pipeline(' in source_str and 'excel_dict = load_excel_files_to_dict' in source_str:
                print(f"[CELL {i}] Found run_pipeline() - will add logging")
                cells_to_modify.append(('run_pipeline', i, source_str))

            # Find create_ready_to_load_data
            if 'for model_key, result in extracted_results.items():' in source_str and 'model_key, result in extracted_results' in source_str:
                print(f"[CELL {i}] Found create_ready_to_load_data() - will add logging")
                cells_to_modify.append(('create_ready_to_load_data', i, source_str))

            # Find save_dfs_to_excel
            if 'def save_dfs_to_excel(' in source_str:
                print(f"[CELL {i}] Found save_dfs_to_excel() - will add logging")
                cells_to_modify.append(('save_dfs_to_excel', i, source_str))

    print(f"\nFound {len(cells_to_modify)} cells to instrument\n")

    # Instrument cells
    for cell_type, cell_idx, source_str in cells_to_modify:
        print(f"Instrumenting {cell_type} (cell {cell_idx})...")

        if cell_type == 'run_pipeline':
            # Add logging import and calls
            new_source = add_logging_to_run_pipeline(source_str)
            nb['cells'][cell_idx]['source'] = new_source.split('\n')

        elif cell_type == 'create_ready_to_load_data':
            new_source = add_logging_to_create_ready_to_load(source_str)
            nb['cells'][cell_idx]['source'] = new_source.split('\n')

    # Save modified notebook
    with open(nb_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

    print(f"\nNotebook instrumented and saved!")
    print(f"Logging will be written to: honda_logs/<timestamp>/")


def add_logging_to_run_pipeline(source: str) -> str:
    """Add logging calls to run_pipeline function"""

    # Add import at the start
    if 'from honda_logs import' not in source:
        source = 'from honda_logs import log_pipeline_start, log_excel_loading, log_models_database_loading, log_data_extraction_start, log_data_extraction_complete, log_ready_to_load_start, log_ready_to_load_complete, log_pipeline_complete, log_error\n\n' + source

    # Add logging after excel_dict = load_excel_files_to_dict
    source = source.replace(
        'excel_dict = load_excel_files_to_dict(input_dir)',
        '''excel_dict = load_excel_files_to_dict(input_dir)
    log_excel_loading(len(excel_dict), excel_dict)'''
    )

    # Add logging after honda_models loading
    source = source.replace(
        'honda_models_valid = honda_models_df[honda_models_df["ModelName"].notna()].copy()',
        '''honda_models_valid = honda_models_df[honda_models_df["ModelName"].notna()].copy()
    log_models_database_loading(honda_models_df)'''
    )

    # Add logging before extraction
    source = source.replace(
        'extracted_results, failures = data_extract_orchestrator(',
        '''log_data_extraction_start()
    extracted_results, failures = data_extract_orchestrator('''
    )

    # Add logging after extraction
    source = source.replace(
        'log_data_extraction_start()\n    extracted_results, failures = data_extract_orchestrator(',
        '''log_data_extraction_start()
    extracted_results, failures = data_extract_orchestrator('''
    )

    # Find and add logging after extraction completes
    if 'if not extracted_results:' in source:
        source = source.replace(
            'if not extracted_results:',
            '''log_data_extraction_complete(extracted_results, failures)
    if not extracted_results:'''
        )

    # Add logging before create_ready_to_load_data
    source = source.replace(
        'create_ready_to_load_data(',
        '''log_ready_to_load_start(len(extracted_results))
    create_ready_to_load_data('''
    )

    # Add logging at end
    if 'print("\\n✅ Pipeline completed successfully")' in source:
        source = source.replace(
            'print("\\n✅ Pipeline completed successfully")',
            '''log_pipeline_complete()
    print("\\n✅ Pipeline completed successfully")'''
        )

    return source


def add_logging_to_create_ready_to_load(source: str) -> str:
    """Add logging calls to create_ready_to_load_data function"""

    # Add logging when model attachment completes
    if 'df_trim = attach_model_number_with_matcher(df_trim, honda_models_db)' in source:
        source = source.replace(
            'df_trim = attach_model_number_with_matcher(df_trim, honda_models_db)',
            '''df_trim_before = df_trim.copy()
            df_trim = attach_model_number_with_matcher(df_trim, honda_models_db)
            log_model_attachment_complete(model_key, df_trim_before, df_trim)'''
        )

    return source


if __name__ == '__main__':
    notebook_path = Path(__file__).parent.parent / "scripts" / "honda_processor.ipynb"

    if not notebook_path.exists():
        print(f"ERROR: Notebook not found: {notebook_path}")
        sys.exit(1)

    instrument_notebook(str(notebook_path))
