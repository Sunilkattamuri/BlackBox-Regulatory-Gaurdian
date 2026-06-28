import docx
import re

try:
    doc = docx.Document(r"c:\Users\ksuni\Sunil\Personal\MTech-BITS\Sem-4\Dissertation\BlackBox-Regulatory-Gaurdian\MID_SEM_REPORT_2024AA05522.docx")
    
    citations = {}
    in_bib = False
    for para in doc.paragraphs:
        if "8. BIBLIOGRAPHY" in para.text:
            in_bib = True
        elif in_bib and len(para.text.strip()) > 0:
            match = re.match(r"\[(\d+)\]\s*(.*)", para.text)
            if match:
                citations[match.group(1)] = match.group(2)
    
    print("Found Citations:")
    for k, v in citations.items():
        print(f"[{k}] {v}")

except Exception as e:
    print(f"Error: {e}")
