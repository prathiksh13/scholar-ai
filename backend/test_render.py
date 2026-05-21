import json
import traceback
import sys
from pathlib import Path
from app.models.document_schema import SemanticDocument
from app.services.renderer import render_semantic_to_pdf

try:
    file_path = "storage/uploads/ff_0cbbd4f3-7135-448a-8c2e-ab4880c864e0_semantic.json"
    document_id = "0cbbd4f3-7135-448a-8c2e-ab4880c864e0"
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    doc = SemanticDocument(**data)
    
    print(f"Elements: {len(doc.elements) if doc.elements else 0}")
    print(f"Figures: {len(doc.figures) if doc.figures else 0}")
    print(f"Tables: {len(doc.tables) if doc.tables else 0}")
    print(f"References: {len(doc.references) if doc.references else 0}")
    
    pdf_path = render_semantic_to_pdf(doc, document_id)
    print(f"Success: PDF rendered at {pdf_path}")

except Exception as e:
    traceback.print_exc()
    sys.exit(1)
