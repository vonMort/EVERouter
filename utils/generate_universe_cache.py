import os
import yaml
import json
from tqdm import tqdm

SDE_BASE_PATH = "../eve_metadata/sde/universe/eve"

stargate_to_system = {}
stargate_links = {}

def get_solarsystem_yaml_paths(base_path):
    system_paths = []
    for region_name in os.listdir(base_path):
        region_path = os.path.join(base_path, region_name)
        if not os.path.isdir(region_path):
            continue

        for constellation_name in os.listdir(region_path):
            const_path = os.path.join(region_path, constellation_name)
            if not os.path.isdir(const_path):
                continue

            for system_name in os.listdir(const_path):
                system_path = os.path.join(const_path, system_name)
                yaml_file = os.path.join(system_path, "solarsystem.yaml")
                if os.path.isfile(yaml_file):
                    system_paths.append((region_name, constellation_name, system_name, yaml_file))
    return system_paths


def parse_yaml_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def parse_solarsystem_yaml(yaml_path, current_system_id):
    data = parse_yaml_file(yaml_path)

    stargates_raw = data.get("stargates", {})

    if isinstance(stargates_raw, dict):
        for gate_id_str, gate_data in stargates_raw.items():
            gate_id = int(gate_id_str)
            stargate_to_system[gate_id] = current_system_id
            if "destination" in gate_data:
                stargate_links[gate_id] = gate_data["destination"]

    result = {
        "solarSystemID": data.get("solarSystemID"),
        "radius": data.get("radius"),
        "security": data.get("security"),
        "securityClass": data.get("securityClass"),
        "sunTypeID": data.get("sunTypeID"),
        "planets": list(data.get("planets", {}).keys()),
        "stargates": list(stargates_raw.keys()),
        "stations": [],
        "planet_details": {},
        "connections": []  # wird später gefüllt
    }

    for planet_id, planet in data.get("planets", {}).items():
        moons = list(planet.get("moons", {}).keys()) if "moons" in planet else []
        result["planet_details"][planet_id] = {
            "moons": moons,
            "typeID": planet.get("typeID")
        }

    for planet in data.get("planets", {}).values():
        if "npcStations" in planet:
            result["stations"].extend(list(planet["npcStations"].keys()))
        for moon in planet.get("moons", {}).values():
            if "npcStations" in moon:
                result["stations"].extend(list(moon["npcStations"].keys()))

    return result


def build_sde_universe_cache():
    universe = {}

    print("🔍 Durchsuche SDE-Verzeichnis...")
    paths = get_solarsystem_yaml_paths(SDE_BASE_PATH)
    print(f"📁 {len(paths)} solarsystem.yaml-Dateien gefunden")

    region_cache = {}
    constellation_cache = {}

    for region, constellation, system, yaml_path in tqdm(paths, desc="📦 Verarbeite Systeme"):
        region_key = region.lower()
        constellation_key = constellation.lower()
        system_key = system.lower()

        region_yaml_path = os.path.join(SDE_BASE_PATH, region, "region.yaml")
        const_yaml_path = os.path.join(SDE_BASE_PATH, region, constellation, "constellation.yaml")

        if region_key not in region_cache:
            region_cache[region_key] = parse_yaml_file(region_yaml_path)
        if constellation_key not in constellation_cache:
            constellation_cache[constellation_key] = parse_yaml_file(const_yaml_path)

        region_yaml = region_cache[region_key]
        constellation_yaml = constellation_cache[constellation_key]

        if region_key not in universe:
            universe[region_key] = {
                "region_id": region_yaml.get("regionID"),
                "region_name_id": region_yaml.get("regionNameID"),
                "description": region_yaml.get("description"),
                "constellations": {}
            }

        if constellation_key not in universe[region_key]["constellations"]:
            universe[region_key]["constellations"][constellation_key] = {
                "constellation_id": constellation_yaml.get("constellationID"),
                "constellation_name_id": constellation_yaml.get("constellationNameID"),
                "systems": {}
            }

        system_data = parse_yaml_file(yaml_path)
        sys_id = system_data.get("solarSystemID")
        parsed_system = parse_solarsystem_yaml(yaml_path, sys_id)

        universe[region_key]["constellations"][constellation_key]["systems"][system_key] = parsed_system

    print("🔗 Setze Verbindungen zwischen Systemen...")
    added_links = 0
    for from_gate_id, dest in stargate_links.items():
        from_sys = stargate_to_system.get(from_gate_id)
        to_gate_id = dest if isinstance(dest, int) else dest.get("stargateID")
        to_sys = stargate_to_system.get(to_gate_id)

        if from_sys and to_sys and from_sys != to_sys:
            for region in universe.values():
                for constellation in region["constellations"].values():
                    for system in constellation["systems"].values():
                        if system["solarSystemID"] == from_sys:
                            if to_sys not in system["connections"]:
                                system["connections"].append(to_sys)
                        elif system["solarSystemID"] == to_sys:
                            if from_sys not in system["connections"]:
                                system["connections"].append(from_sys)
            added_links += 1

    print(f"✅ {added_links} Verbindungen zwischen Systemen hinzugefügt.")
    print("✅ Verarbeitung abgeschlossen.")
    return universe


def save_to_json(data, filepath="../cache/universe_sde_cache.json"):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Universum gespeichert in {filepath}")


if __name__ == "__main__":
    print("🚀 Starte Verarbeitung des SDE...")
    universe_data = build_sde_universe_cache()
    save_to_json(universe_data)
    print("🎉 Alle Daten erfolgreich verarbeitet und gespeichert!")
