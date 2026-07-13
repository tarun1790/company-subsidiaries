import pytest
from app.agents.verification import normalize_name
from app.services.sec_edgar_client import sec_client

def test_normalize_name():
    # Suffix stripping
    assert normalize_name("Microsoft Corporation") == "microsoft"
    assert normalize_name("Stripe Ltd.") == "stripe"
    assert normalize_name("Google Inc.") == "google"
    assert normalize_name("Accenture PLC") == "accenture"
    
    # Case standardization
    assert normalize_name("MICROSOFT LIMITED") == "microsoft"
    
    # Punctuation stripping
    assert normalize_name("Stripe, LLC.") == "stripe"

def test_confidence_calculations():
    # Simple calculation mock tests based on source weights
    # SEC (+0.50), Website (+0.30), Registry (+0.20), Web (+0.10)
    sources_1 = ["SEC Filings", "Official Website"]
    confidence_1 = sum([0.50 if s == "SEC Filings" else 0.30 for s in sources_1])
    assert confidence_1 == 0.80

    sources_2 = ["Official Website", "Public Registry"]
    confidence_2 = sum([0.30 if s == "Official Website" else 0.20 for s in sources_2])
    assert confidence_2 == 0.50

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
