import torch
import json
import random
from together import Together
from dotenv import load_dotenv
import os
import numpy as np
from pathlib import Path
from section_splitter import process_files


together_key = ""

together_key = os.getenv("TOGETHER_API_KEY") # use if key is in envs

# ========== Set random seed ==========
def set_seed(seed=2025):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

# ========== Estimate tokens ==========
def estimate_tokens(text):
    return len(text) // 4  # Approximate: 1 token ≈ 4 characters

# ========== Filter specific section files ==========
def filter_section_files(folder_path, section_keyword, exclude_keywords=None):
    section_files = []
    for filename in os.listdir(folder_path):
        if not filename.endswith(".txt"):
            continue
        # print("filename:", filename)
        # print("key:", section_keyword)
        upper_name = filename.upper()
        if section_keyword in upper_name:
            if exclude_keywords and any(ex_kw in upper_name for ex_kw in exclude_keywords):
                continue
            section_files.append(os.path.join(folder_path, filename))
    return section_files

# ========== Main processing function ==========
def process_section_with_llm(section_keyword, input_folder, output_folder, prompt_path, output_json_folder, exclude_keywords=None, seed=2025):
    # load_dotenv(dotenv_path="/Users/apple/Documents/UBC_MDSCL/Block_6/COLX563/lab4/.env") # Change the path to your .env file where the TOGETHER_API_KEY is stored
    # load_dotenv(dotenv_path="/Users/apple/Documents/UBC_MDSCL/Block_6/COLX563/lab4/.env") # Change the path to your .env file where the TOGETHER_API_KEY is stored
    #key = os.getenv("TOGETHER_API_KEY")
    key = together_key
    llm_client = Together(api_key=together_key)
    model_name = "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free" # May change the model with better performance
    
    set_seed(seed)
    print("filtering section files ")
    target_files = filter_section_files(output_folder, section_keyword.upper(), exclude_keywords)
    
    print("Current working directory:", os.getcwd())
    with open(prompt_path, "r") as file:
        prompt = file.read()
    
    Path(output_json_folder).mkdir(parents=True, exist_ok=True)

    for file_path in target_files:
        print("at file:", file_path)
        with open(file_path, "r") as f:
            text = f.read()

        # Dynamic max_tokens based on input
        full_prompt = f"{prompt.strip()}\n\n{text.strip()}"
        input_token_estimate = estimate_tokens(full_prompt)
        max_total_tokens = 8192
        safe_max_tokens = max_total_tokens - input_token_estimate
        safe_max_tokens = max(256, min(safe_max_tokens, 2048))
        print("about to get response")
        response = llm_client.chat.completions.create(
            model=model_name,
            max_tokens=safe_max_tokens,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.0
        )
        print("about to convert response")
        response_json = response.choices[0].message.content
        base_filename = os.path.basename(file_path).replace(".txt", ".json")
        output_path = os.path.join(output_json_folder, base_filename)
        print("about to try")
        # Handle LLM response safely: parse JSON and catch format errors
        try:
            parsed_json = json.loads(response_json)
            with open(output_path, "w") as out_f:
                json.dump(parsed_json, out_f, indent=2)
            print("output_path:", output_path)
            print(f"Successfully parsed and saved: {output_path}")
        except json.JSONDecodeError as e:
            print(f"JSON parsing failed for: {file_path}")
            print(f"Error: {e}")
    
            debug_path = os.path.join(output_json_folder, base_filename.replace(".json", "_RAW.txt"))
            with open(debug_path, "w") as debug_file:
                debug_file.write(response_json)

            print(f"Raw LLM response saved to: {debug_path}")

    print("Processing complete.")

# ========== Example ==========
# from generalized_pipeline import process_section_with_llm

# MILITARY TRAINING ROUTE
# process_section_with_llm(
#     section_keyword="MILITARY TRAINING ROUTE",  # or any other header
#     input_folder="./converted_txt",
#     output_folder="./sectioned_txt_files",
#     prompt_path="./src/helper/prompt/MILITARY_TRAINING_ROUTE_prompt.txt",
#     output_json_folder="./military_training_route_parsed_jsons",
#     exclude_keywords=[""],  # Optional
#     seed=2025  # Optional
# )

