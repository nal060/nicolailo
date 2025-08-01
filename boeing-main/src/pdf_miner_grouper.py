from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTTextLine, LTChar
import os

def save_pdf_details_to_txt(pdf_path, output_txt_path):
    print(f"Processing: {pdf_path}")  # Debug log
    start_x = 28.5  # New starting point for tab calculations

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
                gapDivisor = 11
                for char in row_chars:
                    if last_x1 is None:
                        if char.x0 > start_x:
                            num_tabs = int((char.x0 - start_x) // gapDivisor)
                            output_line += "\t" * num_tabs
                    else:
                        gap = char.x0 - last_x1
                        if gap > 5:
                            num_tabs = int(gap // gapDivisor)
                            output_line += "\t" * max(1, num_tabs)
                    output_line += char.get_text()
                    last_x1 = char.x1
                out_file.write(output_line + "\n")

# -------- Batch conversion below --------

input_pdf_folder = './nfdd'
output_txt_folder = './converted_txt'

# Ensure the output folder exists
os.makedirs(output_txt_folder, exist_ok=True)

# Loop through all PDFs in the input folder
for file_name in os.listdir(input_pdf_folder):
    if file_name.lower().endswith('.pdf'):
        pdf_path = os.path.join(input_pdf_folder, file_name)
        output_txt_path = os.path.join(output_txt_folder, f"{file_name[:-4]}.txt")

        # Double-check file exists
        if not os.path.isfile(pdf_path):
            print(f"File not found: {pdf_path} — skipping")
            continue

        save_pdf_details_to_txt(pdf_path, output_txt_path)
        print(f"✔ Processed: {file_name} -> {output_txt_path}")