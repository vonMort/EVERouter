import json
from utils.generate_market_cache import cache_all_regions, get_market_orders
from utils.routing import get_route_between

CACHE_DIR = "cache"

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


def analyze_route_trade_opportunities(route, universe_data, item_data, station_data, cargo_capacity, budget):
    from utils.generate_market_cache import get_market_orders
    opportunities = []
    region_cache = {}

    def get_orders_for_system(system_name):
        region_id, system_id = get_region_id_by_system_name(universe_data, system_name)
        if not region_id or not system_id:
            return [], system_id
        if region_id not in region_cache:
            region_cache[region_id] = get_market_orders(region_id, order_type="all")
        return region_cache[region_id], system_id

    for i in range(len(route) - 1):
        source_sys = route[i]
        source_orders_raw, source_sys_id = get_orders_for_system(source_sys)
        for j in range(i + 1, len(route)):
            dest_sys = route[j]
            dest_orders_raw, dest_sys_id = get_orders_for_system(dest_sys)

            market = build_market_data(source_orders_raw, dest_orders_raw, source_sys_id, dest_sys_id, station_data)

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

                si = 0
                bi = 0

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

                opportunities.append({
                    "from": source_sys,
                    "to": dest_sys,
                    "item": item_data["by_id"][item_id]["name"],
                    "units": total_units,
                    "volume": volume_per_unit,
                    "total_profit": total_profit,
                    "unit_profit": total_profit / total_units,
                    "profit_per_m3": total_profit / (volume_per_unit * total_units)
                })

    return sorted(opportunities, key=lambda x: x["total_profit"], reverse=True)


def main():
    print("Willkommen zum EVE Handelsrouten-Planer!\n")

    print("🔄 Starte initiales Markt-Caching aller Regionen...")
    cache_all_regions(order_type="all")

    universe_data = load_cache("cache/universe_sde_cache.json")
    item_data = load_cache("cache/item_cache.json")
    station_data = load_cache("cache/station_cache.json")

    source_system = input("🛨️  In welchem System befindest du dich aktuell? ").strip()
    dest_system = input("🌟 Welches System ist dein Ziel? ").strip()

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

    print("\n🧭 Berechne beste Route zwischen den Systemen...")
    route = get_route_between("cache/universe_sde_cache.json", source_system, dest_system, only_highsec=True)

    if not route:
        print("❌ Keine gültige Route gefunden.")
        return

    print(f"📌 Gefundene Route ({len(route) - 1} Sprünge): " + " → ".join(route))

    start_system = route[0]
    end_system = route[-1]

    source_region, source_system_id = get_region_id_by_system_name(universe_data, start_system)
    dest_region, dest_system_id = get_region_id_by_system_name(universe_data, end_system)

    if source_region is None or dest_region is None:
        print("❌ Konnte Region zu einem der Systeme nicht ermitteln.")
        return

    print("\n🔄 Lade Marktorders aus dem Cache...")
    source_orders = get_market_orders(source_region, order_type="all")
    dest_orders = get_market_orders(dest_region, order_type="all")
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

    print("\n🔍 Berechne profitabelste Multi-Hop-Handelsoptionen entlang der Route...")
    opportunities = analyze_route_trade_opportunities(route, universe_data, item_data, station_data, cargo_capacity,
                                                      budget)

    print("\n💼 Top 10 Handelsoptionen entlang der Route:")
    for op in opportunities[:10]:
        print(
            f"{op['item']:35} | {op['from']:10} → {op['to']:10} | Gewinn: {format_number(op['total_profit'])} ISK | Menge: {op['units']} | Volumen: {op['volume']} m³")


if __name__ == "__main__":
    main()
