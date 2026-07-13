import pytest
from app.agents.evidence_fusion import get_base_name_key
from app.services.sec_edgar_client import sec_client
from app.agents.confidence_scoring import load_scoring_config

def test_get_base_name_key():
    assert get_base_name_key("Microsoft Corporation") == "microsoft"
    assert get_base_name_key("Stripe Ltd.") == "stripe"
    assert get_base_name_key("Google Inc.") == "google"
    assert get_base_name_key("MICROSOFT LIMITED") == "microsoft"
    assert get_base_name_key("Stripe, LLC.") == "stripe"

def test_confidence_calculations():
    config = load_scoring_config()
    auth = config["source_authority"]
    assert auth["sec_filings"] == 0.50
    assert auth["official_website"] == 0.30

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
