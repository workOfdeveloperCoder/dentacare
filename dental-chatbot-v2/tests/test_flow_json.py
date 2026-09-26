from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.flow_schema import validate_flow
from app.plugins import load_plugins


FLOW_DIR = Path(__file__).resolve().parents[1] / "flow"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS | {message}")


def load_flow(name: str) -> dict:
    path = FLOW_DIR / name
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def assert_pathways(flow: dict) -> None:
    nodes = {node["key"]: node for node in flow["nodes"]}
    start = flow["start_node"]
    check(start in nodes, f"{flow['flow_key']} start_node exists")

    reachable = set()
    stack = [start]

    while stack:
        key = stack.pop()

        if key in reachable:
            continue

        reachable.add(key)
        node = nodes[key]

        if node.get("next"):
            stack.append(node["next"])

        for option in node.get("options", []):
            if option.get("next"):
                stack.append(option["next"])

        on_input = node.get("on_input") or {}
        if on_input.get("results_node"):
            stack.append(on_input["results_node"])

        on_select = node.get("on_select") or {}
        if on_select.get("details_node"):
            stack.append(on_select["details_node"])

    isolated = set(nodes) - reachable
    check(
        not isolated,
        f"{flow['flow_key']} has no unreachable nodes: {sorted(isolated) or 'none'}",
    )


def main():
    load_plugins()

    for filename in ("dental_reception.json", "oil_company.json"):
        flow = load_flow(filename)
        validate_flow(flow)
        assert_pathways(flow)
        check(
            "branding" in flow,
            f"{flow['flow_key']} includes widget branding",
        )
        print(f"OK   | {filename} ({len(flow['nodes'])} steps)")

    print()
    print("FLOW JSON TEST PASSED")


if __name__ == "__main__":
    main()
