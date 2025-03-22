import json
import heapq
import logging

ONLY_HIGHSEC = True  # Sicherheitsfilter (True = nur 0.5+ Systeme)

# Logging-Konfiguration
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
logger = logging.getLogger("routing")

def build_graph(universe_data):
    graph = {}
    security = {}
    name_to_id = {}
    id_to_name = {}
    stargate_to_system = {}  # stargate_id -> system_id
    stargate_links = {}      # stargate_id -> destination_stargate_id

    logger.info("🔧 Baue Graph aus Universe-Daten...")

    # 1. Systeme und Stargates sammeln
    for region in universe_data.values():
        for constellation in region["constellations"].values():
            for sys_name, sys_data in constellation["systems"].items():
                sys_id = sys_data["solarSystemID"]
                name_lc = sys_name.lower()

                name_to_id[name_lc] = sys_id
                id_to_name[sys_id] = sys_name
                security[sys_id] = sys_data.get("security", 0.0)
                graph.setdefault(sys_id, set())

                stargates = sys_data.get("stargates", {})
                if isinstance(stargates, dict):
                    for gate_id, gate_data in stargates.items():
                        stargate_to_system[int(gate_id)] = sys_id
                        destination_id = gate_data.get("destination")
                        if destination_id:
                            stargate_links[int(gate_id)] = int(destination_id)
                elif isinstance(stargates, list):
                    logger.warning(f"⚠️ Stargates für System {sys_name} liegen als Liste vor, erwartet war ein Dict.")

    logger.info(f"✅ {len(name_to_id)} Systeme erfasst.")
    logger.info("🔗 Baue Stargate-Verbindungen auf Systemebene...")

    count_links = 0
    for from_gate, to_gate in stargate_links.items():
        from_system = stargate_to_system.get(from_gate)
        to_system = stargate_to_system.get(to_gate)
        if from_system and to_system:
            graph[from_system].add(to_system)
            graph[to_system].add(from_system)
            count_links += 1

    logger.info(f"🔗 {count_links} System-Verbindungen gesetzt über Stargates.")
    return graph, security, name_to_id, id_to_name


def find_shortest_path(universe_data, start_name, end_name, only_highsec=True):
    logger.info(f"🚀 Suche Route von '{start_name}' nach '{end_name}' (nur Highsec: {only_highsec})")

    graph, security, name_to_id, id_to_name = build_graph(universe_data)

    start_id = name_to_id.get(start_name.lower())
    end_id = name_to_id.get(end_name.lower())

    if start_id is None:
        logger.error(f"❌ Startsystem '{start_name}' nicht gefunden.")
        return []
    if end_id is None:
        logger.error(f"❌ Zielsystem '{end_name}' nicht gefunden.")
        return []

    visited = set()
    heap = [(0, start_id, [])]  # (cost, current_node, path)

    while heap:
        cost, current, path = heapq.heappop(heap)

        if current in visited:
            continue
        visited.add(current)

        path = path + [current]

        if current == end_id:
            logger.info(f"✅ Route gefunden mit {len(path)-1} Sprüngen.")
            return [id_to_name.get(pid, str(pid)) for pid in path]

        for neighbor in graph.get(current, []):
            if neighbor in visited:
                continue
            sec = security.get(neighbor, 0.0)
            if only_highsec and sec < 0.5:
                logger.debug(f"⛔ System {id_to_name.get(neighbor, neighbor)} hat Sicherheitsstatus {sec:.1f} < 0.5 – übersprungen")
                continue
            heapq.heappush(heap, (cost + 1, neighbor, path))

    logger.warning("⚠️ Keine Route gefunden.")
    return []


# Beispielnutzung (lokal):
if __name__ == "__main__":
    try:
        with open("../cache/universe_sde_cache.json", "r", encoding="utf-8") as f:
            universe = json.load(f)

        route = find_shortest_path(universe, "Nakri", "Amarr", only_highsec=True)
        if route:
            print("Gefundene Route:", " → ".join(route))
        else:
            print("Keine Route gefunden.")
    except FileNotFoundError as e:
        logger.error(f"Datei nicht gefunden: {e}")
    except Exception as e:
        logger.exception(f"Unerwarteter Fehler: {e}")