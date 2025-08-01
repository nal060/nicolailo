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
from helper.utils import *
import sys


boeingErrorOutputName = "boeingErrorOutput.txt"

def boeingErrorOut(text):
    if(shouldOutputMissing):
        print(text)
    with open(boeingErrorOutputName, "a") as f:
        f.write(text)
        f.write("\n")

shouldOutputMissing = False
headerType = ""
# Read the API key from a file
api_key = ""
# with open("openai_api_key.txt", "r") as keyfile:
#     api_key = keyfile.readline()

together_key = ""
# with open("TOGETHER_API_KEY.txt", "r") as together_key_file:
#     together_key = together_key_file.readline()
### RECOMMENDED:, use bashrc
api_key = os.getenv("BOEING_OPENAI_API_KEY") # use if key is in env
together_key = os.getenv("TOGETHER_API_KEY") # use if key is in env

crossover_dates = fill_crossover_dates()
next_date_index = 0

client = openai.OpenAI(api_key=api_key)


def query_4o_mini(system_prompt, user_prompt):
    response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=10000
            ).choices[0].message.content
    return response

def query_4o_mini_and_correct_stati(system_prompt, user_prompt):
    response = query_4o_mini(system_prompt, user_prompt)
    user_prompt_stati = user_prompt + "\n" + "don't actually output the json yet, "
    user_prompt_stati += "just list all the fields and their corresponding status."
    status_list = query_4o_mini(system_prompt, user_prompt_stati)
    user_prompt_correction = user_prompt + "\n" + "now take the following output object"
    user_prompt_correction += "that you generated, along with the status list that you generated,"
    user_prompt_correction += "check if they match, and output a corrected version of the "
    user_prompt_correction += "json object where the stati match the status list."
    user_prompt_corretion += "Please do not output anything except for the json that I request, no comments nothing, as I am going to feed it directly into a python script. "
    user_prompt_correction += "here is the output object: \n"
    user_prompt_correction += response
    user_prompt_correction += "and here is the status list: \n"
    user_prompt_correction += status_list
    response = query_4o_mini(system_prompt, user_prompt_correction)
    return response

def query_block_10_times(system_prompt, block):
    user_prompt = block
    if(isinstance(block, list)):
        user_prompt = "\n".join(block)
    def run_once():
        response = query_4o_mini(system_prompt, user_prompt)
        j = 0
        while(j < 1):
            user_prompt_new = user_prompt
            user_prompt_new += "\nand here is the text a model already generated:"
            user_prompt_new += "\n\n" + response + "\n\n\n"
            user_prompt_new += "now please re-generate this same output, except correct all errors if there are any"
            #response = query_4o_mini_and_correct_stati(system_prompt, user_prompt)
            response = query_4o_mini(system_prompt, user_prompt)
            j += 1
        return response

    outputs = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(run_once) for _ in range(1)]
        for future in as_completed(futures):
            outputs.append(future.result())

    # Count frequency of each unique output
    output_counts = Counter(outputs)
    most_common_output, freq = output_counts.most_common(1)[0]
    try:
        response = most_common_output
        data = json.loads(response)
        response = flatten_single_item_lists_in_string(response)
        response = pretty_json_string(response)
        response_normed = normalize_spaces(response)
        user_prompt_normed = normalize_spaces(user_prompt)
        valid = True
        if(isinstance(block, list)):
            valid, missing = split_and_check_blocks(user_prompt_normed, response_normed)

            if not valid and shouldOutputMissing:
                print("\n===== VALIDATION FAILED =====")
                print("INPUT:\n", user_prompt)
                print("\nOUTPUT:\n", response)
                print("\nMISSING PIECE:\n", missing)
                print("=============================\n")
        json_valid = True

        return {
            "input_block": user_prompt,
            "most_common_output": response,
            "validation_passed": valid
        }

    except Exception as e:
        print("reponse:", response)
        print(f"error: {str(e)}")
        return {
            "input_block": user_prompt,
            "most_common_output": "{}",
            "validation_passed": False
        }

