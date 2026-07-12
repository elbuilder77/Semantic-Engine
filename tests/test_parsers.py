from io import BytesIO

import pytest

from ses.core.parsers import extract_text_content


def test_extract_txt_content():
    content = extract_text_content(BytesIO(b"alpha beta"), "note.txt")

    assert content == "alpha beta"


def test_extract_csv_content_without_pandas():
    content = extract_text_content(BytesIO(b"name,amount\nSES,42\n"), "data.csv")

    assert "name | amount" in content
    assert "SES | 42" in content
    assert "[Error:" not in content


def test_extract_docx_content():
    docx = pytest.importorskip("docx")

    document = docx.Document()
    document.add_paragraph("Semantic Engine paragraph")
    payload = BytesIO()
    document.save(payload)
    payload.seek(0)

    content = extract_text_content(payload, "sample.docx")

    assert "Semantic Engine paragraph" in content
    assert "[Error:" not in content


def test_extract_xlsx_content():
    openpyxl = pytest.importorskip("openpyxl")

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Contracts"
    sheet.append(["client", "status"])
    sheet.append(["SES", "ready"])
    payload = BytesIO()
    workbook.save(payload)
    payload.seek(0)

    content = extract_text_content(payload, "sample.xlsx")

    assert "# Sheet: Contracts" in content
    assert "client | status" in content
    assert "SES | ready" in content
    assert "[Error:" not in content


def test_extract_pdf_content_uses_installed_pypdf_stack():
    fpdf = pytest.importorskip("fpdf")

    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Semantic PDF content")
    raw = pdf.output(dest="S")
    payload = BytesIO(bytes(raw))

    content = extract_text_content(payload, "sample.pdf")

    assert "Semantic PDF content" in content
    assert "[page 1]" in content
    assert "[Error:" not in content
