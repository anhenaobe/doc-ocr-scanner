import pandas as pd
import logging
from .search_utils import final_dict

def save_multiple_to_excel(dataframes_dict, file_name):
    """
    Saves multiple DataFrames to a single Excel file, each in its own sheet.
    dataframes_dict: dict with sheet names as keys and DataFrames or dicts as values.
    """
    with pd.ExcelWriter(file_name, engine='xlsxwriter') as writer:
        for sheet_name, data in dataframes_dict.items():
            if isinstance(data, dict):
                df = pd.DataFrame(list(data.items()), columns=['Key', 'Value'])
            else:
                df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name=sheet_name, index=False)

def save_results_if_any(results, excel_file):
    """add and saves results to an Excel file if there are any matches."""
    summed_values, string_values = final_dict(results)
    if summed_values or string_values:
        save_multiple_to_excel({
            "Results": results,
            "Summed": summed_values,
            "Strings": string_values
        }, f"{excel_file}.xlsx")
        logging.info(f"Results saved to {excel_file}.xlsx")
        return True
    else:
        logging.info("No matches found.")
        return False