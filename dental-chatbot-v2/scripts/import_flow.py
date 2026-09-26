import json
import sys
from pathlib import Path

from psycopg.types.json import Json

from app.db import ensure_schema, get_connection
from app.flow_schema import flow_config, node_config, validate_flow
from app.plugins import load_plugins


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def import_flow(flow: dict) -> None:
    ensure_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_flows (
                    name,
                    slug,
                    description,
                    is_active,
                    config
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                ON CONFLICT (slug)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    is_active = EXCLUDED.is_active,
                    config = EXCLUDED.config,
                    updated_at = NOW()
                RETURNING id;
                """,
                (
                    flow["name"],
                    flow["flow_key"],
                    flow.get("description"),
                    flow.get("status", "active") == "active",
                    Json(flow_config(flow)),
                ),
            )

            flow_id = cur.fetchone()[0]

            print(f"Flow: {flow['flow_key']}")
            print(f"Flow ID: {flow_id}")

            node_ids = {}

            for node in flow["nodes"]:
                cur.execute(
                    """
                    INSERT INTO chat_nodes (
                        flow_id,
                        node_key,
                        node_type,
                        message,
                        input_key,
                        validation_type,
                        is_start,
                        is_active,
                        config
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, TRUE, %s
                    )
                    ON CONFLICT (flow_id, node_key)
                    DO UPDATE SET
                        node_type = EXCLUDED.node_type,
                        message = EXCLUDED.message,
                        input_key = EXCLUDED.input_key,
                        validation_type = EXCLUDED.validation_type,
                        is_start = EXCLUDED.is_start,
                        is_active = TRUE,
                        config = EXCLUDED.config,
                        updated_at = NOW()
                    RETURNING id;
                    """,
                    (
                        flow_id,
                        node["key"],
                        node["type"],
                        node["message"],
                        node.get("input_key"),
                        node.get("validation_type"),
                        node["key"] == flow["start_node"],
                        Json(node_config(node)),
                    ),
                )

                node_ids[node["key"]] = cur.fetchone()[0]

            print(f"Nodes imported: {len(node_ids)}")

            cur.execute(
                """
                UPDATE chat_nodes
                SET
                    next_node_id = NULL,
                    previous_node_id = NULL,
                    updated_at = NOW()
                WHERE flow_id = %s;
                """,
                (flow_id,),
            )

            for node in flow["nodes"]:
                next_key = node.get("next")

                if not next_key:
                    continue

                cur.execute(
                    """
                    UPDATE chat_nodes
                    SET next_node_id = %s, updated_at = NOW()
                    WHERE id = %s AND flow_id = %s;
                    """,
                    (
                        node_ids[next_key],
                        node_ids[node["key"]],
                        flow_id,
                    ),
                )

            predecessors = {}

            for node in flow["nodes"]:
                next_key = node.get("next")

                if next_key:
                    predecessors.setdefault(next_key, []).append(node["key"])

                for option in node.get("options", []):
                    option_next = option.get("next")

                    if option_next:
                        predecessors.setdefault(option_next, []).append(
                            node["key"]
                        )

            for target_key, sources in predecessors.items():
                unique_sources = list(dict.fromkeys(sources))

                if len(unique_sources) == 1:
                    cur.execute(
                        """
                        UPDATE chat_nodes
                        SET previous_node_id = %s, updated_at = NOW()
                        WHERE id = %s AND flow_id = %s;
                        """,
                        (
                            node_ids[unique_sources[0]],
                            node_ids[target_key],
                            flow_id,
                        ),
                    )

            cur.execute(
                """
                DELETE FROM chat_node_options
                WHERE node_id IN (
                    SELECT id FROM chat_nodes WHERE flow_id = %s
                );
                """,
                (flow_id,),
            )

            option_count = 0

            for node in flow["nodes"]:
                for sort_order, option in enumerate(node.get("options", [])):
                    next_node_id = (
                        node_ids[option["next"]] if option.get("next") else None
                    )

                    cur.execute(
                        """
                        INSERT INTO chat_node_options (
                            node_id,
                            option_key,
                            label,
                            next_node_id,
                            sort_order,
                            is_active
                        )
                        VALUES (%s, %s, %s, %s, %s, TRUE);
                        """,
                        (
                            node_ids[node["key"]],
                            option["key"],
                            option["label"],
                            next_node_id,
                            sort_order,
                        ),
                    )
                    option_count += 1

            print(f"Options imported: {option_count}")

        conn.commit()

    print()
    print("====================================")
    print("FLOW IMPORT COMPLETED")
    print("====================================")
    print(f"Flow: {flow['flow_key']}")
    print(f"Nodes: {len(flow['nodes'])}")
    print(f"Options: {option_count}")
    print("====================================")


def main():
    if len(sys.argv) != 2:
        print(
            "Usage:\n"
            "  python scripts/import_flow.py flow/dental_reception.json\n"
            "  python scripts/import_flow.py flow/oil_company.json"
        )
        sys.exit(1)

    json_path = Path(sys.argv[1])

    if not json_path.exists():
        print(f"File not found: {json_path}")
        sys.exit(1)

    try:
        load_plugins()
        flow = load_json(json_path)
        validate_flow(flow)
        import_flow(flow)
    except Exception as exc:
        print()
        print("IMPORT FAILED")
        print("------------------------------------")
        print(exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
