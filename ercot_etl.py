import requests
import json
import zipfile
import io
import pandas as pd
from datetime import datetime, timedelta

with open('auth_response.json', 'r') as f:
    data = json.load(f)
    access_token = data['access_token']

with open('ercot_credentials.json', 'r') as f:
    credentials = json.load(f)
    SUBSCRIPTION_KEY = credentials['ERCOT_API_KEY']

PRODUCTS_URL = "https://api.ercot.com/api/public-reports"
HEADERS = {"Authorization": "Bearer " + access_token, "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY}




# ============ CONFIGURATION =============
API_BASE = "https://api.ercot.com/api/public-reports"

# EMIL product IDs
LOAD_EMIL = "NP6-346-CD"
PRICE_EMIL = "NP6-785-ER"

# region / zone to extract
ZONE = "LZ_HOUSTON"  # or any Load Zone / Hub

# ============ FUNCTIONS =============

def list_reports(emil_id):
    """List report artifacts for a given EMIL product."""
    resp = requests.get(f"{API_BASE}/{emil_id}", headers=HEADERS)
    resp.raise_for_status()
    jr = resp.json()
    # The artifacts are under "_embedded" → "reports" or similar
    return jr.get("_embedded", {}).get("artifacts", [])

def download_artifact(artifact_url):  
    """Download artifact by URL (CSV, zip, etc.) and return as bytes."""
    resp = requests.get(artifact_url, headers=HEADERS)
    resp.raise_for_status()
    return resp.content

def parse_load(data_bytes):
    """Given bytes (CSV or zipped CSV) from Actual System Load by Forecast Zone, return DataFrame."""
    try:
        # If zip
        z = zipfile.ZipFile(io.BytesIO(data_bytes))
        # assume one file inside
        file_list = z.namelist()
        # find the CSV in zip
        csv_name = [fn for fn in file_list if fn.lower().endswith(".csv")][0]
        with z.open(csv_name) as f:
            df = pd.read_csv(f)
    except zipfile.BadZipFile:
        # Not zipped, assume raw CSV
        df = pd.read_csv(io.BytesIO(data_bytes))
    
    # parse timestamps, filter zone
    # assumes there is a column like "ForecastZone", "HourEnding", "Interval", etc.
    # and a column "Value" or "ActualLoad"
    
    
    # convert hour_ending to datetime
    df['timestamp'] = pd.to_datetime(df['HourEnding'])
    # maybe adjust timezone
    # filter for the zone
    df_zone = df[['timestamp','HOUSTON']]
    print(df_zone.head())
    return df_zone

def parse_price(data_bytes):
    """Given bytes from RTM Load Zone & Hub Prices, return DataFrame for a given settlement point."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data_bytes))
        file_list = z.namelist()
        excel_name = [fn for fn in file_list if fn.lower().endswith((".xlsx", ".xls"))][0]
        with z.open(excel_name) as f:
            df = pd.read_excel(f)
    except zipfile.BadZipFile:
        df = pd.read_excel(io.BytesIO(data_bytes))
    
    # rename columns
    # likely columns e.g. SettlementPointName, SettlementPointType, DeliveryDate, DeliveryHour, Price
    df = df.rename(columns={
        'Settlement Point Name': 'settlement_point',
        'Delivery Date': 'date',
        'Delivery Hour': 'hour',
        'RTM Price': 'rtm_price'
    })
    # build timestamp
    df['timestamp'] = pd.to_datetime(df['date']) + pd.to_timedelta(df['hour'] - 1, unit='h')
    # filter for the zone
    df_zone = df[df['settlement_point'] == ZONE]
    return df_zone[['timestamp', 'rtm_price']]

# ============ MAIN =============

def fetch_load(zone=ZONE, target_date=None):
    if target_date is None:
        target_date = datetime.now().date() - timedelta(days=1)  # previous day
    # list artifacts
    arts = list_reports(LOAD_EMIL)
    # find artifact for that date
    # artifacts may have naming patterns or date columns
    # for simplicity, pick the one matching date in name or metadata
    # This is pseudocode: implement matching logic
    art = None
    for a in arts:
        # suppose artifact has "artifactName" or "displayName" containing the date
        name = a.get('displayName', '') or a.get('name', '')
        if target_date.strftime("%Y%m%d") in name:
            art = a
            break
    if art is None:
        raise ValueError(f"No load artifact found for {target_date}")
    content = download_artifact(art['_links']['endpoint']['href'])
    return parse_load(content)

def fetch_price(zone=ZONE, start_year=2024):
    """Fetch price history for the given zone (maybe multiple years)."""
    arts = list_reports(PRICE_EMIL)
    # filter artifacts by year
    filtered = []
    for a in arts:
        name = a.get('displayName', '') or a.get('name', '')
        if str(start_year) in name:
            filtered.append(a)
    # download all matching artifacts and concatenate
    df_list = []
    for a in filtered:
        content = download_artifact(a['_links']['endpoint']['href'])
        df_zone = parse_price(content)
        df_list.append(df_zone)
    if not df_list:
        raise ValueError(f"No price artifacts found for year {start_year}")
    df_all = pd.concat(df_list).drop_duplicates().sort_values('timestamp')
    return df_all

if __name__ == "__main__":
    # example
    df_load = fetch_load(zone="ForecastZone1", target_date=datetime(2025,9,1).date())
    df_price = fetch_price(zone="LZ_HOUSTON", start_year=2025)
    # align (inner join on timestamp)
    df = pd.merge(df_load, df_price, on='timestamp', how='inner')
    print(df.head())
