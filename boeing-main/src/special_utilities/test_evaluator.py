import json
import difflib
import os
from typing import List, Tuple, Dict, Any
import ast
import io
import contextlib

def capture_print_output(input):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        print(input)
    value = buffer.getvalue()
    return value

def normalize_json_string_and_sort(input_str: str, use_tabs: bool = False) -> str:
    """
    Converts a JSON string into a consistently pretty-printed JSON string.
    Uses sorted keys and either tabs or spaces for indentation.
    """
    try:
        # Try JSON first
        data = json.loads(input_str)
    except json.JSONDecodeError:
        # If it's already a dict/list, use it directly
        data = input_str

    # Pretty-print with sorted keys
    sorted_json = json.dumps(data, sort_keys=True, indent=4)
    output = capture_print_output(sorted_json)
    return output

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
    if isinstance(obj, str):
        try:
            data = json.loads(obj)
        except json.JSONDecodeError:
            data = ast.literal_eval(obj)
    else:
        data = obj
    data = flatten_single_item_lists(data)
    return json.dumps(data)

def normalize_spaces(text: str) -> str:
    """
    Normalize spaces in text, removing multiple spaces and normalizing line endings.
    """
    # Replace multiple spaces with a single space
    text = ' '.join(text.split())
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return text

def get_changed_blocks(text1: str, text2: str) -> List[Tuple[List[str], List[str], Tuple[int, int], Tuple[int, int]]]:
    """
    Get the differences between two texts, returning blocks of changed lines.
    """
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

