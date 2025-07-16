import requests
import pandas as pd
from tqdm import tqdm

API_URL = "http://127.0.0.1:8000/company/search"
INPUT_SAMPLE_CSV = "CSVs/API-input-sample.csv"

def clean_domain(website_val):
    """Extracts a clean domain from various possible website URL formats."""
    if pd.isna(website_val):
        return None
    s = str(website_val).lower().strip()
    for prefix in ["https://https//", "http://http//", "https://", "http://", "https//", "http//"]:
        s = s.replace(prefix, "")
    s = s.split('/')[0]
    return s if s else None

def test_batch():
    df = pd.read_csv(INPUT_SAMPLE_CSV)
    results = []
    n = len(df)
    for _, row in tqdm(df.iterrows(), total=n, desc="Testing"):
        params = {}
        if 'input name' in row and pd.notna(row['input name']):
            params['name'] = row['input name']
        if 'input phone' in row and pd.notna(row['input phone']):
            params['phone'] = row['input phone']
        if 'input website' in row and pd.notna(row['input website']):
            clean = clean_domain(row['input website'])
            if clean:
                params['domain'] = clean
        if 'input_facebook' in row and pd.notna(row['input_facebook']):
            params['facebook'] = row['input_facebook']

        r = requests.get(API_URL, params=params)
        if r.status_code == 200:
            res = r.json()
            company_name = (
                res.get("company_commercial_name")
                or res.get("company_name")
                or res.get("company_legal_name")
                or res.get("matched_name")
                or res.get("name")
            )
            match_score = res.get("match_score", 0)
        else:
            match_score = 0
            company_name = None
        results.append({
            'input_name': row.get('input name', None),
            'matched_name': company_name,
            'match_score': match_score
        })

    result_df = pd.DataFrame(results)
    print("\n--- BATCH TEST SUMMARY ---")
    print(result_df.head(10))
    print("\nAverage match score:", result_df['match_score'].mean())
    result_df['is_match'] = result_df.apply(
        lambda x: x['matched_name'] and x['input_name'] and str(x['matched_name']).lower()[:5] == str(x['input_name']).lower()[:5], axis=1
    )
    accuracy = result_df['is_match'].mean()
    print("Name-match accuracy (first 5 letters):", round(accuracy*100, 2), "%")
    result_df.to_csv("batch_results.csv", index=False)
    print("Results saved to batch_results.csv")

if __name__ == "__main__":
    test_batch()
