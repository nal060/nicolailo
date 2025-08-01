"""
count_files.py

Utility script to analyze the contents of a folder containing NFDD sectioned text files.

This script performs the following:
- Counts the total number of files in a given folder.
- Identifies unique base PDFs and computes how many sections each generated.
- Calculates the average number of sections per PDF.
- Counts how many times each section header appears across all files, normalized
  (e.g., "03_INSTRUMENT_LANDING_SYSTEMS" and "01_INSTRUMENT_LANDING_SYSTEMS" are treated as the same header).

Usage:
    - Modify `folder_path` at the bottom of the script to point to your target folder.
    - Run the script to see an overview of file counts and section distributions.
"""
import os
from collections import defaultdict

def count_files_and_headers(folder_path):
    if not os.path.isdir(folder_path):
        print(f"❌ Path does not exist or is not a directory: {folder_path}")
        return

    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    print(f"📁 Folder: {folder_path}")
    print(f"📄 Total files: {len(files)}")

    # Count how many section files came from each base PDF
    pdf_section_counts = defaultdict(int)
    # Count how many times each header appears
    header_counts = defaultdict(int)

    for file in files:
        if "_SECTION" in file:
            base = file.split("_SECTION_")[0]
            #print(f"Processing file: {file} (base: {base})")
            pdf_section_counts[base] += 1

            # Extract header portion: everything after the second underscore
            parts = file.split("_SECTION_")
            #print(f"Parts: {parts}")
            if len(parts) > 1:
                header_part = parts[1]
                # Remove numeric prefix and file extension
                header_text = "_".join(header_part.split("_")[1:])  # drop section number
                header_text = os.path.splitext(header_text)[0]
                header_counts[header_text] += 1

    print(f"📦 Unique PDFs found: {len(pdf_section_counts)}")
    print(f"📊 Average sections per PDF: {sum(pdf_section_counts.values()) / len(pdf_section_counts):.2f}")

    print("\n🔢 Header counts:")
    for header, count in sorted(header_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{header}: {count}")

if __name__ == "__main__":
    folder_path = "./sectioned_txt_files"  # output from section_splitter.py. Change this to your folder path
    count_files_and_headers(folder_path)
