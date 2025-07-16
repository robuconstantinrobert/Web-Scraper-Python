import pytest
from fastapi.testclient import TestClient
from main import (
    app, clean_url, extract_phone_numbers, extract_social_links, extract_address,
    analyze_results, string_similarity, best_match, scrape_site
)
from bs4 import BeautifulSoup

def test_clean_url_variants():
    assert clean_url("example.com") == "https://example.com"
    assert clean_url("http://example.com") == "http://example.com"
    assert clean_url("https://example.com") == "https://example.com"
    assert clean_url(" www.example.com ") == "https://www.example.com"

def test_extract_phone_numbers_html():
    html = "Call us at <a href='tel:+14085551234'>+1 (408) 555-1234</a>"
    soup = BeautifulSoup(html, "html.parser")
    phones = extract_phone_numbers(html, soup)
    assert "+14085551234" in phones or "+14085551234" in "".join(phones)

def test_extract_social_links_html():
    html = '''
        <a href="https://facebook.com/testpage"></a>
        <a href="https://twitter.com/test"></a>
        <a href="https://linkedin.com/in/user"></a>
        <a href="https://instagram.com/test"></a>
    '''
    soup = BeautifulSoup(html, "html.parser")
    socials = extract_social_links(html, soup)
    assert "facebook" in socials and any("facebook.com/testpage" in l for l in socials["facebook"])
    assert "twitter" in socials and any("twitter.com/test" in l for l in socials["twitter"])
    assert "linkedin" in socials and any("linkedin.com/in/user" in l for l in socials["linkedin"])
    assert "instagram" in socials and any("instagram.com/test" in l for l in socials["instagram"])

def test_extract_address_html():
    html = '<footer>123 Main St, Springfield</footer>'
    soup = BeautifulSoup(html, "html.parser")
    addr = extract_address(soup)
    assert "123 Main St" in addr

    html = '<address>456 Elm Street, Somecity</address>'
    soup = BeautifulSoup(html, "html.parser")
    addr = extract_address(soup)
    assert "456 Elm" in addr


def test_analyze_results():
    mock_results = [
        {'status': 'ok', 'phones': ['+14085551234'], 'social_links': {'facebook': ['fb']}, 'address': "addr"},
        {'status': 'fail', 'phones': [], 'social_links': {}, 'address': None},
        {'status': 'ok', 'phones': [], 'social_links': {}, 'address': None},
    ]
    stats = analyze_results(mock_results)
    assert abs(stats['coverage'] - 2/3) < 0.01
    assert abs(stats['phone_fill'] - 1/3) < 0.01
    assert abs(stats['social_fill'] - 1/3) < 0.01
    assert abs(stats['addr_fill'] - 1/3) < 0.01


def test_string_similarity_basic():
    assert string_similarity("abc", "abc") == 1
    assert 0 < string_similarity("abc", "abd") < 1
    assert string_similarity("", "abc") == 0

def test_best_match_exact_and_fuzzy():
    profiles = [
        {"domain": "abc.com", "phones": ["+1"], "company_commercial_name": "Acme", "social_links": {}, "company_legal_name": "Acme Inc."},
        {"domain": "xyz.com", "phones": ["+2"], "company_commercial_name": "Xyz", "social_links": {}, "company_legal_name": "Xyz LLC"}
    ]
    q = {"domain": "abc.com", "name": None, "phone": None, "facebook": None}
    prof, score = best_match(q, profiles)
    assert prof["domain"] == "abc.com" and score == 100.0
    q = {"domain": None, "name": None, "phone": "+2", "facebook": None}
    prof, score = best_match(q, profiles)
    assert prof["domain"] == "xyz.com" and score == 100.0
    q = {"domain": None, "name": "acme", "phone": None, "facebook": None}
    prof, score = best_match(q, profiles)
    assert prof["domain"] == "abc.com" and score < 100.0 and score > 0

@pytest.fixture
def client():
    return TestClient(app)

def test_api_search_by_domain(client):
    app.dependency_overrides = {}
    app.PROFILES = [
        {"domain": "abc.com", "phones": ["+1"], "company_commercial_name": "Acme", "social_links": {}, "company_legal_name": "Acme Inc."}
    ]
    r = client.get("/company/search?domain=abc.com")
    assert r.status_code == 200
    assert r.json().get("domain") == "abc.com"
    assert r.json().get("match_score") == 100.0

def test_api_search_missing_params(client):
    r = client.get("/company/search")
    assert r.status_code == 400

def test_api_search_by_name_fuzzy(client):
    app.PROFILES = [
        {"domain": "abc.com", "phones": ["+1"], "company_commercial_name": "Acme", "social_links": {}, "company_legal_name": "Acme Inc."}
    ]
    r = client.get("/company/search?name=acme")
    assert r.status_code == 200
    data = r.json()
    assert data.get("domain") == "abc.com"
    assert data.get("match_score") > 0

def test_scrape_site_integration(monkeypatch):
    """Test scrape_site returns expected structure for a domain with static content."""
    def fake_requests_get(url, *args, **kwargs):
        class R:
            text = "<html><a href='tel:+14085551234'></a><a href='https://facebook.com/myfb'></a><footer>1 Test Address</footer></html>"
        return R()
    monkeypatch.setattr(requests, "get", fake_requests_get)
    result = scrape_site("abc.com")
    assert result['status'] == 'ok'
    assert "+14085551234" in result['phones']
    assert "facebook" in result['social_links']
    assert "Test Address" in result['address']

def test_scrape_site_failure(monkeypatch):
    """Test scrape_site handles exceptions gracefully."""
    def fake_requests_get(url, *args, **kwargs):
        raise Exception("Failed to connect")
    monkeypatch.setattr(requests, "get", fake_requests_get)
    result = scrape_site("bad.com")
    assert result['status'] == 'fail'
    assert "error" in result

