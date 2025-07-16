import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import phonenumbers
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import time
import json
from fastapi import FastAPI, Query
from typing import Optional
from difflib import SequenceMatcher

SCRAPE_TIMEOUT = 7
MAX_WORKERS = 32
SCRAPE_CHUNK_SIZE = 100000
INPUT_WEBSITES_CSV = 'CSVs/sample-websites.csv'
INPUT_COMPANY_NAMES_CSV = 'CSVs/sample-websites-company-names.csv'
COMPANY_PROFILES_JSON = 'company_profiles.json'

SOCIAL_PATTERNS = {
    'facebook': re.compile(r'(https?://(?:www\.)?facebook\.com/[\w\-/\.]+)', re.I),
    'twitter': re.compile(r'(https?://(?:www\.)?twitter\.com/[\w\-/\.]+)', re.I),
    'linkedin': re.compile(r'(https?://(?:www\.)?linkedin\.com/[\w\-/\.]+)', re.I),
    'instagram': re.compile(r'(https?://(?:www\.)?instagram\.com/[\w\-/\.]+)', re.I),
}

def clean_url(domain):
    d = str(domain).strip()
    if not d.startswith("http://") and not d.startswith("https://"):
        d = "https://" + d
    return d

def extract_phone_numbers(html, soup):
    phone_numbers = set()
    for match in phonenumbers.PhoneNumberMatcher(html, "US"):
        try:
            phone = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164)
            phone_numbers.add(phone)
        except Exception:
            continue
    for a in soup.find_all('a', href=True):
        if a['href'].startswith('tel:'):
            num = a['href'][4:].strip()
            try:
                parsed = phonenumbers.parse(num, "US")
                phone = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                phone_numbers.add(phone)
            except Exception:
                pass
    return list(phone_numbers)

def extract_social_links(html, soup):
    socials = {k: [] for k in SOCIAL_PATTERNS}
    for network, pattern in SOCIAL_PATTERNS.items():
        socials[network].extend(pattern.findall(html))
    for a in soup.find_all('a', href=True):
        href = a['href']
        for network, pattern in SOCIAL_PATTERNS.items():
            if pattern.match(href):
                socials[network].append(href)
    for k in socials:
        socials[k] = list(set(socials[k]))
    return {k: v for k, v in socials.items() if v}

def extract_address(soup):
    footer = soup.find('footer')
    if footer:
        address_text = footer.get_text(separator=' ', strip=True)
        if 15 < len(address_text) < 250:
            return address_text
    addr_tag = soup.find('address')
    if addr_tag:
        text = addr_tag.get_text(separator=' ', strip=True)
        if 10 < len(text) < 250:
            return text
    for tag in soup.find_all(['div', 'span'], class_=re.compile(r'(address|location)', re.I)):
        text = tag.get_text(separator=' ', strip=True)
        if 10 < len(text) < 250:
            return text
    for tag in soup.find_all(['div', 'span'], id=re.compile(r'(address|location)', re.I)):
        text = tag.get_text(separator=' ', strip=True)
        if 10 < len(text) < 250:
            return text
    return None

def scrape_site(domain):
    result = {
        'domain': domain,
        'phones': [],
        'social_links': {},
        'address': None,
        'status': 'fail'
    }
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/90.0.818.56'
    ]
    urls_to_try = []
    clean_domain = domain.replace('http://', '').replace('https://', '').strip('/')
    for base in ['', 'www.']:
        urls_to_try.extend([
            f"https://{base}{clean_domain}",
            f"http://{base}{clean_domain}",
        ])
    last_err = ''
    for test_url in urls_to_try:
        for attempt in range(3):
            headers = {'User-Agent': user_agents[attempt % len(user_agents)]}
            try:
                resp = requests.get(test_url, timeout=SCRAPE_TIMEOUT, headers=headers, allow_redirects=True)
                if not resp.text.strip():
                    continue
                html = resp.text[:SCRAPE_CHUNK_SIZE]
                soup = BeautifulSoup(html, 'html.parser')
                phones = extract_phone_numbers(html, soup)
                socials = extract_social_links(html, soup)
                address = extract_address(soup)
                result.update({
                    'phones': phones,
                    'social_links': socials,
                    'address': address,
                    'status': 'ok'
                })
                return result
            except Exception as e:
                last_err = str(e)
                time.sleep(0.2)
    result['error'] = last_err if last_err else 'unknown'
    return result

