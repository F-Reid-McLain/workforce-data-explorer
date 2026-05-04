#!/usr/bin/env python3
"""
Data Processing Script for Data Visualization Generator
Converts Excel files to CSV format by removing header rows.
Run quarterly when data is updated.

Usage: python3 process_data.py
"""

import openpyxl
import csv
import os
from pathlib import Path

# Configuration
DATA_DIR = Path(__file__).parent / "Data"
PROCESSED_DIR = DATA_DIR / "processed"

# Files to process: {excel_filename: rows_to_skip}
FILES_TO_PROCESS = {
    "Industry Snapshot.xlsx": 2,
    "Occupation Snapshot.xlsx": 2,
    "Occupation Wages.xlsx": 2,
    # "Real-Time Intelligence.xlsx": 1,  # Skip for now
}

def ensure_processed_dir():
    """Create processed directory if it doesn't exist."""
    PROCESSED_DIR.mkdir(exist_ok=True)
    print(f"✓ Processed directory ready: {PROCESSED_DIR}")

def convert_excel_to_csv(excel_file, skip_rows=2):
    """
    Convert Excel file to CSV, skipping specified number of rows.
    
    Args:
        excel_file: Path to Excel file
        skip_rows: Number of rows to skip from the beginning
    """
    try:
        # Load workbook
        wb = openpyxl.load_workbook(excel_file)
        ws = wb.active
        
        # Extract data starting from skip_rows + 1
        csv_filename = PROCESSED_DIR / (excel_file.stem.replace(" ", "_") + ".csv")
        
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write rows, skipping the first 'skip_rows' rows
            for row_idx, row in enumerate(ws.iter_rows(min_row=skip_rows + 1, values_only=True)):
                # Stop if we hit an empty row (end of data)
                if all(cell is None for cell in row):
                    break
                writer.writerow(row)
        
        print(f"✓ Converted: {excel_file.name} → {csv_filename.name}")
        return csv_filename
        
    except Exception as e:
        print(f"✗ Error processing {excel_file.name}: {e}")
        return None

def main():
    """Main processing function."""
    print("=" * 60)
    print("Data Visualization Generator - Data Processing Script")
    print("=" * 60)
    
    ensure_processed_dir()
    print()
    
    processed_files = []
    for filename, skip_rows in FILES_TO_PROCESS.items():
        excel_path = DATA_DIR / filename
        
        if excel_path.exists():
            csv_file = convert_excel_to_csv(excel_path, skip_rows)
            if csv_file:
                processed_files.append(csv_file)
        else:
            print(f"✗ File not found: {filename}")
    
    print()
    print("=" * 60)
    print(f"Processing complete! {len(processed_files)} file(s) processed.")
    print(f"Output location: {PROCESSED_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
