"""
Vision-Native Document Parser using Multimodal LLMs.
Skips OCR entirely — parses scanned Indian PDFs via vision models.
Includes FinMM-Edit correction layer for domain-specific errors.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from loguru import logger

from src.utils.llm_client import llm_client
from src.models.schemas import (
    ExtractedDocument,
    ExtractedTable,
    FinancialMetrics,
)
from src.ingestor.finmm_edit import FinMMEdit


VISION_SYSTEM_PROMPT = """You are an expert Indian financial document parser.
You are analyzing a scanned page from an Indian corporate document.

Rules:
- Extract ALL text preserving the original structure.
- For tables, output them in a structured format with clear headers and rows.
- Indian currency is ALWAYS ₹ (Indian Rupee), never $ or ¥.
- Correctly identify GSTIN (15 chars), CIN (21 chars), PAN (10 chars) patterns.
- Distinguish between 0 (zero) and O (letter), 1 (one) and l (letter).
- Amounts in Lakhs or Crores — preserve the unit.
- "Cr." = Crores, "L" or "Lacs" = Lakhs.
"""

DOC_CLASSIFY_PROMPT = """Classify this Indian financial document into ONE of:
- annual_report
- financial_statement
- bank_statement
- gst_return
- itr (Income Tax Return)
- legal_notice
- sanction_letter
- board_minutes
- rating_report
- shareholding_pattern
- mca_filing
- other

Also extract: company name, document period/date, and key identifiers (CIN, GSTIN, PAN).

Respond as JSON:
{
    "doc_type": "...",
    "company_name": "...",
    "period": "...",
    "cin": "...",
    "gstin": "...",
    "pan": "...",
    "key_observations": ["..."]
}"""

TABLE_EXTRACTION_PROMPT = """Extract ALL tabular data from this document page.
For each table found, provide:
1. Table headers (column names)
2. All data rows
3. What type of table it is (balance_sheet, pnl, cash_flow, gst_summary, bank_txn, other)

Output as JSON:
{
    "tables": [
        {
            "table_type": "...",
            "headers": ["col1", "col2", ...],
            "rows": [["val1", "val2", ...], ...]
        }
    ]
}

IMPORTANT:
- ₹ symbol, not $ or ¥
- Preserve Lakhs/Crores units
- "—" or "-" means nil/zero
- Carry forward headers from previous pages if this is a continuation"""

FINANCIAL_EXTRACTION_PROMPT = """From this financial data, extract the following metrics.
If a value is not present, use null.

Output as JSON:
{
    "fiscal_year": "2023-24",
    "revenue_cr": null,
    "ebitda_cr": null,
    "pat_cr": null,
    "total_assets_cr": null,
    "total_liabilities_cr": null,
    "net_worth_cr": null,
    "current_ratio": null,
    "debt_equity_ratio": null,
    "interest_coverage_ratio": null,
    "dscr": null,
    "tol_tnw": null,
    "working_capital_cr": null,
    "cash_flow_from_operations_cr": null
}

