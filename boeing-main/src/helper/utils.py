import os
import re
import json
import multiprocessing
from functools import partial
import openai
import time
import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from together import Together
from datetime import date, timedelta
from datetime import datetime
import pandas as pd
from helper.stringify_json_object import clean_and_overwrite_json_files
import io
import contextlib
import warnings
from pandas.errors import PerformanceWarning
import difflib
import requests


def split_tabs_preserve_spaces(line):
    return re.split(r'\t+', line.rstrip())


def extract_asterisk_banner_word(line):
    # Strip leading/trailing whitespace
    stripped = line.strip()
    # Split the line into parts based on spaces
    parts = stripped.split()

    # Check if there are at least 7 parts: 3 asterisks at start, 3 at end, and at least one word in between
    if len(parts) >= 7:
        # Check if the first 3 and last 3 items are asterisks
        if parts[0] == '*' and parts[1] == '*' and parts[2] == '*' and \
           parts[-1] == '*' and parts[-2] == '*' and parts[-3] == '*':
            # Extract and return the middle part(s)
            return True, ' '.join(parts[3:-3])
    
    return False, None

def flatten_single_item_lists(obj):
    if isinstance(obj, dict):
        return {k: flatten_single_item_lists(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        # Recurse into each item first
        processed = [flatten_single_item_lists(i) for i in obj]
        if len(processed) == 1:
            return processed[0]  # Flatten single-item list
        else:
            return processed
    else:
        return obj

def flatten_single_item_lists_in_string(obj):
    data = json.loads(obj)
    data = flatten_single_item_lists(data)
    data = json.dumps(data)
    return data

'''NORMALIZATION STEPS
When we normalize, there are a few steps
1. Convert all single item lists into just the item
2. Convert the json object into a string with each field on its own line 
3. Sort the string by key so that a line by line diff will reveal the issue 
if the string doesn't match the expected value
4. Make it so that there are no strings of continuous spaces, so that if the 
current output and desired output are the same but for different numbers of 
spaces in the strings of spaces, the test will still pass.

In deployment we only want to perform steps 1 and 2, but in testing we want to 
perform all 4 steps. 

flatten_single_item_lists_in_string or flatten_single_item_lists performs step one,
use flatten_single_item_lists_in_string if your object is already a string,
and instead use flatten_single_item_lists if your object is currently in list or 
json form.


pretty_json_string performs only step 2, at least in theory, we aren't certain that this function works

normalize_json_string_and_sort performs steps 2 and 3

normalize_spaces performs step 4
'''

'''
Performs steps 2 and 3 from NORMALIZATION STEPS
This function converts a json object into a pretty printed string where it field 
and value are on their own line, and it sorts by key name. With the output sorted, 
if it doesn't match the desired output, you can tell what is wrong using a line 
by line diff.
'''
def normalize_json_string_and_sort(input_str, use_tabs=False):
    """
    Converts a printed Python dict (as string) into a consistently pretty-printed JSON string.
    Uses sorted keys and either tabs or spaces for indentation.
    """
    try:
        # Try JSON first
        data = json.loads(input_str)
    except json.JSONDecodeError:
        # Fallback to Python dict syntax
        data = ast.literal_eval(input_str)

    # Pretty-print with sorted keys
    sorted_json = json.dumps(data, sort_keys=True, indent=4)

    output = capture_print_output(sorted_json)
    return output

'''see NORMALIZATION STEPS to see what this does'''
def pretty_json_string(input_str, use_tabs=False):
    """
    Converts a printed Python dict (as string) into a consistently pretty-printed JSON string.
    Uses sorted keys and either tabs or spaces for indentation.
    """
    
    # Try JSON first
    data = json.loads(input_str)


    output = json.dumps(data, sort_keys=False, indent=4)
    output = capture_print_output(output)

    return output

def fill_crossover_dates():
    file_path = "src/2099_cycle_dates.xlsx"
    crossover_strings = pd.read_excel(file_path)
    warnings.simplefilter(action="ignore", category=PerformanceWarning)
    crossover_dates = crossover_strings
    crossover_dates["Effective Date"] = crossover_dates["Effective Date"].dt.date
    crossover_dates["Cycle End date"] = crossover_dates["Cycle End date"].dt.date
    crossover_dates["Cycle start date"] = crossover_dates["Cycle start date"].dt.date

    return crossover_dates

def extract_date_from_filename(filename):
    # Match pattern like 'nfdd-2023-04-28' or 'nfdd-12023-4-7'
    match = re.search(r'nfdd-(\d{4,6})-(\d{1,2})-(\d{1,2})', filename)
    if match:
        year, month, day = map(int, match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            print(f"Invalid date: {year}-{month}-{day}")
    else:
        print("No date found in filename")
    return None

def is_asterisk_line(line):
    targetSeq = "*  *  *  "
    startsWithAsterisks = len(line.strip()) > len(targetSeq) and line.strip()[0:len(targetSeq)] == targetSeq 
    if(not startsWithAsterisks):
        targetSeq = "* * * "
        startsWithAsterisks = len(line.strip()) > len(targetSeq) and line.strip()[0:len(targetSeq)] == targetSeq 
    asteriskCount = line.count("*")
    hasSixAsterisks = asteriskCount == 6
    return (startsWithAsterisks and hasSixAsterisks)

'''see NORMALIZATION STEPS to see what this does'''
def normalize_spaces(text):
    result = []
    prev_was_space = False
    for char in text:
        if char == ' ':
            if not prev_was_space:
                result.append(' ')
            prev_was_space = True
        else:
            result.append(char)
            prev_was_space = False
    return ''.join(result)


def strip_nfdd_date(input_str):
    # Matches "NFDD" followed by a space and a date (e.g., 2024-06-01 or 1-Jan-2024)
    pattern = r'NFDD[\d\s\t\-]*\d{2}[-/]\d{2}[-/]\d{4}'
    cleaned_str = re.sub(pattern, '', input_str)
    return cleaned_str.strip()


def extract_date_from_first_block(block):
    block_str = block
    if(isinstance(block, list)):
        block_str = "\n".join(block)
    # Look for the word "EFFECTIVE" followed by a date in the format DD/MM/YYYY
    match = re.search(r'EFFECTIVE\s+(\d{1,2}/\d{1,2}/\d{4})\s', block_str)
    if match:
        return match.group(1)
    print("block_str:")
    print(block_str)
    return None
def capture_print_output(input):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        print(input)
    value = buffer.getvalue()
    return value




def get_changed_blocks(text1, text2):
    lines1 = text1.splitlines()
    lines2 = text2.splitlines()

    sm = difflib.SequenceMatcher(None, lines1, lines2)
    changes = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in {'replace', 'delete', 'insert'}:
            from_lines = lines1[i1:i2]
            to_lines = lines2[j1:j2]
            changes.append((from_lines, to_lines, (i1 + 1, i2), (j1 + 1, j2)))

    return changes

def find_all_caps_words(text):
    # Regex explanation:
    # \b([A-Z]+)\b  -- match a whole word in all caps (one or more uppercase letters)
    # \s+          -- at least one space
    # -            -- a hyphen
    # \s*          -- zero or more spaces
    pattern = r'\b([A-Z]+)\b\s+-\s*'

    match = re.match(pattern, text)
    if match:
        return match.group(1)  # return the all caps word
    return None

def find_bracketed_alphanum(text):
    # Regex explanation:
    # \(          -- literal opening bracket
    # \s+         -- one or more spaces
    # ([A-Za-z0-9]+) -- capture group for letters and numbers (one or more)
    # \s+         -- one or more spaces
    # \)          -- literal closing bracket
    pattern = r'\(\s+([A-Za-z0-9]+)\s+\)'

    match = re.match(pattern, text)
    if match:
        return match.group(1)  # return the all caps word
    return None

def relocate_rwy_end(obj):
    if isinstance(obj, dict):
        keys_to_process = list(obj.keys())  # Copy keys to avoid modifying the dict while iterating
        for key in keys_to_process:
            value = obj[key]

            if key == "RWY ID":
                # Case: RWY ID is a dictionary
                if isinstance(value, dict):
                    if "RWY END" in value:
                        rwy_end_data = value.pop("RWY END")

                        if "RWY END" in obj:
                            # Merge based on type
                            if isinstance(obj["RWY END"], list):
                                if isinstance(rwy_end_data, list):
                                    obj["RWY END"].extend(rwy_end_data)
                                else:
                                    obj["RWY END"].append(rwy_end_data)
                            else:
                                if isinstance(rwy_end_data, list):
                                    obj["RWY END"] = [obj["RWY END"]] + rwy_end_data
                                else:
                                    obj["RWY END"] = [obj["RWY END"], rwy_end_data]
                        else:
                            obj["RWY END"] = rwy_end_data

                # Case: RWY ID is a list
                elif isinstance(value, list):
                    collected_rwy_end = []

                    for item in value:
                        if isinstance(item, dict) and "RWY END" in item:
                            found = item.pop("RWY END")
                            if isinstance(found, list):
                                collected_rwy_end.extend(found)
                            else:
                                collected_rwy_end.append(found)

                    if collected_rwy_end:
                        if "RWY END" in obj:
                            if isinstance(obj["RWY END"], list):
                                obj["RWY END"].extend(collected_rwy_end)
                            else:
                                obj["RWY END"] = [obj["RWY END"]] + collected_rwy_end
                        else:
                            obj["RWY END"] = collected_rwy_end if len(collected_rwy_end) > 1 else collected_rwy_end[0]

            # Recurse on all values
            relocate_rwy_end(value)

    elif isinstance(obj, list):
        for item in obj:
            relocate_rwy_end(item)

    return obj

def split_and_check_blocks(block1, block2_json_str):
    # Create local copies for safe temporary modification
    block1_clean = block1.replace('"', '')
    block2_json_clean = block2_json_str.replace('\\"', '')

    blocks1 = [line.strip() for line in block1_clean.splitlines()]
    split_blocks1 = [item for line in blocks1 for item in line.split('\t') if item]
    temp_blocks = [item for item in split_blocks1 if not (item.startswith("NFDD") and re.search(r'\d', item))]

    filtered_blocks1 = []
    i = 0
    while i < len(temp_blocks):
        if i < len(temp_blocks) - 1 and temp_blocks[i].strip().lower() == "page" and temp_blocks[i + 1].strip().isdigit():
            i += 2
        else:
            filtered_blocks1.append(temp_blocks[i])
            i += 1

    for block in filtered_blocks1:
        #create a few variants for each block so that special cases can pass the checker
        block_variants = [block]
        #handle LATTITUDE - 
        all_caps_variant = find_all_caps_words(block)
        if(all_caps_variant):
            block_variants.append(all_caps_variant)

        #handle airport_code like ( 4M5 )
        no_bracket_variant = find_bracketed_alphanum(block)
        if(no_bracket_variant):
            block_variants.append(no_bracket_variant)

        #handle three asterisks like ESTABLISHED
        tempFound, no_asterisk_variant = extract_asterisk_banner_word(block.strip())
        if(tempFound):
            block_variants.append(no_asterisk_variant)
        hasFound = False
        for temp_block in block_variants:
            if(temp_block in block2_json_clean):
                hasFound = True

        if (not hasFound):
            return False, block
        
    return True, None


def is_nfdd_line(line):
    pattern = r'^[ \t]*NFDD[ \t]+\d+[ \t]*-[ \t]*\d+[ \t]*$'
    return bool(re.match(pattern, line))

def is_base_line(line):
    isUnindentedText = (line.strip() != "" and not line.startswith((' ', '\t')))
    isNfddLine = is_nfdd_line(line)
    return isUnindentedText or isNfddLine

def is_regular_line(line):
    return line.strip() == "" or line.startswith('\t')

def split_into_blocks(lines):
    blocks = []
    current_block = []

    for i in range(len(lines)):
        current_line = lines[i]
        current_block.append(current_line.rstrip())

        next_line = lines[i + 1] if i + 1 < len(lines) else None
        if is_regular_line(current_line) and next_line and is_base_line(next_line):
            blocks.append(current_block)
            current_block = []

    if current_block:
        blocks.append(current_block)

    return blocks


def is_route_type_line(s):
    # Check if all alphabetic characters are uppercase
    letters_only = ''.join(c for c in s if c.isalpha())
    all_caps = letters_only.isupper()
    
    # Check if "route" is present (case-insensitive)
    contains_route = "route" in s.lower()
    
    return all_caps and contains_route

# Compare output JSON files
def compare_outputs(json_path_1, json_path_2):
    with open(json_path_1, 'r', encoding='utf-8') as f1, open(json_path_2, 'r', encoding='utf-8') as f2:
        data1 = json.load(f1)
        data2 = json.load(f2)

    mismatches = []
    for entry1 in data1:
        match = next((entry2 for entry2 in data2 if entry2['input_block'] == entry1['input_block']), None)
        if not match:
            mismatches.append({"input_block": entry1["input_block"], "error": "Missing in second file"})
        elif entry1["output"] != match["output"]:
            mismatches.append({
                "input_block": entry1["input_block"],
                "output_1": entry1["output"],
                "output_2": match["output"]
            })

    if mismatches:
        print("\n===== OUTPUT MISMATCHES =====")
        for mismatch in mismatches:
            print(json.dumps(mismatch, indent=2, ensure_ascii=False))
        print("=============================\n")
    else:
        print("All outputs match for each input block.")