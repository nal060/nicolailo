import subprocess
import os
import shutil
import time
import sys

arg = ""
if len(sys.argv) > 1:
    arg = sys.argv[1]
    if(not (arg=="just_run_llm" or arg=="just_extract_text")):
        print("error, the first argument that you just entered is not allowed. Allowed args are: just_run_llm or just_extract_text")
        exit()
    print("First argument:", arg)
else:
    print("No command-line argument provided.")

startTime = time.time()
shouldJustReadTxt = False

#just_extract_text      just_run_llm

boeingErrorOutputName = "./boeingErrorOutput.txt"
with open(boeingErrorOutputName, "w") as f:
    f.write("All errors shown below, if the rest of the file is blank, there are no errors:\n")

def move_and_empty_folder(source_folder, target_folder):
    # Ensure absolute path
    source_folder = os.path.abspath(source_folder)

    #Create old_saved_contents folder in same parent directory
    old_stuff_folder = os.path.join(source_folder, '../old_saved_contents/', "")
    old_stuff_folder = os.path.abspath(old_stuff_folder)
    os.makedirs(old_stuff_folder, exist_ok=True)
    # Create "old_saved_contents/old_json" folder in same parent directory
    old_stuff_folder = os.path.join(source_folder, '../old_saved_contents/', target_folder)
    old_stuff_folder = os.path.abspath(old_stuff_folder)
    os.makedirs(old_stuff_folder, exist_ok=True)

    # Move all contents from source to old_stuff
    for item in os.listdir(source_folder):
        item_path = os.path.join(source_folder, item)
        dest_path = os.path.join(old_stuff_folder, item)
        shutil.move(item_path, dest_path)

    print(f"All contents moved from {source_folder} to {old_stuff_folder}")



base_dir = os.getcwd() + "/src/"

if(not arg == "just_run_llm"):
    if not shouldJustReadTxt:
        move_and_empty_folder("./processed_files_in_json", "./old_json")
        move_and_empty_folder("./converted_txt", "./old_converted_txt")
        move_and_empty_folder("./sectioned_txt_files", "./old_sectioned_txt")

        #now convert pdfs to text
        result = subprocess.run(["python", base_dir+"pdf_miner_grouper.py"])
        print(f"Output for pdf parser:\n{result.stdout}")
        if result.stderr:
            print(f"Error for pdf parser:\n{result.stderr}")

        #now split the text files up into the relevant parts
        subprocess.run(["python", base_dir+"section_splitter.py"])
        print(f"Output for section_splitter:\n{result.stdout}")
        if result.stderr:
            print(f"Error for section splitter:\n{result.stderr}")

if(arg=="just_extract_text"):
    exit()
print("about to start Zhengyi's section")
result = subprocess.run(
    ["python", "-u", base_dir + "Zhengyi_sections_productionized.py"],
)
#     capture_output=True,
#     text=True
# )
# print(f"Output for Zhengyi's Pipeline:\n{result.stdout}")
# if result.stderr:
#     print(f"Error for Zhengyi's Pipeline:\n{result.stderr}")

# Example list of arguments to pass to process_unified_LLM.py
argument_list = [
    "airports", "towers", "fixes", "patterns", "preferred",
    "frequencies", "boundary", "airways", "stations", "systems",
    "military", "miscellaneous", "navaidcom"
    ]
for arg in argument_list:
    result = subprocess.run(
        ["python", base_dir + "process_unified_LLM.py", arg],
        capture_output=True,
        text=True
    )
    print(f"Output for section '{arg}':\n{result.stdout}")
    if result.stderr:
        print(f"Error for argument '{arg}':\n{result.stderr}")

if not shouldJustReadTxt:
    move_and_empty_folder("./nfdd", "./old_pdfs")

endTime = time.time()
timeTaken = endTime - startTime
print("number of seconds taken:", timeTaken)