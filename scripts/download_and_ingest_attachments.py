#!/usr/bin/env python3
"""Download law.go.kr attachments (flDownload.do) and ingest text into RAG JSONL.

Usage:
  python scripts/download_and_ingest_attachments.py --flSeq 159323931
  python scripts/download_and_ingest_attachments.py --url "https://www.law.go.kr/LSW/flDownload.do?flSeq=159323931"

Notes:
- Requires `requests` and `pdfminer.six` for PDF extraction. HWP extraction is best-effort when `pyhwp` is installed.
- Downloads into `data/law_attachments/` and appends extracted text as new JSONL docs to `data/rag_documents.jsonl`.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parents[1]
ATTACH_DIR = BASE_DIR / "data" / "law_attachments"
RAG_PATH = BASE_DIR / "data" / "rag_documents.jsonl"

os.makedirs(ATTACH_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dl_ingest")


def download_url(url: str, out_path: Path) -> Path:
    import requests

    logger.info(f"Downloading {url} -> {out_path}")
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with out_path.open("wb") as f:
        for chunk in resp.iter_content(8192):
            if chunk:
                f.write(chunk)
    return out_path


def extract_pdf_text(path: Path) -> str:
    try:
        from pdfminer.high_level import extract_text
    except Exception as e:  # pragma: no cover - dependency error
        logger.error("pdfminer.six is required for PDF extraction: %s", e)
        return ""
    try:
        text = extract_text(str(path))
        return text or ""
    except Exception as e:
        logger.exception("PDF extraction failed: %s", e)
        return ""


def extract_hwp_text(path: Path) -> str:
    # Try pyhwp if available
    try:
        import pyhwp
    except Exception:
        logger.warning("pyhwp not available; HWP extraction skipped for %s", path.name)
        return ""
    try:
        # Minimal pyhwp usage: open and extract text
        doc = pyhwp.HWPDocument(str(path))
        # pyhwp API varies; try common attribute
        text = ""
        for para in doc.body_text:
            text += para + "\n"
        return text
    except Exception as e:
        logger.exception("HWP extraction failed: %s", e)
        return ""


def make_doc(title: str, source_name: str, content: str, flseq: Optional[str] = None) -> dict:
    doc_id = f"RAG-LAW-{flseq or abs(hash(title))}"
    return {
        "doc_id": doc_id,
        "title": title,
        "source_type": "행정고시/첨부문서",
        "source_name": source_name,
        "content": content,
        "legal_citations": ["보세전시장 운영에 관한 고시 제6조"] if "특허" in title or "특허" in content else [],
        "keywords": ["보세전시장", "특허신청", "구비서류"],
        "category": "보세전시장 설정 및 관리",
        "effective_date": "",
        "risk_level": "low",
    }


def append_to_rag(doc: dict):
    logger.info("Appending doc %s to %s", doc.get("doc_id"), RAG_PATH)
    with RAG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")


def parse_flseq_from_url(url: str) -> Optional[str]:
    m = re.search(r"flSeq=(\d+)", url)
    if m:
        return m.group(1)
    return None


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--url", "-u", help="Full flDownload.do URL to download", action="append")
    p.add_argument("--flSeq", "-f", help="flSeq numeric id (can be repeated)", action="append")
    p.add_argument("--source-name", default="보세전시장 운영에 관한 고시 첨부", help="Source name to store in doc")
    args = p.parse_args(argv)

    urls = []
    if args.url:
        urls.extend(args.url)
    if args.flSeq:
        for fs in args.flSeq:
            urls.append(f"https://www.law.go.kr/LSW/flDownload.do?flSeq={fs}")

    if not urls:
        p.error("Please provide at least one --url or --flSeq")

    for url in urls:
        fl = parse_flseq_from_url(url)
        out_name = f"{fl or 'attachment'}.bin"
        out_path = ATTACH_DIR / out_name
        try:
            download_url(url, out_path)
        except Exception as e:
            logger.exception("Download failed for %s: %s", url, e)
            continue

        # Try to detect file type from header or filename
        text = ""
        suffix = out_path.suffix.lower()
        # If response had no extension, try to guess via magic bytes
        if suffix in {".pdf", ".bin"}:
            # treat as PDF first
            text = extract_pdf_text(out_path)

        if not text and out_path.suffix.lower() in {".hwp", ".bin"}:
            text = extract_hwp_text(out_path)

        # Fallback: try to read as text
        if not text:
            try:
                with out_path.open("r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except Exception:
                text = ""

        title = f"법령 첨부 {fl or out_path.name}"
        doc = make_doc(title=title, source_name=args.source_name, content=text, flseq=fl)
        append_to_rag(doc)

    logger.info("Done.")


if __name__ == "__main__":
    main()
