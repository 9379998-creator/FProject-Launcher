import sys
import os
import json
import time
import fitz  # PyMuPDF

def diagnose_pdf(pdf_path):
    print(f"Starting diagnosis for: {pdf_path}")
    start_time = time.time()
    
    file_size = os.path.getsize(pdf_path)
    
    # Open document safely (no full rasterization)
    t0 = time.time()
    doc = fitz.open(pdf_path)
    t_open = time.time() - t0
    
    page_count = len(doc)
    is_encrypted = doc.is_encrypted
    pdf_version = doc.metadata.get("format", "PDF")
    metadata = doc.metadata
    
    # Check TOC / Outlines
    toc = doc.get_toc()
    has_toc = len(toc) > 0
    toc_count = len(toc)
    
    # Check attachments
    attachments = []
    try:
        embedded_count = doc.embfile_count()
        for i in range(embedded_count):
            attachments.append(doc.embfile_name(i))
    except Exception as e:
        attachments = [f"Error checking attachments: {str(e)}"]
        
    # Check pages: sample page 0, middle page, last page, and scan first 20 pages for structure
    # Also check if text is extractable
    sample_indices = [0, page_count // 2, page_count - 1]
    sample_results = []
    
    total_images_sampled = 0
    total_text_chars_sampled = 0
    
    for idx in sample_indices:
        t_page_start = time.time()
        page = doc.load_page(idx)
        rect = page.rect
        rotation = page.rotation
        
        # Test render time at 150 DPI (matrix = 150/72)
        scale = 150.0 / 72.0
        mat = fitz.Matrix(scale, scale)
        t_render_start = time.time()
        pix = page.get_pixmap(matrix=mat, alpha=False)
        render_time = time.time() - t_render_start
        pix_bytes = len(pix.samples)
        pix_w, pix_h = pix.width, pix.height
        pix = None  # Free immediately
        
        # Text extraction
        text = page.get_text()
        text_len = len(text.strip())
        
        # Image count on page
        images = page.get_images()
        image_count = len(images)
        
        sample_results.append({
            "page_number": idx + 1,
            "width_pt": rect.width,
            "height_pt": rect.height,
            "orientation": "landscape" if rect.width > rect.height else "portrait",
            "rotation": rotation,
            "render_150dpi_seconds": round(render_time, 4),
            "render_dimensions": [pix_w, pix_h],
            "text_char_count": text_len,
            "image_count": image_count
        })
        
    # Broad scan: check first 30 pages and last 10 pages for text and font info
    has_fonts = False
    has_vector_drawings = False
    pages_with_text = 0
    pages_with_images = 0
    check_subset = list(range(min(20, page_count)))
    
    for idx in check_subset:
        p = doc.load_page(idx)
        fonts = p.get_fonts()
        if fonts:
            has_fonts = True
        txt = p.get_text()
        if len(txt.strip()) > 20:
            pages_with_text += 1
        imgs = p.get_images()
        if imgs:
            pages_with_images += 1
        drawings = p.get_drawings()
        if drawings:
            has_vector_drawings = True
            
    # Classify content
    if pages_with_text > 0 and pages_with_images > 0 and has_vector_drawings:
        doc_type = "Смешанный (векторные чертежи, растровые изображения, текстовые слои)"
    elif pages_with_text > 0 and has_vector_drawings:
        doc_type = "Преимущественно векторный (чертежи, схемы, типографика)"
    elif pages_with_images > 0 and pages_with_text == 0:
        doc_type = "Преимущественно растровый (сканы)"
    else:
        doc_type = "Смешанный технический каталог"

    total_time = time.time() - start_time
    
    report = {
        "file_name": os.path.basename(pdf_path),
        "file_size_bytes": file_size,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "page_count": page_count,
        "pdf_version": pdf_version,
        "is_encrypted": is_encrypted,
        "metadata": {
            "title": metadata.get("title"),
            "author": metadata.get("author"),
            "creator": metadata.get("creator"),
            "producer": metadata.get("producer"),
            "creation_date": metadata.get("creationDate"),
            "mod_date": metadata.get("modDate")
        },
        "has_toc": has_toc,
        "toc_entries_count": toc_count,
        "toc_sample": [item[1] for item in toc[:10]] if has_toc else [],
        "has_attachments": len(attachments) > 0,
        "attachments": attachments,
        "has_fonts": has_fonts,
        "text_extractable": pages_with_text > 0,
        "composition_type": doc_type,
        "has_vector_drawings": has_vector_drawings,
        "time_to_open_seconds": round(t_open, 4),
        "total_diagnosis_time_seconds": round(total_time, 4),
        "sample_pages": sample_results
    }
    
    return report

if __name__ == "__main__":
    pdf_path = r"G:\Общие диски\006_Информационная база\Каталоги профильных систем\0004 Reynaers\MASTERLINE 8 - 2019.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
        
    rep = diagnose_pdf(pdf_path)
    
    out_dir = r"C:\Users\a9379\.gemini\antigravity\scratch\fero-launcher-v4-dwg-audit\runtime\logs"
    os.makedirs(out_dir, exist_ok=True)
    
    json_path = os.path.join(out_dir, "pdf-diagnostics-masterline8.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f"JSON saved to {json_path}")
    print("Done. Page count:", rep["page_count"])