def batch_scrape(websites, max_workers=MAX_WORKERS):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(scrape_site, url): url for url in websites}
        for future in tqdm(as_completed(future_to_url), total=len(websites), desc="Scraping"):
            results.append(future.result())
    return results

def analyze_results(results):
    n = len(results)
    coverage = sum(1 for r in results if r['status'] == 'ok') / n
    phone_fill = sum(1 for r in results if r['phones']) / n
    social_fill = sum(1 for r in results if r['social_links']) / n
    addr_fill = sum(1 for r in results if r['address']) / n
    print(f"\n--- ANALYSIS ---")
    print(f"COVERAGE: {coverage:.2%} | PHONES: {phone_fill:.2%} | SOCIALS: {social_fill:.2%} | ADDRESSES: {addr_fill:.2%}")
    return {
        "coverage": coverage,
        "phone_fill": phone_fill,
        "social_fill": social_fill,
        "addr_fill": addr_fill
    }

def prepare_data():
    print("Loading CSVs...")
    websites_df = pd.read_csv(INPUT_WEBSITES_CSV)
    companies_df = pd.read_csv(INPUT_COMPANY_NAMES_CSV)
    websites = None
    for col in ['domain', 'website', 'url']:
        if col in websites_df.columns:
            websites = websites_df[col].dropna().tolist()
            break
    if websites is None:
        websites = websites_df.iloc[:, 0].dropna().tolist()
    print(f"Scraping {len(websites)} websites...")
    domains = [str(u).strip().replace('http://', '').replace('https://', '').strip('/') for u in websites]
    urls = [clean_url(u) for u in domains]
    t0 = time.time()
    scraped = batch_scrape(domains, max_workers=MAX_WORKERS)
    elapsed = time.time() - t0
    print(f"Scraping completed in {elapsed:.1f} seconds.")
    analyze_results(scraped)
    scraped_df = pd.DataFrame(scraped)
    merge_col = 'domain'
    merged_df = companies_df.copy()
    if merge_col not in merged_df.columns:
        merged_df[merge_col] = merged_df.iloc[:, 0]
    if merge_col not in scraped_df.columns:
        scraped_df[merge_col] = scraped_df.iloc[:, 0]
    final = merged_df.merge(scraped_df, on=merge_col, how='left', suffixes=('', '_scraped'))
    for f in ['phones', 'social_links', 'address', 'status', 'error']:
        if f+'_scraped' in final.columns:
            final[f] = final[f+'_scraped']
            final.drop(columns=[f+'_scraped'], inplace=True)
    final.to_json(COMPANY_PROFILES_JSON, orient='records', force_ascii=False)
    print(f"Data merged and saved to {COMPANY_PROFILES_JSON}")

def string_similarity(a, b):
    if not a or not b:
        return 0
    return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()

def best_match(query, profiles):
    best_score = 0
    best_profile = None
    for profile in profiles:
        score = 0
        name_fields = ['company_commercial_name', 'company_legal_name', 'company_all_available_names', 'name', 'company_name']
        for k in name_fields:
            if query.get('name') and k in profile and profile[k]:
                score += 2 * string_similarity(query['name'], profile[k])
        if query.get('domain') and 'domain' in profile and profile['domain']:
            score += 2 * string_similarity(query['domain'], profile['domain'])
        if query.get('phone') and profile.get('phones'):
            try:
                score += max([string_similarity(query['phone'], p) for p in (profile['phones'] or [])] or [0])
            except Exception:
                pass
        if query.get('facebook'):
            social_links = profile.get('social_links', {})
            if not isinstance(social_links, dict):
                social_links = {}
            fb_links = social_links.get('facebook', [])
            if fb_links:
                score += max([string_similarity(query['facebook'], link) for link in fb_links] or [0])
        if score > best_score:
            best_score = score
            best_profile = profile
    return best_profile, best_score

app = FastAPI(title="Company Profile API")

@app.on_event("startup")
def load_profiles():
    global PROFILES
    with open(COMPANY_PROFILES_JSON, 'r', encoding='utf-8') as f:
        PROFILES = json.load(f)

@app.get("/company/search")
def company_search(
    name: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    facebook: Optional[str] = Query(None)
):
    query = {"name": name, "domain": domain, "phone": phone, "facebook": facebook}
    profile, score = best_match(query, PROFILES)
    if profile:
        profile = dict(profile)
        profile['match_score'] = round(score, 3)
    return profile or {"error": "No match found"}

if __name__ == "__main__":
    import os
    if not os.path.exists(COMPANY_PROFILES_JSON):
        prepare_data()
    print("Data ready. To run the API use: uvicorn main:app --reload")