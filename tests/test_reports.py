import os
import pytest
from ses.core.reports import ReportService

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
