from app.plugins import (
    ACTIONS,
    INPUT_HANDLERS,
    OPTION_SOURCES,
    SELECT_HANDLERS,
    load_plugins,
)

load_plugins()


FLOW_CONFIG_KEYS = (
    "branding",
    "navigation",
    "summary_fields",
    "order_prefix",
)

NODE_CORE_KEYS = {
    "key",
    "type",
    "message",
    "input_key",
    "validation_type",
    "next",
    "options",
}


def flow_config(flow: dict) -> dict:
    return {
        key: flow[key]
        for key in FLOW_CONFIG_KEYS
        if key in flow
    }


def node_config(node: dict) -> dict:
    return {
        key: value
        for key, value in node.items()
        if key not in NODE_CORE_KEYS
    }


def validate_flow(flow: dict) -> None:
    required = [
        "flow_key",
        "name",
        "nodes",
        "start_node",
    ]

    for field in required:
        if field not in flow:
            raise ValueError(f"Missing required field: {field}")

    if not isinstance(flow["nodes"], list):
        raise ValueError("'nodes' must be an array")

    node_keys = set()

    for node in flow["nodes"]:
        key = node.get("key")

        if not key:
            raise ValueError("Node is missing 'key'")

        if key in node_keys:
            raise ValueError(f"Duplicate node key: {key}")

        node_keys.add(key)

        if not node.get("type"):
            raise ValueError(f"Node '{key}' is missing 'type'")

        if not node.get("message"):
            raise ValueError(f"Node '{key}' is missing 'message'")

        options = node.get("options", [])

        if not isinstance(options, list):
            raise ValueError(f"Node '{key}': options must be an array")

    if flow["start_node"] not in node_keys:
        raise ValueError(
            f"start_node '{flow['start_node']}' does not exist"
        )

    navigation = flow.get("navigation") or {}
    main_menu_node = navigation.get("main_menu_node")

    if main_menu_node and main_menu_node not in node_keys:
        raise ValueError(
            f"navigation.main_menu_node '{main_menu_node}' does not exist"
        )

    referenced = []

    for node in flow["nodes"]:
        if node.get("next"):
            referenced.append((node["key"], node["next"]))

        for option in node.get("options", []):
            if option.get("next"):
                referenced.append(
                    (f"{node['key']}.{option.get('key')}", option["next"])
                )

        on_input = node.get("on_input") or {}

        if on_input.get("results_node"):
            referenced.append(
                (f"{node['key']}.on_input.results_node", on_input["results_node"])
            )

        on_select = node.get("on_select") or {}

        if on_select.get("details_node"):
            referenced.append(
                (f"{node['key']}.on_select.details_node", on_select["details_node"])
            )

        for extra in on_select.get("extra_options", []):
            if extra.get("next"):
                referenced.append(
                    (
                        f"{node['key']}.on_select.extra_options",
                        extra["next"],
                    )
                )

        action = node.get("action")

        if isinstance(action, dict) and action.get("handler"):
            if action["handler"] not in ACTIONS:
                raise ValueError(
                    f"Node '{node['key']}' uses unknown action handler "
                    f"'{action['handler']}'"
                )

        source = node.get("options_source") or {}

        if source.get("provider") and source["provider"] not in OPTION_SOURCES:
            raise ValueError(
                f"Node '{node['key']}' uses unknown options_source "
                f"'{source['provider']}'"
            )

        if on_input.get("handler") and on_input["handler"] not in INPUT_HANDLERS:
            raise ValueError(
                f"Node '{node['key']}' uses unknown on_input handler "
                f"'{on_input['handler']}'"
            )

        if on_select.get("handler") and on_select["handler"] not in SELECT_HANDLERS:
            raise ValueError(
                f"Node '{node['key']}' uses unknown on_select handler "
                f"'{on_select['handler']}'"
            )

    for source, next_key in referenced:
        if next_key not in node_keys:
            raise ValueError(
                f"{source} references unknown node '{next_key}'"
            )