def query_block(system_prompt, block):
    user_prompt = block
    if(isinstance(block, list)):
        user_prompt = "\n".join(block)
    times_tried = 0
    times_to_try = 5
    json_valid = False
    response = ""
    while(times_tried < times_to_try and json_valid == False):
        try:
            response = query_4o_mini(system_prompt, user_prompt)
            response = flatten_single_item_lists_in_string(response)
            data = json.loads(response)
            response = relocate_rwy_end(data)
            response = json.dumps(response)
            response = pretty_json_string(response)
            response_normed = normalize_spaces(response)
            user_prompt_normed = normalize_spaces(user_prompt)
            valid = True
            if(isinstance(block, list)):
                valid, missing = split_and_check_blocks(user_prompt_normed, response_normed)

                if not valid:
                    boeingErrorOut("\n===== VALIDATION FAILED =====")
                    boeingErrorOut("INPUT:\n" + str(user_prompt))
                    boeingErrorOut("\nOUTPUT:\n" + str(response))
                    boeingErrorOut("\nMISSING PIECE:\n" + str(missing))
                    boeingErrorOut("=============================\n")
            json_valid = True

            return {
                "input_block": user_prompt,
                "most_common_output": response,
                "validation_passed": valid
            }

        except Exception as e:
            times_tried += 1
            if(times_tried >= times_to_try):
                print("reponse:", response)
                print(f"error: {str(e)}")
                print("user prompt:")
                print(user_prompt)
                exit()
                return {
                    "input_block": user_prompt,
                    "most_common_output": "{}",
                    "validation_passed": False
                }

def is_base_line_asterisks_mode(line, next_line):
    global headerType
    looks_like_base = is_base_line(line) or is_asterisk_line(line)
    looks_like_route_type = is_route_type_line(line)
    next_is_ifr_route_name = False
    if(next_line and headerType == "preferred"):
        next_is_ifr_route_name = is_preferred_ifr_route_name(next_line)
    is_route_type_line_var = looks_like_route_type and next_is_ifr_route_name
    return looks_like_base or is_route_type_line_var

def is_regular_line_asterisks_mode(line, next_line):
    return not is_base_line_asterisks_mode(line, next_line)

def is_preferred_ifr_route_name(line):
    num_asterisks = line.count('*')
    if line == line.lstrip("\t") and num_asterisks == 3:
        return True
    return False

firstCloserHeaderTypes = ["fixes", "preferred", "boundary", "airways", "military", "miscellaneous"]
specialCloserHeaderTypes = ["patterns"]
dateHeaderTypes = firstCloserHeaderTypes[:]
dateHeaderTypes.extend(specialCloserHeaderTypes)

directDateHeaderTypes = ["boundary", "airways", "military", "miscellaneous"]
def split_into_blocks_asterisks_mode(lines):
    global headerType, dateHeaderTypes, firstCloserHeaderTypes, specialCloserHeaderTypes
        
    blocks = []
    current_block = []
    
    endTexts = ""
    i = 0
    if(headerType in firstCloserHeaderTypes):
        endTexts = ["MODIFIED OR CANCELLED", "MODIFIED OR CANCELED", "MODIFIED, OR CANCELLED", "MODIFIED, OR CANCELED"]

    if(headerType == "patterns"):
        endTexts = ["AFFECTING CHARTS ARE INCLUDED IN THE LISTING."]
    if(headerType in dateHeaderTypes):
        found = False
        while(i < 6):
            for element in endTexts:
                if(element in lines[i]):
                    found = True
            if(found):
                break
            i += 1
        if(not found):
            boeingErrorOut("Catastrophic error, could not find the end of the opening text!")
            boeingErrorOut(lines[0:6])
            i = 10
            blocks.append("junk with no date specifically to trigger the date error")
        else:
            i += 1
            block0 = lines[0:i]
            blocks.append(block0)
            
    justPassedAsteriskLine = False
    #remove the first line if it is a page number
    if(len(lines) > 0):
        tempLine = lines[0]
        parts = split_tabs_preserve_spaces(tempLine.strip())
        if(tempLine and (tempLine.strip() == "" or (len(parts) == 2 and "Page" in parts))):
            lines.pop(i+1)
            shouldLoop = True
    while(i < len(lines)):
        current_line = lines[i]
        current_block.append(current_line.rstrip())
        next_line = ""
        shouldLoop = True 
        #this loop basically adds current_block to blocks when the current line is a regular line
        #and the next line is a base line
        while(shouldLoop):
            parts = ""
            next_line = lines[i + 1] if i + 1 < len(lines) else None
            if(next_line):
                parts = split_tabs_preserve_spaces(next_line.strip())
            shouldLoop = False
            if(next_line and (next_line.strip() == "" or (len(parts) == 2 and "Page" in parts))):
                lines.pop(i+1)
                shouldLoop = True

        next_line = lines[i + 1] if i + 1 < len(lines) else None
        next_line_2 = lines[i + 2] if i + 2 < len(lines) else None

        is_regular_line_var = is_regular_line_asterisks_mode(current_line, next_line)
        if next_line and is_preferred_ifr_route_name(next_line) and is_route_type_line(current_line):
            is_regular_line_var = False

        if is_regular_line_var and next_line and is_base_line_asterisks_mode(next_line, next_line_2):
            blocks.append(current_block)
            current_block = []
        justPassedAsteriskLine = False
        if(is_asterisk_line(current_line)):
            justPassedAsteriskLine = True
        i += 1

    if current_block:
        blocks.append(current_block)

    return blocks