def load_golden_data(test_type: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load golden data for a specific test type from the test_set directory.
    Matches files by their exact names.
    
    Args:
        test_type: The type of test (e.g., 'NAVAIDS', 'PARACHUTE', etc.)
        
    Returns:
        Dictionary mapping filenames to their entries
    """
    golden_dir = os.path.join("test_cases", "")

    if not os.path.exists(golden_dir):
        raise ValueError(f"Golden data directory not found: {golden_dir}")

    golden_data = {}
    for filename in os.listdir(golden_dir):
        if not filename.endswith('.json'):
            continue
            
        file_path = os.path.join(golden_dir, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                golden_data[filename] = data
            elif isinstance(data, dict):
                golden_data[filename] = [data]
    
    return golden_data

def load_parsed_data(test_type: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load parsed data for a specific test type from the parsed_* directory.
    Matches files by their exact names.
    
    Args:
        test_type: The type of test (e.g., 'NAVAIDS', 'PARACHUTE', etc.)
        
    Returns:
        Dictionary mapping filenames to their entries
    """
    parsed_dir = os.path.join(f"parsed_{test_type}_jsons")
    if not os.path.exists(parsed_dir):
        raise ValueError(f"Parsed data directory not found: {parsed_dir}")
    
    parsed_data = {}
    for filename in os.listdir(parsed_dir):
        if not filename.endswith('.json'):
            continue
            
        file_path = os.path.join(parsed_dir, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                parsed_data[filename] = data
            elif isinstance(data, dict):
                parsed_data[filename] = [data]
    
    return parsed_data

def get_entry_key(entry: Dict[str, Any]) -> str:
    """
    Generate a unique key for an entry based on its identifying fields.
    """
    key_parts = []
    for field in ['NFDD', 'name', 'location', 'state']:
        if field in entry and 'value' in entry[field]:
            key_parts.append(str(entry[field]['value']))
    return '|'.join(key_parts)

def evaluate_parsed_against_golden(test_type: str, verbose: bool = True) -> Dict[str, Any]:
    """
    Evaluate parsed data against golden data for a specific test type.
    Uses evaluation logic from llm_pipeline.py but without OpenAI calls.
    Matches files by their exact names between golden and parsed data folders.
    
    Args:
        test_type: The type of test (e.g., 'NAVAIDS', 'PARACHUTE', etc.)
        verbose: Whether to print detailed test results
        
    Returns:
        Dictionary containing test results
    """
    try:
        golden_data = load_golden_data(test_type)
        parsed_data = load_parsed_data(test_type)
        
        if not golden_data:
            raise ValueError(f"No golden data found for {test_type}")
        if not parsed_data:
            raise ValueError(f"No parsed data found for {test_type}")
        
        total_tests = 0
        passed_tests = 0
        failed_cases = []
        
        # Match files by their exact names
        for golden_filename, golden_entries in golden_data.items():
            if golden_filename not in parsed_data:
                if verbose:
                    print(f"\nWarning: No matching parsed file found for {golden_filename}")
                continue
                
            parsed_entries = parsed_data[golden_filename]
            
            # Create a mapping of entry keys to golden entries
            golden_map = {get_entry_key(entry): entry for entry in golden_entries}
            
            # Match parsed entries with golden entries
            for parsed_entry in parsed_entries:
                total_tests += 1
                key = get_entry_key(parsed_entry)
                
                if key not in golden_map:
                    if verbose:
                        print(f"\nWarning: No matching golden entry found for key {key} in {golden_filename}")
                    continue
                
                golden_entry = golden_map[key]
                
                try:
                    # Convert entries to JSON strings for comparison
                    golden_str = json.dumps(golden_entry, sort_keys=True)
                    parsed_str = json.dumps(parsed_entry, sort_keys=True)
                    
                    # Normalize both outputs for comparison using llm_pipeline logic
                    result = normalize_json_string_and_sort(
                        flatten_single_item_lists_in_string(parsed_str),
                        use_tabs=False
                    )
                    expected = normalize_json_string_and_sort(
                        flatten_single_item_lists_in_string(golden_str),
                        use_tabs=False
                    )
                    
                    # Normalize spaces for comparison
                    result_normed = normalize_spaces(result)
                    expected_normed = normalize_spaces(expected)
                    
                    # Compare results
                    if str(result_normed).strip() == expected_normed.strip():
                        passed_tests += 1
                        if verbose:
                            print(f"Test PASSED: {golden_filename} - Entry {key}")
                    else:
                        failed_case = {
                            "filename": golden_filename,
                            "entry_key": key,
                            "expected": expected,
                            "actual": result,
                            "differences": []
                        }
                        
                        # Get detailed differences using llm_pipeline logic
                        diffs = get_changed_blocks(result_normed, expected_normed)
                        for diff_num, (from_lines, to_lines, from_nums, to_nums) in enumerate(diffs, 1):
                            failed_case["differences"].append({
                                "diff_number": diff_num,
                                "from_lines": from_lines,
                                "to_lines": to_lines,
                                "line_numbers": {
                                    "from": from_nums,
                                    "to": to_nums
                                }
                            })
                        
                        failed_cases.append(failed_case)
                        
                        if verbose:
                            print(f"\nTest FAILED: {golden_filename} - Entry {key}")
                            print("\nExpected Output:")
                            print(expected)
                            print("\nActual Output:")
                            print(result)
                            print("\nDifferences:")
                            for diff in failed_case["differences"]:
                                print(f"\nChange {diff['diff_number']}:")
                                print("  - result:")
                                for line in diff["from_lines"]:
                                    print(f"    {line}")
                                print("  - to expected:")
                                for line in diff["to_lines"]:
                                    print(f"    {line}")
                                print(f"Line numbers: {diff['line_numbers']['from']} -> {diff['line_numbers']['to']}")
                except Exception as e:
                    failed_case = {
                        "filename": golden_filename,
                        "entry_key": key,
                        "error": f"Error processing entry: {str(e)}",
                        "expected": json.dumps(golden_entry, sort_keys=True),
                        "actual": json.dumps(parsed_entry, sort_keys=True)
                    }
                    failed_cases.append(failed_case)
                    if verbose:
                        print(f"\nTest ERROR: {golden_filename} - Entry {key}")
                        print(f"Error: {str(e)}")
                        print("\nExpected Output:")
                        print(json.dumps(golden_entry, indent=2))
                        print("\nActual Output:")
                        print(json.dumps(parsed_entry, indent=2))
        
        if total_tests == 0:
            raise ValueError(f"No matching entries found between golden and parsed data for {test_type}")
        
        # Calculate final statistics
        accuracy = passed_tests / total_tests if total_tests > 0 else 0
        
        if verbose:
            print(f"\nTest Summary for {test_type}:")
            print(f"Total Tests: {total_tests}")
            print(f"Passed Tests: {passed_tests}")
            print(f"Failed Tests: {total_tests - passed_tests}")
            print(f"Accuracy: {accuracy:.2%}")
        
        return {
            "test_type": test_type,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "accuracy": accuracy,
            "failed_cases": failed_cases
        }
        
    except Exception as e:
        return {
            "test_type": test_type,
            "error": str(e),
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "accuracy": 0,
            "failed_cases": []
        }

def evaluate_all_test_types(verbose: bool = True) -> Dict[str, Any]:
    """
    Evaluate all test types against their golden data.
    
    Args:
        verbose: Whether to print detailed test results
        
    Returns:
        Dictionary containing results for all test types
    """
    test_types = [
        "NAVAIDS",
        "PARACHUTE",
        "SPECIAL_ACTIVITY_AIRSPACE",
        "VOR_RECEIVER_CHECKPOINTS"
    ]
    
    all_results = {}
    total_passed = 0
    total_tests = 0
    
    for test_type in test_types:
        print(f"\nEvaluating {test_type}...")
        results = evaluate_parsed_against_golden(test_type, verbose)
        all_results[test_type] = results
        
        if "error" not in results:
            total_passed += results["passed_tests"]
            total_tests += results["total_tests"]
    
    overall_accuracy = total_passed / total_tests if total_tests > 0 else 0
    
    if verbose:
        print("\nOverall Summary:")
        print(f"Total Tests Across All Types: {total_tests}")
        print(f"Total Passed Tests: {total_passed}")
        print(f"Overall Accuracy: {overall_accuracy:.2%}")
    
    all_results["overall"] = {
        "total_tests": total_tests,
        "passed_tests": total_passed,
        "accuracy": overall_accuracy
    }
    
    return all_results

def save_test_results(results: Dict[str, Any], output_file: str) -> None:
    """
    Save test results to a JSON file.
    
    Args:
        results: Dictionary containing test results
        output_file: Path to the output JSON file
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2) 