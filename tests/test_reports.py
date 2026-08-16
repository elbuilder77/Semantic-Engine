import os
from unittest.mock import patch

import pytest

from ses.core.reports import EnterpriseReportPDF, FPDF, ReportService

def test_report_generation(tmp_path):
    # Mocking FPDF since it might not be in the environment
    output_dir = tmp_path / "reports"
    service = ReportService(output_dir=str(output_dir))
    
    query = "Test query"
    answer = "Test answer"
    sources = [{
        "metadata": {"filename": "test.pdf"},
        "score": 0.9,
        "text_snippet": "snippet"
    }]
    
    try:
        path = service.generate_evidence_pdf(query, answer, sources, "client_1")
        assert os.path.exists(path)
        assert path.endswith(".pdf")
    except ImportError:
        pytest.skip("fpdf2 not installed")


def test_custom_font_without_italic_uses_regular_style():
    if FPDF is None:
        pytest.skip("fpdf2 not installed")

    with patch("ses.core.reports.os.path.isfile", return_value=True), \
         patch.object(EnterpriseReportPDF, "add_font"):
        pdf = EnterpriseReportPDF(font_path="/tmp/Custom-Regular.ttf")

    assert pdf._font_family == "SESFont"
    assert pdf._has_italic is False

    with patch.object(pdf, "set_x"), \
         patch.object(pdf, "set_font") as set_font, \
         patch.object(pdf, "set_text_color"), \
         patch.object(pdf, "multi_cell"), \
         patch.object(pdf, "ln"):
        pdf.draw_italic_block("evidence")

    set_font.assert_called_once_with("SESFont", "", 8)

def test_generate_usage_report_pdf(tmp_path):
    output_dir = tmp_path / "reports"
    service = ReportService(output_dir=str(output_dir))

    analytics_data = {
        "total_requests": 100,
        "total_errors": 5,
        "total_searches": 60,
        "total_ingestions": 40,
        "average_latency_ms": 150.5,
        "keys_performance": [
            {
                "name": "Test Key",
                "namespace": "test_ns",
                "role": "client",
                "total_calls": 50,
                "avg_latency_ms": 100.0
            }
        ]
    }

    try:
        path = service.generate_usage_report_pdf(analytics_data, "Test Tenant")
        assert os.path.exists(path)
        assert path.endswith(".pdf")
    except ImportError:
        pytest.skip("fpdf2 not installed")

def test_generate_health_report_pdf(tmp_path):
    output_dir = tmp_path / "reports"
    service = ReportService(output_dir=str(output_dir))

    health_data = {
        "status": "healthy",
        "uptime_seconds": 3600,
        "services": {
            "qdrant": {"status": "ok"},
            "redis": {"status": "ok"},
            "ollama": {"status": "ok"}
        }
    }

    try:
        path = service.generate_system_health_pdf(health_data, {}, "Test Tenant")
        assert os.path.exists(path)
        assert path.endswith(".pdf")
    except ImportError:
        pytest.skip("fpdf2 not installed")