asteriskHeaderTypes = ["fixes", "patterns", "preferred", "boundary", "airways", "military", "miscellaneous"]
directAsteriskHeaderTypes = ["boundary", "airways", "military", "miscellaneous"]
davidHeaders = ["military", "miscellaneous", "navaidcom"]
def process_file(file_path, output_path_ini, system_prompt):
    global headerType, dateHeaderTypes, asteriskHeaderTypes, directAsteriskHeaderTypes
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    blocks = []
    #first, split the file into a list of all the relevant blocks so the LLM can
    #read them one at a time
    if(headerType in asteriskHeaderTypes):
        print("using asterisk mode")
        blocks = split_into_blocks_asterisks_mode(lines)
    else:
        blocks = split_into_blocks(lines)

    date = ""
    valid_blocks = []
    lastSeenAsteriskStatus = ""
    lastSeenRouteType = ""
    for i, block in enumerate(blocks):
        if i == 0:
            #some header types have dates at the top, extract this from the first block
            if(headerType in dateHeaderTypes):
                tempRes = extract_date_from_first_block(block)
                if(not tempRes):
                    boeingErrorOut(("Catastrophic error! The default date is not shown in:" + str(headerType)))
                    break
                date = tempRes
            continue       
        #skip the recurring irrlevant block 
        if block[0].startswith("NFDD") and all(not c.isalpha() for c in "".join(block[0])):
            continue
        if(headerType in dateHeaderTypes):
            #look for a status in asterisks e.g. ESTABLISHED, CANCELLED 
            # or a route type so that we can store this 
            # and append it to all the other blocks below the current one, 
            # to which the header also applies
            i = 0
            while(i < len(block)):
                line = block[i]
                next_line = block[i + 1] if i + 1 < len(block) else None
                is_asterisk, status = extract_asterisk_banner_word(line)

                if(is_asterisk):
                    lastSeenAsteriskStatus = status
                    block.pop(i)
                    i -= 1
                elif next_line and is_preferred_ifr_route_name(next_line) and is_route_type_line(line):
                    lastSeenRouteType = line
                    block.pop(i)
                    i -= 1
                i += 1
            #insert the relevant default effective date, asterisk header, and route status
            statusString = "																			*  *  *  "+lastSeenAsteriskStatus+"  *  *  *"
            block.insert(0, lastSeenRouteType)
            block.insert(0, statusString)
            if(headerType in dateHeaderTypes and not headerType in directDateHeaderTypes):
                block.insert(0, date)
        valid_blocks.append(block)

    query_func = partial(query_block, system_prompt)
    results = []
    for block in valid_blocks:
        #set output to a blank object just in case we cannot perform parsing
        output = "{}"
        try:
            if(headerType in davidHeaders):
                blockTemp = "\n".join(block)
                print("stripping date")
                blockTemp = strip_nfdd_date(blockTemp)
                block = blockTemp.split("\n")
                print("done stripping date")
            #query the LLM to get the json version of the current block
            r = query_func(block)
            output = r["most_common_output"]
            date_needing_headers = ["airports", "towers", "frequencies", "stations", "systems", "navaidcom"]
            date_needing_headers.extend(directDateHeaderTypes)
            #if the current header is one where the LLM doesn't read the date, insert the date,
            #and pretty up the string
            if(headerType in date_needing_headers):
                #convert the output to json so it is easy to insert the date
                output = json.loads(output)
                next_effective_date = crossover_dates.iloc[next_date_index,1]
                next_effective_date = next_effective_date.strftime('%d/%m/%Y')
                output["default_date"] = next_effective_date
                #now convert the output back to a string, and pretty it up
                output = relocate_rwy_end(output)
                output = json.dumps(output)
                output = pretty_json_string(output)
            


        except Exception as e:
            print("one block of text could not be parsed")
            print(e)
        #add the output to the list
        results.append(output)

    #write the output to a file with a name that matches the input file, with a json extension
    output_path = os.path.splitext(output_path_ini)[0] + ".json"
    print("output_path:", output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    return output_path

def get_next_date_index(current_date):
    global next_date_index, crossover_dates
    i = 0
    while(i < len(crossover_dates)):
        tempComp = crossover_dates.iloc[i, 2]
        if(current_date <= tempComp):
            return i
        i += 1
    return -1

base_dir = os.getcwd() + "/src/"
def process_all_relevant_files(param, output_folder):
    global headerType, crossover_dates, next_date_index, base_dir

    #decide which prompts to load, each header uses the prompt for the previous headers
    #as part of its own prompt
    header_options = [
        "airports", "towers", "fixes", "patterns", "preferred",
        "frequencies", "boundary", "airways", "stations", "systems",
        "military", "miscellaneous", "navaidcom"
        ]
    david_header_options = [
        "military", "miscellaneous", "navaidcom"
    ]
    if(param == "options"):
        print("options:")
        print(header_options)
        exit()
    david_prompt_file_dict = {
        "military" : "MILITARY", "miscellaneous" : "MISCELLANEOUS", "navaidcom": "NAVAIDCOM"
    }
    david_test_file_dict = {
        "military" : "military", "miscellaneous" : "miscellaneous", "navaidcom": "navaidcom"
    }
    david_target_file_dict = {
        "military" : "MILITARY_TRAINING_ROUTE", "miscellaneous" : "MISCELLANEOUS_ACTIVITY_AREAS", "navaidcom": "NAVAIDCOM"
    }
    david_dictionaries = (david_prompt_file_dict, david_test_file_dict, david_target_file_dict)
        
    prompt_file_dict = {
        "airports": "AIRPORT", "towers": "TOWER", "fixes" : "FIXES", "patterns" : "PATTERNS","preferred" : "PREFERRED", 
        "frequencies": "FREQUENCIES", "boundary": "BOUNDARY", "airways": "AIRWAYS", "stations": "STATIONS", "systems": "SYSTEMS"
        }
    test_file_dict = {
        "airports": "airport", "towers": "tower", "fixes" : "fixes", "patterns" : "patterns", "preferred" : "preferred", 
        "frequencies": "frequencies", "boundary": "boundary", "airways": "airways", "stations": "stations", "systems": "systems"
        }
    target_file_dict = {
        "airports": "AIRPORT", "towers": "AIR_TRAFFIC_CONTROL_TOWERS", "fixes" : "AIRSPACE_FIXES", "patterns" : "PATTERNS", "preferred" : "PREFERRED_IFR_ROUTE", 
        "frequencies": "ARTCC_COMMUNICATIONS_FREQUENCIES", "boundary": "ARTCC_BOUNDARY_POINTS", "airways": "ATS_AIRWAYS", "stations": "FLIGHT_SERVICE_STATIONS", "systems": "INSTRUMENT_LANDING_SYSTEMS"
        }
    headerType = param
    input_folder="./sectioned_txt_files"
    system_prompt = ""
    correction_prompt = ""

    chosen_prompt_file_index = header_options.index(param)
    if(chosen_prompt_file_index == -1 or chosen_prompt_file_index >= len(header_options)):
        print("error, you entered a param not in the header options")
        exit()
    
    is_David_section = False
    #switch the file name lists if its one of David's files
    if(chosen_prompt_file_index > 9):
        prompt_file_dict, test_file_dict, target_file_dict = david_dictionaries
        header_options = david_header_options
        chosen_prompt_file_index = header_options.index(param)
        is_David_section = True

    chosen_test_file_part = test_file_dict[param]
    chosen_target_file_part = target_file_dict[param]

    system_prompt = ""
    if(is_David_section):
        chosen_prompt_file_part = prompt_file_dict[param]
        tempFileName = "./prompts_concat/" + (chosen_prompt_file_part+"_prompt_concat.txt")
        with open(tempFileName, "r", encoding='utf-8') as f:
            system_prompt_temp = f.read().strip()
            system_prompt += system_prompt_temp
    else:
        #generate the prompt by appending the prompts for all the relevant sections
        i = 0
        while(i < (chosen_prompt_file_index + 1)):
            chosen_prompt_file_part = prompt_file_dict[header_options[i]]
            tempFileName = "./prompts_concat/" + (chosen_prompt_file_part+"_prompt_concat.txt")
            with open(tempFileName, "r", encoding='utf-8') as f:
                system_prompt_temp = f.read().strip()
                system_prompt += system_prompt_temp
            i += 1

    system_prompt += "\n now here is the text that I actually want you to parse:"

    #load the test inputs and outputs 
    #HERE ARE THE TEST CASES:
    with open(("./test_cases/test_" + chosen_test_file_part + "_inputs.txt"), "r", encoding="utf-8") as f:
        raw_inputs = f.read()

    with open(("./test_cases/test_" + chosen_test_file_part + "_outputs.txt"), "r", encoding="utf-8") as f:
        raw_outputs = f.read()

    # Split input blocks by four blank lines (containing only whitespace)
    input_blocks = [block.strip() for block in raw_inputs.strip().split("\n\n\n\n") if block.strip()]
    
    # Split outputs by single blank lines
    output_blocks = [block.strip() for block in raw_outputs.strip().split("\n\n") if block.strip()]

    num_blocks = 0
    num_incorrect = 0

    shouldRunTests = False
    if(shouldRunTests):
        #error out if the number of test cases does not match the number of solutions 
        if len(input_blocks) != len(output_blocks):
            print("test cases:")
            print(f"ERROR: Number of inputs ({len(input_blocks)}) does not match number of outputs ({len(output_blocks)})")
            exit()
        #for each test case
        for i, (input_block, expected_output) in enumerate(zip(input_blocks, output_blocks), 1):
            print("running a test")
            num_blocks += 1

            #get the output from the LLM so we can check it 
            result = query_block(system_prompt, input_block.split("\n"))["most_common_output"]#.replace("'","\"")
            
            #normalize the output from the LLM and the desired output so they are easy to compare and see what's wrong if there is an issue
            #if the output is not normalized, then things might be correct but in different orders and therefore marked 
            #as wrong, just as one example. Plus if the two outputs don't match then we can't extract the difference 
            #and make it easy to see if the result is unsorted

            #see the NORMALIZATION STEPS comment to see what the normalization steps are
            result = normalize_json_string_and_sort(flatten_single_item_lists_in_string(result), use_tabs = False)
            expected = normalize_json_string_and_sort(flatten_single_item_lists_in_string(expected_output), use_tabs = False)

            result_to_show = result
            result_normed = normalize_spaces(result_to_show)
            expected_normed = normalize_spaces(expected)
            #if the outputs don't match
            if str(result_normed).strip() != expected_normed.strip():
                num_incorrect += 1
                print(f"Test {i} FAILED:")
                print("Input:")
                print(input_block)
                print("Expected Output:")
                print(expected)
                print("Actual Output:")
                print(result_to_show)
                print()
                #print out the list of all the differences and the line numbers where they occur
                #the line numbers are the lines of the normalized expected form, not the regular expect form,
                #and not of the output itself
                diffs = get_changed_blocks(result_normed, expected_normed)
                for i, (from_lines, to_lines, from_nums, to_nums) in enumerate(diffs, 1):
                    print(f"Change {i}:")
                    print("  - result:")
                    for line in from_lines:
                        print(f"    {line}")
                    print("  - to expected:")
                    for line in to_lines:
                        print(f"    {line}")
                    print("to_line_nums:", to_nums[0], to_nums[1])
                    print()

            print("accuracy:", (1.0*num_blocks-num_incorrect)/num_blocks)
        print("All tests ran.")
    for filename in os.listdir(input_folder):
        if chosen_target_file_part not in filename.upper() or "json" in filename:
            continue
        print(f"Processing file: {filename}")
        
        #get the date the file is from so we know the default effective date
        current_date = extract_date_from_filename(filename)
        next_date_index = get_next_date_index(current_date)

        file_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)
        process_file(file_path, output_path, system_prompt)

# Main
if __name__ == "__main__":
    # Check if exactly one parameter other than the program name is provided
    if len(sys.argv) != 2:
        print("Usage: python script.py <parameter>")
        print("in other words, you must enter exactly one parameter ")
        print("enter the parameter 'options' to see the list of options'")
        exit()
    
    # Extract the parameter
    param = sys.argv[1]
    
    print(f"The parameter you entered is: {param}")

    output_folder = "./processed_files_in_json"
    process_all_relevant_files(param, output_folder)

    print(f"Ensuring all JSON are strings and not objects...")
    print(f"Calling stringify_json_object...\n")

    clean_and_overwrite_json_files(output_folder)