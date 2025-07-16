# Company Profile Matching API

## Overview

The **Company Profile Matching API** is a scalable pipeline and RESTful service for extracting, analyzing, and searching company profile data from a predefined list of websites. It automates web scraping of phone numbers, social links, and addresses, merges the results with reference datasets, evaluates extraction quality, and exposes a fast API for fuzzy company profile matching.

## Tech Stack

* **Language & Frameworks:** Python, FastAPI
* **Web Scraping:** BeautifulSoup, Requests, ThreadPoolExecutor, tqdm
* **Data Processing:** Pandas, phonenumbers
* **Utilities:** User-agent rotation, E.164 phone normalization

---

## Features

1. **Parallel Web Scraping**

   * Extracts phone numbers (both visible and `<a href="tel:">` links), social media links (Facebook, Twitter, LinkedIn, Instagram), and postal addresses from hundreds of websites in parallel.
   * Configurable worker pool (default 32+ threads) and robust fallback strategies.

2. **Data Analysis & Quality Metrics**

   * Reports *coverage* (sites successfully crawled) and *fill rates* (% of phones, socials, addresses found).
   * Example summary:

   ```
   COVERAGE: 73% | PHONES: 40% | SOCIALS: 31% | ADDRESSES: 14%
   ```

3. **Unified JSON Database**

   * Merges scraped data with reference metadata (company names, domains) into a single `company_profiles.json` for fast lookup.

4. **Fuzzy Search REST API**

   * Endpoint: `GET /company/search`
   * Query parameters: `name`, `domain`, `phone`, `facebook`
   * Returns the best-matching profile with a similarity score based on weighted sequence matching.

5. **Batch Testing & Accuracy Reporting**

   * `test_batch.py` evaluates the API against a sample CSV, calculates average match scores, first-5-letter name-match accuracy, and exports results to `batch_results.csv`.

---

## Directory Structure

```
├── main.py                  # Pipeline: scrape, analyze, merge, launch API
├── test_batch.py            # Batch testing script for match accuracy
├── CSVs/
│   ├── sample-websites.csv                # List of websites to crawl
│   ├── sample-websites-company-names.csv  # Reference company metadata
│   └── API-input-sample.csv               # Sample inputs for batch tests
├── company_profiles.json    # Auto-generated unified data output
└── README.md                # This file
```

---

## Getting Started

### 1. Setup

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/company-profile-matching-api.git
   cd company-profile-matching-api
   ```
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   > **requirements.txt** should include: `fastapi`, `uvicorn`, `requests`, `beautifulsoup4`, `pandas`, `tqdm`, `phonenumbers`

### 2. Run Data Extraction & Analysis

```bash
python main.py
```

* Crawls websites, analyzes coverage, merges with reference CSVs, and outputs `company_profiles.json`.

### 3. Start the API Server

```bash
uvicorn main:app --reload
```

* If `company_profiles.json` is missing, `main.py` will generate it at startup.

### 4. Querying the API

**Example:**

```http
GET http://127.0.0.1:8000/company/search?name=Acorn%20Law%20P.C.&domain=acornlawpc.com
```

**Response:**

```json
{
  "domain": "acornlawpc.com",
  "company_commercial_name": "Acorn Law P.C.",
  "phones": ["+15551234567"],
  "social_links": { "facebook": ["https://facebook.com/acornlaw"] },
  "address": "123 Acorn St, City, State",
  "match_score": 7.04
}
```

### 5. Batch Evaluation

```bash
python test_batch.py
```

* Processes `API-input-sample.csv`, computes accuracy metrics, and writes `batch_results.csv`.

---

## How It Works

1. **Scraping Module**: Uses multi-threading to fetch HTML, extract data via regex and HTML parsing.
2. **Normalization**: Standardizes phone numbers to E.164, cleans domains, and normalizes social URLs.
3. **Merging**: Joins scraped results with reference metadata by domain.
4. **Fuzzy Matching**: Applies sequence similarity on names, domains, phones, and social links to compute a final score.
5. **Reporting**: Generates coverage/fill-rate metrics and batch-test accuracy for transparency.

---

## Scaling & Customization

* **Performance**: Handles \~1000 sites in under 10 minutes on modern hardware.
* **Extensibility**: Easily integrate Elasticsearch, a relational database, or other similarity libraries (e.g., `fuzzywuzzy`, Jaccard).
* **Configuration**: Tweak timeouts, user-agent lists, worker counts, and extraction patterns via `main.py` parameters.

---

## Contributing

Contributions, issues, and feature requests are welcome! Feel free to:

* Submit a PR to improve parsing logic.
* Add more social platforms or data fields.
* Integrate alternative matching algorithms.

---

## License

[MIT](LICENSE)

