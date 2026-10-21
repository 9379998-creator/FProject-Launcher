# -*- coding: utf-8 -*-
import sys
from pathlib import Path

repo_root = Path(r"C:\Users\a9379\.gemini\antigravity\scratch\FProject-Launcher")
sys.path.insert(0, str(repo_root))

from app.backend.server import search_pdf_document

pdf_path = Path(r"C:\Users\a9379\.gemini\antigravity\scratch\26048-05_Matisov\НВФ_О1_к1.pdf")
res = search_pdf_document(pdf_path, "фасад")

print("--- Test search_pdf_document ---")
print("Query:", res["query"])
print("Total hits:", res["totalHits"])
print("Pages with hits:", res["pagesCount"])
print("Total pages in PDF:", res["totalPages"])

for p_num, p_data in sorted(res["pages"].items(), key=lambda x: int(x[0])):
    print(f"Page {p_num}: {p_data['count']} hits")
