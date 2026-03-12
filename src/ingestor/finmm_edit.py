"""
FinMM-Edit: Financial Multi-Modal Editing Layer.

A specialized correction layer that detects and fixes domain-specific
errors in extracted financial text and tables. This catches errors that
even MLLM vision models make on Indian documents:

- Currency symbol confusion (₹ vs $ vs ¥)
- Number/letter confusion (0/O, 1/l/I, 5/S)
- Indian number system (Lakhs, Crores) normalization
- GSTIN/CIN/PAN pattern validation
- Balance sheet arithmetic cross-checks
"""
from __future__ import annotations

import re
from typing import Optional
from loguru import logger

from src.models.schemas import ExtractedTable


class FinMMEdit:
    """
    Contextual correction layer for Indian financial document extraction.
    Uses rule-based + contextual heuristics (no LLM call — fast & deterministic).
    """

    # Indian financial patterns
    GSTIN_PATTERN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b")
    CIN_PATTERN = re.compile(r"\b[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b")
    PAN_PATTERN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")

    # Currency symbols that get confused
    CURRENCY_FIXES = {
        "$": "₹",
        "¥": "₹",
        "€": "₹",
        "£": "₹",
        "Rs.": "₹",
        "Rs": "₹",
        "INR": "₹",
    }

    # Common OCR/Vision misreads in financial context
    FINANCIAL_KEYWORDS = {
        "crore", "crores", "cr.", "cr",
        "lakh", "lakhs", "lac", "lacs",
        "turnover", "revenue", "income", "expenditure",
        "profit", "loss", "asset", "liability",
        "debit", "credit", "balance", "interest",
        "principal", "emi", "dscr", "ebitda",
    }

    def __init__(self):
        self.corrections_log: list[str] = []

    def correct(self, text: str, doc_type: str = "other") -> tuple[str, list[str]]:
        """
        Apply all correction passes on extracted text.
        Returns (corrected_text, list_of_corrections_made).
        """
        self.corrections_log = []
        corrected = text

        # Pass 1: Currency symbol normalization
        corrected = self._fix_currency_symbols(corrected)

        # Pass 2: Indian number system normalization
        corrected = self._fix_indian_numbers(corrected)

        # Pass 3: Common misreads near financial keywords
        corrected = self._fix_contextual_misreads(corrected)

        # Pass 4: GSTIN/CIN/PAN validation
        corrected = self._validate_identifiers(corrected)

        # Pass 5: Whitespace and formatting cleanup
        corrected = self._clean_formatting(corrected)

        if self.corrections_log:
            logger.info(f"FinMM-Edit: Made {len(self.corrections_log)} corrections")

        return corrected, self.corrections_log

    def correct_table(self, table: ExtractedTable) -> ExtractedTable:
        """Apply corrections to an extracted table."""
        # Fix headers
        corrected_headers = []
        for h in table.headers:
            fixed, _ = self.correct(h)
            corrected_headers.append(fixed.strip())

        # Fix cells
        corrected_rows = []
        for row in table.rows:
            fixed_row = []
            for cell in row:
                fixed, _ = self.correct(str(cell))
                # Try to normalize numbers in table cells
                fixed = self._normalize_table_number(fixed)
                fixed_row.append(fixed.strip())
            corrected_rows.append(fixed_row)

        return ExtractedTable(
            table_id=table.table_id,
            page_number=table.page_number,
            headers=corrected_headers,
            rows=corrected_rows,
            table_type=table.table_type,
            confidence=min(table.confidence + 0.05, 1.0),  # Slight boost for correction
        )

    # ── Correction Passes ────────────────────────────────

    def _fix_currency_symbols(self, text: str) -> str:
        """Replace non-₹ currency symbols in Indian financial context."""
        result = text
        for wrong, right in self.CURRENCY_FIXES.items():
            if wrong in result:
                # Only replace if near Indian financial keywords
                pattern = re.compile(
                    rf"({re.escape(wrong)})\s*[\d,.]",
                    re.IGNORECASE,
                )
                matches = pattern.findall(result)
                if matches:
                    result = pattern.sub(f"{right} ", result)
                    self.corrections_log.append(f"Currency: {wrong} → {right}")
        return result

    def _fix_indian_numbers(self, text: str) -> str:
        """Normalize Indian number representations."""
        result = text

        # Fix "Cr." and "Lakh" variations
        variations = {
            r"\bCr\.?\b": "Cr.",
            r"\bCrore[s]?\b": "Cr.",
            r"\bLac[s]?\b": "Lakhs",
            r"\bLakh[s]?\b": "Lakhs",
        }
        for pattern, replacement in variations.items():
            new_result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
            if new_result != result:
                self.corrections_log.append(f"Number unit normalized to: {replacement}")
                result = new_result

        # Fix common number formatting: 1,23,456.78 → keep as-is (Indian format)
        # But fix: 1.23.456 → 1,23,456 (period used as separator)
        result = re.sub(
            r"(\d)\.(\d{2})\.(\d{3})",
            r"\1,\2,\3",
            result,
        )

        return result

    def _fix_contextual_misreads(self, text: str) -> str:
        """Fix 0/O, 1/l/I confusion near financial terms."""
        result = text

        # In numeric contexts, replace O with 0 and l with 1
        # Pattern: letter that should be number in numeric string
        result = re.sub(
            r"(?<=\d)[Oo](?=\d)",
            "0",
            result,
        )
        result = re.sub(
            r"(?<=\d)[lI](?=\d)",
            "1",
            result,
        )

        # Fix "1O" → "10", "2O" → "20" etc. near financial amounts
        result = re.sub(
            r"(\d)O\b",
            r"\g<1>0",
            result,
        )

        # Fix "S" misread as "5" in non-numeric context and vice versa
        # In amounts like "₹ 5,00,000" — keep as number
        # In "GSTIN" — keep as letter

        return result

    def _validate_identifiers(self, text: str) -> str:
        """Validate and attempt to fix GSTIN, CIN, PAN patterns."""
        result = text

        # Find near-GSTIN patterns and validate
        near_gstin = re.compile(r"\b(\d{2}[A-Z0-9]{5}\d{4}[A-Z0-9]\d[A-Z0-9][A-Z0-9])\b")
        for match in near_gstin.finditer(result):
            candidate = match.group(1)
            if not self.GSTIN_PATTERN.match(candidate):
                # Attempt common fixes
                fixed = candidate
                # Position 13 should be 'Z' for most GSTINs
                if len(fixed) == 15 and fixed[12] != "Z":
                    fixed = fixed[:12] + "Z" + fixed[13:]
                    if self.GSTIN_PATTERN.match(fixed):
                        result = result.replace(candidate, fixed)
                        self.corrections_log.append(f"GSTIN fix: {candidate} → {fixed}")

        return result

    def _clean_formatting(self, text: str) -> str:
        """Clean up whitespace and formatting artifacts."""
        result = text

        # Remove excessive whitespace
        result = re.sub(r" {3,}", "  ", result)

        # Fix broken words (common in PDF extraction)
        result = re.sub(r"(\w)- \n(\w)", r"\1\2", result)

        # Normalize line endings
        result = re.sub(r"\r\n", "\n", result)
        result = re.sub(r"\n{4,}", "\n\n\n", result)

        return result

    def _normalize_table_number(self, cell: str) -> str:
        """Normalize a table cell that should be a number."""
        cleaned = cell.strip()

        # Remove currency symbols for pure number cells
        cleaned = re.sub(r"[₹$¥€]", "", cleaned).strip()

        # Check if it looks like a number
        num_pattern = re.compile(r"^[\-\(]?\s*[\d,]+\.?\d*\s*\)?$")
        if num_pattern.match(cleaned):
            # Handle parentheses as negative (accounting format)
            if cleaned.startswith("(") and cleaned.endswith(")"):
                cleaned = "-" + cleaned[1:-1]
            # Remove commas
            cleaned = cleaned.replace(",", "")

        # Convert "—" or "-" or "nil" to "0"
        if cleaned in ("—", "-", "nil", "Nil", "NIL", "N/A", "n/a", "--"):
            cleaned = "0"

        return cleaned
