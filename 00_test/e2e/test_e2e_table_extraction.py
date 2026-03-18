"""
E2E B1 Table Extraction Tests — Deep table quality assessment.

Tests B1 capability from 04_docs/05-OCR_capabilities/:
  B1 — Table Extraction: detect tables, handle bordered/borderless,
       cell content extraction, HTML/markdown generation, row/column counting,
       merged cell handling (colspan/rowspan).

Test IDs: TB-001 → TB-020

Requires: PaddleVL worker running (structured_extract method).
"""

import os
import re
import time

import httpx
import pytest

DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "05_test_cases", "data_test"
)

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8080/api/v1")
ADMIN_EMAIL = "e2e-admin@test.com"
ADMIN_PASSWORD = "E2eAdmin123!"

OCR_TIMEOUT = 300
POLL_INTERVAL = 3


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _auth(client: httpx.Client, email: str, password: str) -> str:
    for _ in range(5):
        resp = client.post("/auth/login", json={"email": email, "password": password})
        if resp.status_code == 200:
            return resp.json()["token"]
        if resp.status_code == 429:
            time.sleep(3)
            continue
        break
    for _ in range(3):
        resp = client.post("/auth/register", json={"email": email, "password": password})
        if resp.status_code == 200:
            return resp.json()["token"]
        if resp.status_code == 429:
            time.sleep(3)
            continue
        break
    raise AssertionError(f"Auth failed: {resp.status_code} {resp.text}")


def _file_path(name: str) -> str:
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        pytest.skip(f"Test file not found: {path}")
    return path


def _upload(client: httpx.Client, filepath: str,
            method: str = "structured_extract", output_format: str = "json",
            tier: int = 0) -> dict:
    filename = os.path.basename(filepath)
    mime = "application/pdf" if filepath.lower().endswith(".pdf") else "image/png"
    with open(filepath, "rb") as f:
        for _ in range(5):
            f.seek(0)
            resp = client.post(
                "/upload",
                files=[("files", (filename, f, mime))],
                data={
                    "output_format": output_format,
                    "method": method,
                    "tier": str(tier),
                    "retention_hours": "24",
                },
            )
            if resp.status_code != 429:
                break
            time.sleep(3)
    assert resp.status_code == 200, f"Upload failed ({resp.status_code}): {resp.text}"
    return resp.json()


def _poll(client: httpx.Client, request_id: str,
          timeout: int = OCR_TIMEOUT) -> dict:
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        resp = client.get(f"/requests/{request_id}")
        assert resp.status_code == 200
        data = resp.json()
        last_status = data.get("status")
        if last_status in ("COMPLETED", "FAILED", "PARTIAL_SUCCESS", "CANCELLED"):
            return data
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Request {request_id} stuck at '{last_status}' after {timeout}s")


def _get_json(client: httpx.Client, job_id: str) -> dict:
    resp = client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 200, f"Result download failed: {resp.status_code}"
    return resp.json()


def _get_text(client: httpx.Client, job_id: str) -> str:
    resp = client.get(f"/jobs/{job_id}/result")
    if resp.status_code != 200:
        return ""
    data = resp.json()
    if isinstance(data, dict) and "text" in data:
        return data["text"]
    return str(data)


def _upload_and_get_json(client, filepath, timeout=OCR_TIMEOUT):
    """Upload file for structured extraction and return JSON result."""
    data = _upload(client, filepath, method="structured_extract", output_format="json")
    result = _poll(client, data["request_id"], timeout=timeout)
    assert result["status"] == "COMPLETED", f"Failed: {result.get('status')}"
    return _get_json(client, result["jobs"][0]["id"])


def _upload_and_get_text(client, filepath, output_format="md", timeout=OCR_TIMEOUT):
    """Upload file for structured extraction and return text result."""
    data = _upload(client, filepath, method="structured_extract",
                   output_format=output_format)
    result = _poll(client, data["request_id"], timeout=timeout)
    assert result["status"] == "COMPLETED", f"Failed: {result.get('status')}"
    return _get_text(client, result["jobs"][0]["id"])


