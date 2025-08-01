# Boeing NFDD Parsing Pipeline

This project parses and structures FAA National Flight Data Digest (NFDD) documents. It extracts PDFs from the FAA website, converts them to plain text, and outputs structured JSON grouped by section, state, and location.

---

# How to use this project:
1. Open a terminal in the boeing folder. 
2. Empty the boeing/nfdd folder, then place the pdf that you want to parse
    into said folder. If there is no such folder, just create an empty one with that name yourself.
3. Run 
python ./src/read_whole_pdf.py 
in the terminal in the boeing folder 
4. Locate the extracted json files in the /src/processed_files_in_json folder.
5. Locate any helpful error messages that might tell you which sections need to be re-done manually in the boeingErrorOutput.txt file.
6. If you want an accuracy higher than around 90%, you will have to manually verify all of the outputs in process_files_in_json since the 
    system is not accurate 100% of the time, and does not output an error message every time it gets something wrong
7. If you suspect that the system has fallen prey to any issues or failures, check the 
    "troubleshooting" section for how to resolve them 
8. Note that once the system runs and saves the json to process_files_in_json, if you run
    the system again, those json files all get moved to old_saved_contents/old_json, so it 
    doesn't truly delete its own previous work. 

## How to handle exception headers
1. Firstly, run this command: 
python ./src/read_whole_pdf.py just_extract_text
2. Once it has finished, you will have to manually go through each generated text file 
    in boeing/src/sectioned_txt_files and see if any of them contain the unexpected header 
    (exactly one of them should). When you find the unexpected header, delete it and all the contents 
    after it from that text file.
3. Then run:
python ./src/read_whole_pdf.py just_run_llm


## Troubleshooting:
1. Is is possible that the splitter in the process_unified_LLM program failed to deted the end
    of a date section at the end of the pdf. If you see anything like "catastrophic error" or
    "failed to find the end of date section" in the error log, then this issue is likely
    occuring. If this is the case, firstly run the command:
    python ./src/read_whole_pdf.py just_extract_text
    then go check all the txt files 
    generated in src/sectioned_txt_files and make sure that each of them either has 
    a) no section that looks like this near the top:
    	ALL AZIMUTHS ARE MAGNETIC AND FROM THE FACILITY.
	ALL DISTANCES ARE IN NAUTICAL MILES.
	EFFECTIVE 6/12/2025 OR AS NOTED THE FOLLOWING AIRSPACE FIXES
	ARE ESTABLISHED MODIFIED OR CANCELLED AS INDICATED.

    or b) if it has such a section, you should edit it. Make sure that the section is no more 
    than 4 lines long, that it has no more than one newline character between the section and 
    the title of the document, and that it also has these words in order on its last line: 
    MODIFIED OR CANCELLED
    and that those three words are spelled correctly.
    so long as all of those things are true of the section, the issue should be fixed, and you
    should not see that catastrophic error anymore, and you can run the command:
    python ./src/read_whole_pdf.py just_run_llm

2.  The secondary pipeline that handles the following sections: NAVAIDS
    PARACHUTE JUMPING AREAS     SPECIAL ACTIVITY AIRSPACE       VOR RECEIVER CHECK POINTS
    is more failure prone than the other pipeline. If you see the word "RAW" in any of the 
    files pertaining to any of these sections in the output json folder, then it has likely 
    failed at least some of its parsing. If this occurs, you will need to either manually 
    parse those particular sections, or you can edit the intermediate text files a little 
    and still have them parsed automatically. Here's how it can be done:
    firstly run:
    python ./src/read_whole_pdf.py just_extract_text
    then go find all the text files pertaining to those headers in src/sectioned_txt_files
    and you will need to effectively make several copies of each of those text files, and
    delete most of the information from most copies, such that each copy only has about 4 
    blocks of text in it, and between all the copies, every block of text that was originally 
    present is still there. Make sure to leave the top of file header in each copy of the file 
    that you create, as the automatic parser expects that to be present.
    Then once you have finished doing that, run 
    python ./src/read_whole_pdf.py just_run_llm
    and once that is complete, the system will have extracted all possible output to the best 
    of its ability


3. There could be some new headers that the system hasn't seen before (although this is
    generally unlikely). This error here is quite rare, and if you ever encounter it then you should probably
    upgrade the system to handle the new headers.  If you suspect that there are any, Look through the pdf, and make a list of all the headers (meaning bold
    underlined text) it contains, if any of them do not appear in the list 
    in the file titled "acceptable_headers.txt".
    they will have to be dealt with manually, and will have their information appear in some misread form in one of the text files. 
    If you find such a header, you will have to follow the instructions below 
    labeled "How to handle exception headers". Note that sometimes there is one 
    space and sometimes there are two between the words in header names, so if you want to use control+f to search for a header in the file, you will have 
    to make sure that you change it to have only one space between words before 
    you can use control f. 


---

## Scripts Overview

### src/special_utilities/download_pdfs.py

Downloads all linked PDFs into `data/raw_pdfs/`.

### src/pdf_miner_grouper.py

Parses each FAA PDF layout using PDFMiner and writes a tab-aligned `.txt` version to `data/raw_txt/`.

### src/special_utilities/extract_headers.py

Identifies and logs headers within these structured text files.

### src/section_splitter.py

Splits the structured text files into separate files based on previously detected headers.

### src/process_unified_LLM.py & src/llm_process_pipeline.py

Parses individual section files into structured JSON using an LLM.

---

## Installation

Install required dependencies using:

    pip install -r requirements.txt

---

## Contributors

- Cole Piche
- David Kang
- Nicole Lopez
- Zhengyi Shan
