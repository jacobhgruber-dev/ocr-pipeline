import os, time, json, traceback
from pathlib import Path
print("HF_HOME", os.environ.get("HF_HOME"), flush=True)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
out = Path("/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/work/docling_p1")
pipe = PdfPipelineOptions()
if hasattr(pipe, "do_ocr"):
    pipe.do_ocr = False
converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipe)})
results = []
pdfs = sorted(out.glob("*_p*-*.pdf"), key=lambda p: p.stat().st_size)
for slice_pdf in pdfs:
    sid = slice_pdf.name.split("_p")[0]
    t0 = time.time()
    print("CONVERT", sid, flush=True)
    try:
        res = converter.convert(str(slice_pdf))
        md = res.document.export_to_markdown()
        (out / f"{sid}.md").write_text(md, encoding="utf-8")
        row = {
            "sample_id": sid,
            "engine": "docling",
            "file": slice_pdf.name,
            "md_chars": len(md),
            "md_words": len(md.split()),
            "elapsed_s": round(time.time() - t0, 2),
            "pipe_tables": md.count("|---") + md.count("| ---"),
            "italics_stars": md.count("*"),
            "phase": "P1_docling",
        }
        results.append(row)
        print("OK", json.dumps(row), flush=True)
    except Exception as e:
        print("FAIL", sid, repr(e), flush=True)
        traceback.print_exc()
        results.append({"sample_id": sid, "engine": "docling", "error": str(e), "phase": "P1_docling"})
for p in list(out.rglob("*.png")):
    p.unlink(missing_ok=True)
Path("/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/results/docling_compare.jsonl").write_text(
    "\n".join(json.dumps(r) for r in results) + "\n"
)
print("DONE", len(results), flush=True)