Convert all amounts to Crores. 1 Crore = 100 Lakhs = 10 Million."""


class VisionParser:
    """Parse documents using vision-native MLLM + FinMM-Edit."""

    def __init__(self):
        self.finmm = FinMMEdit()
        self._temp_dir = Path("data/temp_pages")
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    async def parse(self, file_path: str | Path) -> ExtractedDocument:
        """Parse a document file (PDF or image) into structured data."""
        file_path = Path(file_path)
        logger.info(f"Parsing document: {file_path.name}")

        if file_path.suffix.lower() == ".pdf":
            return await self._parse_pdf(file_path)
        elif file_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
            return await self._parse_image(file_path)
        else:
            # Treat as text file
            return await self._parse_text(file_path)

    async def _parse_pdf(self, pdf_path: Path) -> ExtractedDocument:
        """Convert PDF pages to images, parse each with vision model."""
        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        logger.info(f"PDF has {page_count} pages")

        # Convert pages to images
        page_images = []
        for i in range(page_count):
            page = doc[i]
            # Render at 300 DPI for quality
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_path = self._temp_dir / f"{pdf_path.stem}_page_{i + 1}.png"
            pix.save(str(img_path))
            page_images.append(img_path)
        doc.close()

        # Classify the document from first page
        classification = await self._classify_document(page_images[0])
        doc_type = classification.get("doc_type", "other")

        # Parse all pages (parallel batches of 3)
        all_text_parts = []
        all_tables = []
        batch_size = 3

        for batch_start in range(0, len(page_images), batch_size):
            batch = page_images[batch_start:batch_start + batch_size]
            tasks = [self._parse_single_page(img, idx + batch_start + 1) for idx, img in enumerate(batch)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Page parse failed: {result}")
                    continue
                text, tables = result
                all_text_parts.append(text)
                all_tables.extend(tables)

        full_text = "\n\n---PAGE BREAK---\n\n".join(all_text_parts)

        # Apply FinMM-Edit corrections
        corrected_text, corrections = self.finmm.correct(full_text, doc_type)
        corrected_tables = [self.finmm.correct_table(t) for t in all_tables]

        # Calculate confidence
        total_chars = len(full_text)
        correction_chars = sum(len(c) for c in corrections)
        confidence = max(0.0, 1.0 - (correction_chars / max(total_chars, 1)))

        # Cleanup temp files
        for img in page_images:
            try:
                img.unlink()
            except OSError:
                pass

        return ExtractedDocument(
            source_file=str(pdf_path),
            doc_type=doc_type,
            extracted_text=corrected_text,
            tables=corrected_tables,
            metadata=classification,
            extraction_confidence=confidence,
            finmm_corrections=corrections,
        )

    async def _parse_image(self, image_path: Path) -> ExtractedDocument:
        """Parse single image document."""
        classification = await self._classify_document(image_path)
        text, tables = await self._parse_single_page(image_path, 1)
        corrected_text, corrections = self.finmm.correct(text, classification.get("doc_type", "other"))

        return ExtractedDocument(
            source_file=str(image_path),
            doc_type=classification.get("doc_type", "other"),
            extracted_text=corrected_text,
            tables=tables,
            metadata=classification,
            extraction_confidence=0.85,
            finmm_corrections=corrections,
        )

    async def _parse_text(self, text_path: Path) -> ExtractedDocument:
        """Handle plain text/CSV files."""
        content = text_path.read_text(encoding="utf-8", errors="ignore")
        return ExtractedDocument(
            source_file=str(text_path),
            doc_type="structured_data",
            extracted_text=content,
            extraction_confidence=0.95,
        )

    async def _classify_document(self, image_path: Path) -> dict:
        """Classify document type from first page."""
        try:
            result = await llm_client.vision_parse_json(
                image_path=image_path,
                prompt=DOC_CLASSIFY_PROMPT,
                system_prompt=VISION_SYSTEM_PROMPT,
            )
            logger.info(f"Classified as: {result.get('doc_type', 'unknown')}")
            return result
        except Exception as e:
            logger.warning(f"Classification failed: {e}")
            return {"doc_type": "other"}

    async def _parse_single_page(
        self, image_path: Path, page_num: int
    ) -> tuple[str, list[ExtractedTable]]:
        """Parse a single page into text + tables."""
        # Extract text
        text = await llm_client.vision_parse(
            image_path=image_path,
            prompt=f"Extract all text from page {page_num} of this Indian financial document. Preserve structure.",
            system_prompt=VISION_SYSTEM_PROMPT,
        )

        # Extract tables
        tables = []
        try:
            table_data = await llm_client.vision_parse_json(
                image_path=image_path,
                prompt=TABLE_EXTRACTION_PROMPT,
                system_prompt=VISION_SYSTEM_PROMPT,
            )
            for t in table_data.get("tables", []):
                tables.append(ExtractedTable(
                    page_number=page_num,
                    headers=t.get("headers", []),
                    rows=t.get("rows", []),
                    table_type=t.get("table_type", "other"),
                    confidence=0.85,
                ))
        except Exception as e:
            logger.warning(f"Table extraction failed on page {page_num}: {e}")

        return text, tables

    async def extract_financials(
        self, doc: ExtractedDocument
    ) -> list[FinancialMetrics]:
        """Extract structured financial metrics from a parsed document."""
        if not doc.tables and not doc.extracted_text:
            return []

        # Build context from tables and text
        context = doc.extracted_text[:4000]
        if doc.tables:
            for t in doc.tables[:5]:
                context += f"\n\nTable ({t.table_type}):\n"
                if t.headers:
                    context += " | ".join(t.headers) + "\n"
                for row in t.rows[:20]:
                    context += " | ".join(str(v) for v in row) + "\n"

        try:
            result = await llm_client.generate_json(
                prompt=f"Financial data:\n{context}\n\n{FINANCIAL_EXTRACTION_PROMPT}",
                system_prompt="You are an Indian chartered accountant extracting financial metrics.",
            )

            # Could be a single year or multiple years
            if isinstance(result, list):
                return [FinancialMetrics(**r) for r in result]
            else:
                return [FinancialMetrics(**result)]
        except Exception as e:
            logger.error(f"Financial extraction failed: {e}")
            return []
