import json
import requests
import os
import time

ESI_BASE = "https://esi.evetech.net/latest"
CACHE_DIR = "cache"
CACHE_DURATION = 60 * 30  # 30 Minuten

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def get_region_id_by_system_name(universe_data, system_name):
    system_name = system_name.strip().lower()
    for region_name, region_data in universe_data.items():
        for constellation_name, const_data in region_data["constellations"].items():
            for sys_name, sys_data in const_data["systems"].items():
                if sys_name.lower() == system_name:
                    region_id = region_data.get("region_id")
                    print(f"✅ System '{sys_name}' gefunden in Konstellation '{constellation_name}' der Region '{region_name}' → SystemID: {sys_data.get('solarSystemID')} → RegionID: {region_id}")
                    return region_id, sys_data.get("solarSystemID")
    print(f"❌ System '{system_name}' nicht gefunden.")
    return None, None

def load_cache(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def format_number(number):
    return f"{number:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

def get_market_orders(region_id, order_type="all"):
    cache_key = f"{CACHE_DIR}/region_{region_id}_{order_type}.json"
    if os.path.exists(cache_key):
        if time.time() - os.path.getmtime(cache_key) < CACHE_DURATION:
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
            break
        page_data = response.json()
        if not page_data:
            break
        orders.extend(page_data)
        page += 1

    with open(cache_key, "w", encoding="utf-8") as f:
        json.dump(orders, f)

    return orders

def build_market_data(source_orders, dest_orders, source_system_id, dest_system_id, station_data):
    market = {}

    def is_in_system(order, system_id):
        station_id = str(order.get("location_id"))
        if station_id in station_data.get("by_id", {}):
            return station_data["by_id"][station_id]["solarSystemID"] == system_id
        return False

    for order in source_orders:
        if not order["is_buy_order"] and is_in_system(order, source_system_id):
            item_id = str(order["type_id"])
            if item_id not in market:
                market[item_id] = {"sell_orders": []}
            market[item_id]["sell_orders"].append(order)

    for order in dest_orders:
        if order["is_buy_order"] and is_in_system(order, dest_system_id):
            item_id = str(order["type_id"])
            if item_id not in market:
                market[item_id] = {"buy_orders": []}
            if "buy_orders" not in market[item_id]:
                market[item_id]["buy_orders"] = []
            market[item_id]["buy_orders"].append(order)

    return market

def main():
    print("Willkommen zum EVE Handelsrouten-Planer!\n")

    universe_data = load_cache("cache/universe_sde_cache.json")
    item_data = load_cache("cache/item_cache.json")
    station_data = load_cache("cache/station_cache.json")

    source_system = input("🛰️  In welchem System befindest du dich aktuell? ").strip()
    dest_system = input("🎯 Welches System ist dein Ziel? ").strip()

    try:
        cargo_capacity = float(input("📦 Wie viel m³ Frachtvolumen steht dir zur Verfügung? (Standard: 10000) ") or 10000)
    except ValueError:
        cargo_capacity = 10000

    try:
        budget = float(input("💰 Wie viel ISK Budget hast du für den Einkauf? (Standard: 100000000) ") or 100000000)
    except ValueError:
        budget = 100000000

    print("\n✅ Eingaben erfolgreich erfasst!")
    print(f"- Ausgangssystem: {source_system}")
    print(f"- Zielsystem:     {dest_system}")
    print(f"- Frachtvolumen:  {format_number(cargo_capacity)} m³")
    print(f"- Budget:         {format_number(budget)} ISK")

    source_region, source_system_id = get_region_id_by_system_name(universe_data, source_system)
    dest_region, dest_system_id = get_region_id_by_system_name(universe_data, dest_system)

    if source_region is None or dest_region is None:
        print("❌ Konnte Region zu einem der Systeme nicht ermitteln.")
        return

    print("\n🔄 Lade Marktorders vom ESI...")
    source_orders = get_market_orders(source_region, order_type="sell")
    dest_orders = get_market_orders(dest_region, order_type="buy")
    print(f"✅ {len(source_orders)} Verkaufsorders im Quellgebiet, {len(dest_orders)} Kauforders im Zielgebiet geladen.")

    market = build_market_data(source_orders, dest_orders, source_system_id, dest_system_id, station_data)

    profitable = []
    for item_id, data in market.items():
        if item_id not in item_data["by_id"]:
            continue

        sell_orders = sorted(data.get("sell_orders", []), key=lambda x: x["price"])
        buy_orders = sorted(data.get("buy_orders", []), key=lambda x: -x["price"])

        if not sell_orders or not buy_orders:
            continue

        volume_per_unit = item_data["by_id"][item_id]["volume"]
        available_budget = budget
        available_volume = cargo_capacity

        total_profit = 0
        total_units = 0

        si = 0  # sell order index
        bi = 0  # buy order index

        while si < len(sell_orders) and bi < len(buy_orders):
            sell = sell_orders[si]
            buy = buy_orders[bi]

            if sell["price"] >= buy["price"]:
                break

            unit_profit = buy["price"] - sell["price"]
            max_units = min(
                sell["volume_remain"],
                buy["volume_remain"],
                available_budget // sell["price"],
                available_volume // volume_per_unit
            )

            if max_units <= 0:
                break

            profit = max_units * unit_profit

            total_units += max_units
            total_profit += profit
            available_budget -= max_units * sell["price"]
            available_volume -= max_units * volume_per_unit

            sell_orders[si]["volume_remain"] -= max_units
            buy_orders[bi]["volume_remain"] -= max_units

            if sell_orders[si]["volume_remain"] <= 0:
                si += 1
            if buy_orders[bi]["volume_remain"] <= 0:
                bi += 1

        if total_units == 0:
            continue

        profitable.append({
            "item_id": item_id,
            "name": item_data["by_id"][item_id]["name"],
            "unit_profit": total_profit / total_units,
            "volume": volume_per_unit,
            "units": total_units,
            "total_profit": total_profit,
            "profit_per_m3": total_profit / (volume_per_unit * total_units)
        })

    profitable_sorted = sorted(profitable, key=lambda x: x["total_profit"], reverse=True)

    print("\n💡 Top 10 profitabelste Items (nach Gesamtgewinn, unter Berücksichtigung von Volumen, Angebot und Budget):")
    for item in profitable_sorted[:10]:
        print(f"{item['name']:35} | Menge: {int(item['units']):5d} | Gewinn: {format_number(item['total_profit'])} ISK | Gewinn/Einheit: {format_number(item['unit_profit'])} ISK | Volumen: {item['volume']} m³")

if __name__ == "__main__":
    main()
