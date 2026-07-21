import pytest
from app.agents.evidence_fusion import get_base_name_key
from app.services.sec_edgar_client import sec_client
from app.agents.confidence_scoring import calculate_9_factor_confidence

def test_get_base_name_key():
    assert "microsoft" in get_base_name_key("Microsoft Corporation")
    assert "stripe" in get_base_name_key("Stripe Ltd.")
    assert "google" in get_base_name_key("Google Inc.")

def test_confidence_calculations():
    mock_sub = {
        "name": "Test Subsidiary Ltd",
        "evidences": [{"source_type": "SEC EDGAR Exhibit 21", "extracted_text": "Exhibit 21 Table"}],
        "confidence": 0.95,
        "relationship_type": "Subsidiary"
    }
    score = calculate_9_factor_confidence(mock_sub)
    assert score >= 0.70
    assert score <= 1.00

def test_sec_exhibit21_parser():
    mock_html = """
    <html>
        <body>
            <table>
                <tr>
                    <th>Name of Subsidiary</th>
                    <th>Jurisdiction</th>
                </tr>
                <tr>
                    <td>Microsoft Ireland Operations Limited</td>
                    <td>Ireland</td>
                </tr>
                <tr>
                    <td>Microsoft India Private Limited</td>
                    <td>India</td>
                </tr>
            </table>
        </body>
    </html>
    """
    results = sec_client.parse_exhibit_21_html(mock_html)
    assert len(results) == 2
    assert results[0]["name"] == "Microsoft Ireland Operations Limited"
    assert results[0]["country"] == "Ireland"
    assert results[1]["name"] == "Microsoft India Private Limited"
    assert results[1]["country"] == "India"