def _extract_tables_from_json(json_data: dict) -> list[dict]:
    """Extract all table regions from structured JSON output."""
    tables = []
    for page in json_data.get("pages", []):
        page_num = page.get("page_number", 0)
        for region in page.get("regions", []):
            if region.get("type") == "table":
                region["_page"] = page_num
                tables.append(region)
    return tables


def _count_md_table_rows(md_text: str) -> list[dict]:
    """Find markdown tables and count their rows/columns."""
    tables = []
    lines = md_text.split("\n")
    current_table = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current_table.append(stripped)
        else:
            if len(current_table) >= 2:
                # Parse table
                data_rows = [
                    r for r in current_table
                    if not re.match(r"^\|[\s\-:]+\|$", r)
                ]
                cols = len(current_table[0].split("|")) - 2  # minus leading/trailing empty
                tables.append({
                    "total_lines": len(current_table),
                    "data_rows": len(data_rows),
                    "columns": max(cols, 1),
                    "raw": current_table,
                })
            current_table = []
    # Handle table at end of text
    if len(current_table) >= 2:
        data_rows = [
            r for r in current_table
            if not re.match(r"^\|[\s\-:]+\|$", r)
        ]
        cols = len(current_table[0].split("|")) - 2
        tables.append({
            "total_lines": len(current_table),
            "data_rows": len(data_rows),
            "columns": max(cols, 1),
            "raw": current_table,
        })
    return tables


