from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTTextLine, LTChar
import os
import sys

# Global storage
all_headers = set()
log_file_path = "header_extraction_log.txt"

# Logger setup
def log(message="", end="\n"):
    print(message, end=end)
    with open(log_file_path, "a", encoding="utf-8") as log_file:
        log_file.write(str(message) + end)

def save_pdf_details_to_txt(pdf_path, output_txt_path):
    global all_headers
    log(f"Processing: {pdf_path}")
    start_x = 28.5
    headers_in_this_file = set()

    with open(output_txt_path, "w", encoding="utf-8") as out_file:
        for page_layout in extract_pages(pdf_path):
            chars = []
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    for text_line in element:
                        if isinstance(text_line, LTTextLine):
                            for character in text_line._objs:
                                if isinstance(character, LTChar):
                                    chars.append(character)

            if not chars:
                continue

            rows = []
            for char in chars:
                added_to_row = False
                for row in rows:
                    if abs(char.y0 - row[0].y0) <= 1:
                        row.append(char)
                        added_to_row = True
                        break
                if not added_to_row:
                    rows.append([char])

            rows.sort(key=lambda r: -sum(c.y0 for c in r) / len(r))

            for row_chars in rows:
                row_chars.sort(key=lambda c: c.x0)
                output_line = ""
                last_x1 = None
                row_text = ""
                font_set = set()
                for char in row_chars:
                    font_set.add(char.fontname)
                    row_text += char.get_text()
                    if last_x1 is None:
                        if char.x0 > start_x:
                            num_tabs = int((char.x0 - start_x) // 12)
                            output_line += "\t" * num_tabs
                    else:
                        gap = char.x0 - last_x1
                        if gap > 5:
                            num_tabs = int(gap // 12)
                            output_line += "\t" * max(1, num_tabs)
                    output_line += char.get_text()
                    last_x1 = char.x1

                out_file.write(output_line + "\n")

                # Header detection logic
                cleaned_row_text = row_text.strip()
                if (
                    cleaned_row_text and
                    all(f == 'AAAAAA+TimesNewRoman,Bold' for f in font_set) and
                    cleaned_row_text.upper() == cleaned_row_text and
                    not cleaned_row_text.startswith("NFDD")
                ):
                    headers_in_this_file.add(cleaned_row_text)

    # Determine and log new headers
    new_headers = headers_in_this_file - all_headers
    if new_headers:
        log("→ New headers found in this file:")
        for header in sorted(new_headers):
            log("   " + header)
    else:
        log("→ No new headers found in this file.")

    all_headers.update(headers_in_this_file)

# -------- Batch conversion --------

input_pdf_folder = './nfdd'
output_txt_folder = './converted_txt'

os.makedirs(output_txt_folder, exist_ok=True)

# Clear or create the log file
with open(log_file_path, "w", encoding="utf-8") as f:
    f.write("=== PDF Header Extraction Log ===\n\n")

# Process all PDF files
for file_name in os.listdir(input_pdf_folder):
    if file_name.lower().endswith('.pdf'):
        pdf_path = os.path.join(input_pdf_folder, file_name)
        output_txt_path = os.path.join(output_txt_folder, f"{file_name[:-4]}.txt")

        if not os.path.isfile(pdf_path):
            log(f"File not found: {pdf_path} — skipping")
            continue

        save_pdf_details_to_txt(pdf_path, output_txt_path)
        log(f"✔ Processed: {file_name} -> {output_txt_path}\n")

# Final summary
log("\n=== Final List of All Unique Headers ===")
for header in sorted(all_headers):
    log(header)