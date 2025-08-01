import json
import os
import sys
import chardet

"""
clean_json_output.py

This script reads all `.json` and `.txt` files in a given folder that contain *stringified* JSON content
(e.g., JSON strings with escape characters like `\\n`, `\\`, and `\\\"`), and cleans them by:

- Parsing the stringified JSON into proper Python data structures (dicts or lists)
- Writing the cleaned JSON back into the original file in pretty-printed format
  (i.e., properly indented, without escape characters)

Typical use case: cleaning the output of a language model that returns stringified JSON inside a list of strings.

-------------------------------------
USAGE:
    python clean_json_output.py <folder_path>

EXAMPLE:
    python clean_json_output.py ./input_jsons

This will recursively process all `.json` and `.txt` files in `./input_jsons`, clean them, and overwrite them.
"""

def clean_and_overwrite_json_files(folder_path):
    for filename in os.listdir(folder_path):
        if filename.endswith('.json') or filename.endswith('.txt'):
            file_path = os.path.join(folder_path, filename)
            try:
                encoding = ""
                # Detect encoding
                with open(file_path, 'rb') as f:
                    raw_data = f.read(10000)  # read a portion of the file for detection
                    result = chardet.detect(raw_data)
                    encoding = result['encoding']
                    print(f"Detected encoding: {encoding}")
                
                with open(file_path, 'r', encoding=encoding) as file:
                    raw_content = file.read().strip()

                    # Try parsing the outermost JSON layer
                    parsed_outer = json.loads(raw_content)

                    # If it's a list of JSON strings, parse each element
                    if isinstance(parsed_outer, list) and all(isinstance(x, str) for x in parsed_outer):
                        cleaned = [json.loads(x) for x in parsed_outer]
                    # If it's a single JSON string
                    elif isinstance(parsed_outer, str):
                        cleaned = json.loads(parsed_outer)
                    else:
                        cleaned = parsed_outer

                # Overwrite with clean, properly formatted JSON
                with open(file_path, 'w', encoding='utf-8') as file:
                    json.dump(cleaned, file, indent=2)

                print(f"Cleaned and saved: {filename}")
            except json.JSONDecodeError as e:
                print(f"Failed to parse {filename}: {e}")
            except Exception as e:
                print(f"Unexpected error with {filename}: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python stringify_json_object.py <folder_path>")
        sys.exit(1)

    folder_path = sys.argv[1]
    clean_and_overwrite_json_files(folder_path)

if __name__ == "__main__":
    main()