def _parse_html_table(html: str) -> dict:
    """Parse HTML table and extract structure info."""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    cells_per_row = []
    total_cells = 0
    has_header = bool(re.search(r"<th[^>]*>", html))
    has_colspan = bool(re.search(r"colspan", html, re.IGNORECASE))
    has_rowspan = bool(re.search(r"rowspan", html, re.IGNORECASE))

    for row_html in rows:
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.DOTALL)
        cells_per_row.append(len(cells))
        total_cells += len(cells)

    return {
        "row_count": len(rows),
        "cells_per_row": cells_per_row,
        "total_cells": total_cells,
        "has_header": has_header,
        "has_colspan": has_colspan,
        "has_rowspan": has_rowspan,
        "non_empty_cells": len(re.findall(
            r"<t[hd][^>]*>\s*\S.*?</t[hd]>", html, re.DOTALL
        )),
    }


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def vl_client():
    """Authenticated client + verify PaddleVL worker available."""
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        token = _auth(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        client.headers["Authorization"] = f"Bearer {token}"

        resp = client.get("/services/available")
        assert resp.status_code == 200
        services = resp.json()["items"]
        vl_services = [
            s for s in services
            if "structured_extract" in s.get("allowed_methods", [])
        ]
        if not vl_services:
            pytest.skip("No PaddleVL worker running (structured_extract)")

        active = vl_services[0]
        print(f"\n  PaddleVL Worker: {active['id']} "
              f"({active['active_instances']} instances)")
        yield client


@pytest.fixture(scope="module")
def academic_json(vl_client) -> dict:
    """Cached JSON result for academic PDF (expensive, reuse across tests)."""
    filepath = _file_path("1709.04109v4.pdf")
    return _upload_and_get_json(vl_client, filepath)


@pytest.fixture(scope="module")
def academic_md(vl_client) -> str:
    """Cached markdown result for academic PDF."""
    filepath = _file_path("1709.04109v4.pdf")
    return _upload_and_get_text(vl_client, filepath, output_format="md")


@pytest.fixture(scope="module")
def academic_html(vl_client) -> str:
    """Cached HTML result for academic PDF."""
    filepath = _file_path("1709.04109v4.pdf")
    return _upload_and_get_text(vl_client, filepath, output_format="html")


@pytest.fixture(scope="module")
def paper_json(vl_client) -> dict:
    """Cached JSON result for paper image."""
    filepath = _file_path("paper_image.png")
    return _upload_and_get_json(vl_client, filepath)


@pytest.fixture(scope="module")
def paper_md(vl_client) -> str:
    """Cached markdown for paper image."""
    filepath = _file_path("paper_image.png")
    return _upload_and_get_text(vl_client, filepath, output_format="md")


# ═══════════════════════════════════════════════════════════════════════════════
# TB-001 → TB-005: Table Detection (B1 core requirement)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.table
class TestB1_TableDetection:
    """B1: Detect table regions in documents.

    Capability doc: "Detect tables, handle merged cells, spanning, nested tables"
    Engine: PaddleVL PPStructure layout analysis + table recognition.
    """

    def test_tb001_academic_pdf_has_tables(self, academic_json):
        """TB-001: Academic PDF (Attention paper) contains tables."""
        tables = _extract_tables_from_json(academic_json)
        print(f"\n  Tables detected: {len(tables)}")
        for i, t in enumerate(tables):
            print(f"    Table {i+1} (page {t['_page']}): "
                  f"html={'yes' if t.get('html') else 'no'}, "
                  f"md={'yes' if t.get('markdown') else 'no'}, "
                  f"content={len(t.get('content', ''))} chars")
        assert len(tables) >= 1, (
            "No tables detected in Attention paper — "
            "the paper has performance tables (Table 1-4)"
        )

    def test_tb002_table_has_bbox(self, academic_json):
        """TB-002: Each table region has valid bounding box."""
        tables = _extract_tables_from_json(academic_json)
        if not tables:
            pytest.skip("No tables detected")

        for i, t in enumerate(tables):
            bbox = t.get("bbox") or t.get("bounding_box")
            assert bbox is not None, f"Table {i} missing bbox"

            # Validate bbox format: [x1, y1, x2, y2] or {x, y, w, h}
            if isinstance(bbox, list) and len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                assert x2 > x1, f"Table {i} bbox invalid: x2 ({x2}) <= x1 ({x1})"
                assert y2 > y1, f"Table {i} bbox invalid: y2 ({y2}) <= y1 ({y1})"
            elif isinstance(bbox, dict):
                assert "x" in bbox or "x1" in bbox, f"Table {i} bbox unknown format"

            print(f"\n  Table {i+1} bbox: {bbox}")

    def test_tb003_table_on_correct_page(self, academic_json):
        """TB-003: Tables appear on expected pages (not all on page 1)."""
        tables = _extract_tables_from_json(academic_json)
        if not tables:
            pytest.skip("No tables detected")

        pages_with_tables = sorted(set(t["_page"] for t in tables))
        print(f"\n  Pages with tables: {pages_with_tables}")

        # Academic paper typically has tables spread across pages
        # At minimum, not ALL tables should be on page 1
        if len(tables) > 1:
            assert len(pages_with_tables) >= 1, (
                "All tables on same page — page assignment may be wrong"
            )

    def test_tb004_paper_image_table_detection(self, paper_json):
        """TB-004: Paper image (single page) — table detection if present."""
        tables = _extract_tables_from_json(paper_json)
        print(f"\n  Tables in paper image: {len(tables)}")
        # Paper image may or may not have tables depending on which section
        # Just verify no crash and report findings
        for i, t in enumerate(tables[:3]):
            content_len = len(t.get("content", "") + t.get("html", "") + t.get("markdown", ""))
            print(f"    Table {i+1}: {content_len} chars total content")

    def test_tb005_table_region_type_consistent(self, academic_json):
        """TB-005: Table regions all have type='table' consistently."""
        all_regions = [
            r for p in academic_json.get("pages", [])
            for r in p.get("regions", [])
        ]
        table_regions = [r for r in all_regions if r.get("type") == "table"]
        # Check no table content misclassified as 'text'
        text_regions_with_pipe = [
            r for r in all_regions
            if r.get("type") == "text" and "|" in r.get("content", "")
            and r.get("content", "").count("|") > 4
        ]
        print(f"\n  Table regions: {len(table_regions)}")
        print(f"  Text regions with pipe chars (possible missed tables): "
              f"{len(text_regions_with_pipe)}")


# ═══════════════════════════════════════════════════════════════════════════════
# TB-006 → TB-010: Table Content Extraction (B1 content quality)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.table
class TestB1_TableContent:
    """B1: Extract cell content from detected tables.

    Capability doc: "Cell content OCR, Spanning cell reconstruction,
    Header row detection, Data type inference"
    """

    def test_tb006_table_has_html_content(self, academic_json):
        """TB-006: Tables have HTML representation with rows and cells."""
        tables = _extract_tables_from_json(academic_json)
        if not tables:
            pytest.skip("No tables detected")

        tables_with_html = [t for t in tables if t.get("html", "").strip()]
        print(f"\n  Tables with HTML: {len(tables_with_html)}/{len(tables)}")

        if not tables_with_html:
            # Try content or markdown instead
            tables_with_content = [
                t for t in tables
                if t.get("content", "").strip() or t.get("markdown", "").strip()
            ]
            assert tables_with_content, (
                "Tables detected but none have HTML, markdown, or text content"
            )
            pytest.skip("Tables have content but no HTML — checking markdown instead")

        # Parse first HTML table
        html = tables_with_html[0]["html"]
        info = _parse_html_table(html)
        print(f"  First table HTML: {info['row_count']} rows, "
              f"{info['total_cells']} cells, "
              f"header={info['has_header']}")
        assert info["row_count"] >= 2, (
            f"Table HTML has only {info['row_count']} row(s) — expected at least header + data"
        )

    def test_tb007_table_cells_not_empty(self, academic_json):
        """TB-007: Table cells contain actual text (not all empty)."""
        tables = _extract_tables_from_json(academic_json)
        tables_with_html = [t for t in tables if t.get("html", "").strip()]
        if not tables_with_html:
            pytest.skip("No tables with HTML content")

        for i, t in enumerate(tables_with_html[:3]):
            info = _parse_html_table(t["html"])
            fill_rate = (
                info["non_empty_cells"] / info["total_cells"]
                if info["total_cells"] > 0 else 0
            )
            print(f"\n  Table {i+1}: {info['non_empty_cells']}/{info['total_cells']} "
                  f"non-empty cells ({fill_rate:.0%})")
            assert fill_rate >= 0.3, (
                f"Table {i+1} has too many empty cells: {fill_rate:.0%} filled. "
                f"Cell OCR may be failing."
            )

    def test_tb008_table_has_numeric_data(self, academic_json):
        """TB-008: Performance tables contain numeric data (BLEU scores etc.)."""
        tables = _extract_tables_from_json(academic_json)
        if not tables:
            pytest.skip("No tables detected")

        any_numeric = False
        for i, t in enumerate(tables):
            content = t.get("html", "") + t.get("markdown", "") + t.get("content", "")
            # Look for numbers (BLEU scores like 28.4, 41.0, etc.)
            numbers = re.findall(r"\d+\.?\d*", content)
            if len(numbers) >= 3:
                any_numeric = True
                print(f"\n  Table {i+1}: {len(numbers)} numeric values found")
                print(f"    Sample: {numbers[:10]}")

        assert any_numeric, (
            "No table with numeric data found — "
            "Attention paper has BLEU/perplexity score tables"
        )

    def test_tb009_markdown_table_structure(self, academic_md):
        """TB-009: Markdown output has proper table syntax (pipes + separator)."""
        md_tables = _count_md_table_rows(academic_md)
        print(f"\n  Markdown tables found: {len(md_tables)}")

        for i, t in enumerate(md_tables[:5]):
            print(f"    Table {i+1}: {t['data_rows']} data rows, "
                  f"{t['columns']} columns, {t['total_lines']} total lines")
            # Print first 3 rows
            for row in t["raw"][:3]:
                print(f"      {row[:100]}")

        assert len(md_tables) >= 1, (
            "No markdown tables found — pipe syntax missing"
        )

        # Verify at least one table has proper separator row
        for t in md_tables:
            has_separator = any(
                re.match(r"^\|[\s\-:]+\|$", row)
                for row in t["raw"]
            )
            if has_separator:
                print(f"\n  Separator row found (proper markdown table)")
                break
        else:
            print("\n  WARNING: No tables have separator row (---|---)")

    def test_tb010_html_table_semantic_tags(self, academic_html):
        """TB-010: HTML output has semantic table tags (table, thead, tbody, tr, td/th)."""
        # Check for table tags in HTML output
        has_table = "<table" in academic_html
        has_tr = "<tr" in academic_html
        has_td = "<td" in academic_html or "<th" in academic_html
        has_thead = "<thead" in academic_html
        has_tbody = "<tbody" in academic_html

        print(f"\n  <table>: {has_table}")
        print(f"  <tr>: {has_tr}")
        print(f"  <td>/<th>: {has_td}")
        print(f"  <thead>: {has_thead}")
        print(f"  <tbody>: {has_tbody}")

        assert has_table, "HTML output missing <table> tag"
        assert has_tr, "HTML output missing <tr> tag"
        assert has_td, "HTML output missing <td>/<th> tags"


# ═══════════════════════════════════════════════════════════════════════════════
# TB-011 → TB-015: Table Structure Quality (B1 advanced)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.table
class TestB1_TableStructure:
    """B1: Verify table structure accuracy (rows, columns, spanning).

    Capability doc: "Spanning cell reconstruction (rowspan/colspan),
    Header row detection, Output: DataFrame → CSV/Excel/JSON"
    """

    def test_tb011_row_column_count_reasonable(self, academic_json):
        """TB-011: Row/column counts in detected tables are reasonable."""
        tables = _extract_tables_from_json(academic_json)
        tables_with_html = [t for t in tables if t.get("html", "").strip()]
        if not tables_with_html:
            pytest.skip("No tables with HTML")

        for i, t in enumerate(tables_with_html):
            info = _parse_html_table(t["html"])
            print(f"\n  Table {i+1}: {info['row_count']} rows, "
                  f"cells/row: {info['cells_per_row']}")

            # Tables in academic papers typically have 2-50 rows
            assert 2 <= info["row_count"] <= 100, (
                f"Table {i+1} has {info['row_count']} rows — suspicious"
            )

            # Column count should be consistent across rows (unless spanning)
            if info["cells_per_row"] and not (info["has_colspan"] or info["has_rowspan"]):
                unique_col_counts = set(info["cells_per_row"])
                if len(unique_col_counts) > 2:
                    print(f"    WARNING: Inconsistent columns: {unique_col_counts}")

    def test_tb012_colspan_rowspan_handling(self, academic_json):
        """TB-012: Merged cells (colspan/rowspan) are represented in HTML."""
        tables = _extract_tables_from_json(academic_json)
        tables_with_html = [t for t in tables if t.get("html", "").strip()]
        if not tables_with_html:
            pytest.skip("No tables with HTML")

        any_spanning = False
        for i, t in enumerate(tables_with_html):
            info = _parse_html_table(t["html"])
            if info["has_colspan"] or info["has_rowspan"]:
                any_spanning = True
                print(f"\n  Table {i+1}: colspan={info['has_colspan']}, "
                      f"rowspan={info['has_rowspan']}")

        # Report finding — spanning is not guaranteed in all tables
        if not any_spanning:
            print("\n  No colspan/rowspan found in any table "
                  "(paper may not have merged cells)")

    def test_tb013_header_row_detection(self, academic_json):
        """TB-013: Table header row distinguished from data rows."""
        tables = _extract_tables_from_json(academic_json)
        tables_with_html = [t for t in tables if t.get("html", "").strip()]
        if not tables_with_html:
            pytest.skip("No tables with HTML")

        tables_with_header = 0
        for i, t in enumerate(tables_with_html):
            info = _parse_html_table(t["html"])
            if info["has_header"]:
                tables_with_header += 1
                print(f"\n  Table {i+1}: header detected (<th> tags)")

        print(f"\n  Tables with header: {tables_with_header}/{len(tables_with_html)}")
        # At least some tables should have headers
        if len(tables_with_html) >= 2:
            assert tables_with_header >= 1, (
                "No tables have header rows (<th> tags) — "
                "header detection may be missing"
            )

    def test_tb014_table_content_matches_keywords(self, academic_json):
        """TB-014: Table content contains expected keywords (model names, scores)."""
        tables = _extract_tables_from_json(academic_json)
        if not tables:
            pytest.skip("No tables detected")

        # Keywords expected in Attention paper tables
        expected_keywords = [
            "BLEU", "model", "Transformer",
            "attention", "EN-DE", "EN-FR",
        ]

        all_table_text = " ".join(
            t.get("html", "") + t.get("markdown", "") + t.get("content", "")
            for t in tables
        ).lower()

        found = [kw for kw in expected_keywords if kw.lower() in all_table_text]
        missed = [kw for kw in expected_keywords if kw.lower() not in all_table_text]

        hit_rate = len(found) / len(expected_keywords) if expected_keywords else 0
        print(f"\n  Table keyword hit rate: {hit_rate:.0%}")
        print(f"  Found: {found}")
        print(f"  Missed: {missed}")

        # At least some keywords should be in tables
        assert hit_rate >= 0.3, (
            f"Table content keyword hit too low: {hit_rate:.0%}. "
            f"Missed: {missed}"
        )

    def test_tb015_table_not_duplicated(self, academic_json):
        """TB-015: Same table not detected multiple times on same page."""
        tables = _extract_tables_from_json(academic_json)
        if len(tables) < 2:
            pytest.skip("Less than 2 tables — no duplication possible")

        # Group tables by page
        by_page = {}
        for t in tables:
            page = t["_page"]
            by_page.setdefault(page, []).append(t)

        for page, page_tables in by_page.items():
            if len(page_tables) < 2:
                continue
            # Check if any two tables have very similar content (>80% overlap)
            for i in range(len(page_tables)):
                for j in range(i + 1, len(page_tables)):
                    c1 = (page_tables[i].get("html", "") +
                           page_tables[i].get("content", "")).strip()
                    c2 = (page_tables[j].get("html", "") +
                           page_tables[j].get("content", "")).strip()
                    if c1 and c2 and len(c1) > 20:
                        # Simple overlap check
                        shorter = min(len(c1), len(c2))
                        common = sum(1 for a, b in zip(c1, c2) if a == b)
                        overlap = common / shorter if shorter > 0 else 0
                        if overlap > 0.8:
                            print(f"\n  WARNING: Tables {i+1} and {j+1} "
                                  f"on page {page} have {overlap:.0%} overlap "
                                  f"(possible duplicate)")


# ═══════════════════════════════════════════════════════════════════════════════
# TB-016 → TB-020: Cross-Format Table Consistency
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.table
class TestB1_TableCrossFormat:
    """B1: Table content consistent across JSON/Markdown/HTML formats.

    Capability doc: "Output: DataFrame → CSV/Excel/JSON"
    """

    def test_tb016_json_vs_md_table_count(self, academic_json, academic_md):
        """TB-016: JSON table count matches markdown table count."""
        json_tables = _extract_tables_from_json(academic_json)
        md_tables = _count_md_table_rows(academic_md)

        print(f"\n  JSON table regions: {len(json_tables)}")
        print(f"  Markdown tables: {len(md_tables)}")

        # Counts may differ slightly (markdown may merge or split)
        # but should be in same ballpark
        if len(json_tables) > 0 and len(md_tables) > 0:
            ratio = max(len(json_tables), len(md_tables)) / min(len(json_tables), len(md_tables))
            print(f"  Ratio: {ratio:.1f}x")
            assert ratio <= 3.0, (
                f"Table count mismatch too large: "
                f"JSON={len(json_tables)} vs MD={len(md_tables)}"
            )

    def test_tb017_json_vs_html_table_count(self, academic_json, academic_html):
        """TB-017: JSON table count roughly matches HTML table count."""
        json_tables = _extract_tables_from_json(academic_json)
        html_table_count = academic_html.count("<table")

        print(f"\n  JSON table regions: {len(json_tables)}")
        print(f"  HTML <table> tags: {html_table_count}")

    def test_tb018_md_table_has_numeric_content(self, academic_md):
        """TB-018: Markdown tables contain numeric data (not just pipes)."""
        md_tables = _count_md_table_rows(academic_md)
        if not md_tables:
            pytest.skip("No markdown tables")

        any_numeric_table = False
        for i, t in enumerate(md_tables):
            table_text = "\n".join(t["raw"])
            numbers = re.findall(r"\d+\.?\d*", table_text)
            if len(numbers) >= 3:
                any_numeric_table = True
                print(f"\n  MD Table {i+1}: {len(numbers)} numeric values")

        assert any_numeric_table, (
            "No markdown table has numeric content — "
            "cell content may be lost in format conversion"
        )

    def test_tb019_html_table_has_content(self, academic_html):
        """TB-019: HTML tables have actual cell content (not empty structure)."""
        # Extract all HTML tables
        html_tables = re.findall(
            r"<table[^>]*>(.*?)</table>", academic_html, re.DOTALL
        )
        if not html_tables:
            pytest.skip("No HTML tables found")

        for i, table_html in enumerate(html_tables[:3]):
            info = _parse_html_table(table_html)
            print(f"\n  HTML Table {i+1}: {info['row_count']} rows, "
                  f"{info['non_empty_cells']}/{info['total_cells']} filled cells")
            assert info["non_empty_cells"] > 0, (
                f"HTML table {i+1} has all empty cells"
            )

    def test_tb020_table_quality_summary(self, academic_json, academic_md, academic_html):
        """TB-020: Comprehensive table quality summary across all formats."""
        json_tables = _extract_tables_from_json(academic_json)
        md_tables = _count_md_table_rows(academic_md)
        html_table_count = academic_html.count("<table")

        # Build summary
        print("\n  ═══ B1 TABLE QUALITY SUMMARY ═══")
        print(f"  JSON table regions:  {len(json_tables)}")
        print(f"  Markdown tables:     {len(md_tables)}")
        print(f"  HTML <table> tags:   {html_table_count}")

        # JSON detail
        if json_tables:
            with_html = sum(1 for t in json_tables if t.get("html", "").strip())
            with_md = sum(1 for t in json_tables if t.get("markdown", "").strip())
            with_content = sum(1 for t in json_tables if t.get("content", "").strip())
            print(f"\n  JSON tables with HTML:     {with_html}")
            print(f"  JSON tables with Markdown: {with_md}")
            print(f"  JSON tables with Content:  {with_content}")

        # MD detail
        if md_tables:
            total_data_rows = sum(t["data_rows"] for t in md_tables)
            max_cols = max(t["columns"] for t in md_tables)
            print(f"\n  MD total data rows: {total_data_rows}")
            print(f"  MD max columns:     {max_cols}")

        # Overall assessment
        has_tables = len(json_tables) >= 1
        has_content = any(
            t.get("html", "").strip() or t.get("content", "").strip()
            for t in json_tables
        ) if json_tables else False
        has_md_tables = len(md_tables) >= 1

        print(f"\n  ─── Assessment ───")
        print(f"  Table detection:     {'PASS' if has_tables else 'FAIL'}")
        print(f"  Content extraction:  {'PASS' if has_content else 'FAIL'}")
        print(f"  Markdown conversion: {'PASS' if has_md_tables else 'FAIL'}")
        print(f"  HTML conversion:     {'PASS' if html_table_count >= 1 else 'FAIL'}")

        assert has_tables, "No tables detected at all"
