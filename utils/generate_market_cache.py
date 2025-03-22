import json
import os
import time
import requests

ESI_BASE = "https://esi.evetech.net/latest"
CACHE_DIR = "cache"
EMPIRE_REGIONS = {
    "aridia", "derelik", "devoid", "domain", "genesis", "kador", "khanid", "kor-azor", "tash-murkon", "thebleaklands",
    "lonetrek", "thecitadel", "theforge", "essence", "everyshore", "placid", "sinqlaison", "solitude",
    "vergevendor", "metropolis", "heimatar", "moldenheath"
}
CACHE_DURATION = 60 * 30  # 30 Minuten

def get_all_region_ids():
    with open("./cache/universe_sde_cache.json", "r", encoding="utf-8") as f:
        universe_data = json.load(f)
    region_ids = []
    for region_name, region_data in universe_data.items():
        if region_name.lower() in [r.lower() for r in EMPIRE_REGIONS]:
            region_ids.append(region_data["region_id"])
    return region_ids

def get_market_orders(region_id, order_type="all"):
    cache_key = f"{CACHE_DIR}/region_{region_id}_{order_type}.json"
    if os.path.exists(cache_key) and time.time() - os.path.getmtime(cache_key) < CACHE_DURATION:
        with open(cache_key, "r", encoding="utf-8") as f:
            return json.load(f)

    orders = []
    page = 1
    while True:
        url = f"{ESI_BASE}/markets/{region_id}/orders/"
        params = {"datasource": "tranquility", "page": page}
        if order_type != "all":
            params["order_type"] = order_type
        response = requests.get(url, params=params)
        if response.status_code != 200:
            print(f"❌ Fehler beim Laden von Seite {page} für Region {region_id}: {response.status_code}")
            break
        page_data = response.json()
        if not page_data:
            break
        orders.extend(page_data)
        page += 1

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_key, "w", encoding="utf-8") as f:
        json.dump(orders, f)

    return orders

def cache_all_regions(order_type="all"):
    region_ids = get_all_region_ids()
    print(f"🌍 {len(region_ids)} Regionen werden geprüft...")

    for region_id in region_ids:
        cache_key = f"{CACHE_DIR}/region_{region_id}_{order_type}.json"
        needs_refresh = False

        if not os.path.exists(cache_key):
            print(f"📂 Region {region_id}: Kein Cache vorhanden – lade Daten neu.")
            needs_refresh = True
        else:
            age_sec = time.time() - os.path.getmtime(cache_key)
            if age_sec >= CACHE_DURATION:
                print(f"⏳ Region {region_id}: Cache ist {int(age_sec / 60)} Minuten alt – wird neu geladen.")
                needs_refresh = True
            else:
                print(f"✅ Region {region_id}: Cache ist aktuell ({int(age_sec / 60)} Minuten) – wird nicht aktualisiert.")

        if needs_refresh:
            try:
                get_market_orders(region_id, order_type=order_type)
            except Exception as e:
                print(f"⚠️ Fehler beim Aktualisieren der Region {region_id}: {e}")
