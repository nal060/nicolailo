import os
import re

def clean_file_content(src_path):
    with open(src_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove everything after the last "page\t+\d+"
    match = list(re.finditer(r'page(?:\t+)(\d+)', content, re.IGNORECASE))
    if match:
        last_match = match[-1]
        return content[:last_match.start()]
    return content

def is_valid_header(line):
    # Must start with at least 10 tabs
    starts_with_ten_tabs = re.match(r'^\t{10,}', line) is not None
    is_upper = line.strip() == line.strip().upper()
    contains_letters = re.search(r'[A-Z]', line.upper()) is not None
    contains_nfdd_and_digit = 'NFDD' in line.upper() and re.search(r'\d', line)
    contains_nfdd_phrase = 'NATIONAL FLIGHT DATA DIGEST' in line.upper()
    contains_three_asterisks = line.count('*') >= 3
    contains_altitude_route = 'ALTITUDE ROUTE' in line.upper()
    inHeaderList = False
    lineText = line.strip()
    if(lineText in ["AIR TRAFFIC CONTROL TOWERS","AIRPORT","AIRSPACE FIXES","ARTCC  COMMUNICATIONS  FREQUENCIES","ARTCC BOUNDARY POINTS","ATS AIRWAYS","FLIGHT  SERVICE  STATIONS","HOLDING PATTERNS","INSTRUMENT LANDING SYSTEMS","MILITARY TRAINING ROUTE","MISCELLANEOUS ACTIVITY AREAS","NATIONAL FLIGHT DATA DIGEST","NAVAID/COM","NAVAIDS","PARACHUTE JUMPING AREAS","PREFERRED IFR ROUTE","SPECIAL ACTIVITY AIRSPACE","VOR RECEIVER CHECK POINTS"]):
        inHeaderList = True
    return (
        starts_with_ten_tabs and
        is_upper and
        contains_letters and
        inHeaderList and
        not (
            contains_nfdd_and_digit or
            contains_nfdd_phrase or
            contains_three_asterisks or
            contains_altitude_route
        )
    )

def sanitize_filename_part(text, max_len=40):
    text = text.strip().replace('\t', ' ').replace('\n', ' ')
    text = re.sub(r'[^a-zA-Z0-9_\- ]+', '', text)
    text = re.sub(r'\s+', '_', text)
    return text[:max_len]

def split_into_sections(content):
    lines = content.splitlines()
    sections = []
    current_section = []
    header_line = None

    for line in lines:
        if is_valid_header(line):
            if current_section:
                sections.append((header_line, current_section))
            header_line = line
            current_section = [line]
        else:
            if current_section:
                current_section.append(line)

    if current_section:
        sections.append((header_line, current_section))
    return sections

def split_and_check_blocks(block1, block2):
    # Split the first block by newlines and tabs
    blocks1 = [line.strip() for line in block1.splitlines()]
    split_blocks1 = [item for line in blocks1 for item in line.split('\t') if item]

    # Check if each block from block1 appears in block2
    for block in split_blocks1:
        if block not in block2:
            print(f"Block '{block}' from block1 is not found in block2.")
            return False

    print("All blocks from block1 are found in block2.")
    return True



def process_files(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)

    for filename in os.listdir(input_folder):
        if not filename.endswith(".txt"):
            continue
        if filename in ['nfdd-2024-07-25-143.txt', 'nfdd-2024-08-06-151.txt']:
            continue
        # if filename not in ["nfdd-2023-08-08-151.txt"]:
        #     continue 

        src_path = os.path.join(input_folder, filename)
        #print(f"Processing file: {filename}...")

        cleaned_content = clean_file_content(src_path)
        sections = split_into_sections(cleaned_content)

        base_filename = os.path.splitext(filename)[0]
        for i, (header, section_lines) in enumerate(sections, 1):
            short_header = sanitize_filename_part(header if header else "NO_HEADER")
            section_filename = f"{base_filename}_SECTION_{i:02d}_{short_header}.txt"
            section_path = os.path.join(output_folder, section_filename)
            with open(section_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(section_lines))

    print("✅ All files cleaned, split, and saved with headers in filenames.")

if __name__ == "__main__":
    input_folder = "./converted_txt"
    output_folder = "./sectioned_txt_files"
    process_files(input_folder, output_folder)