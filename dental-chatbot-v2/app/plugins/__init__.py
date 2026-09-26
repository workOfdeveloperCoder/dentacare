from __future__ import annotations

from typing import Any, Callable


OptionSource = Callable[..., list[dict[str, Any]]]
ActionHandler = Callable[..., dict[str, Any]]
InputHandler = Callable[..., dict[str, Any] | None]
SelectHandler = Callable[..., dict[str, Any] | None]


OPTION_SOURCES: dict[str, OptionSource] = {}
ACTIONS: dict[str, ActionHandler] = {}
INPUT_HANDLERS: dict[str, InputHandler] = {}
SELECT_HANDLERS: dict[str, SelectHandler] = {}


def option_source(name: str):
    def decorator(func: OptionSource) -> OptionSource:
        OPTION_SOURCES[name] = func
        return func

    return decorator


def action(name: str):
    def decorator(func: ActionHandler) -> ActionHandler:
        ACTIONS[name] = func
        return func

    return decorator


def input_handler(name: str):
    def decorator(func: InputHandler) -> InputHandler:
        INPUT_HANDLERS[name] = func
        return func

    return decorator


def select_handler(name: str):
    def decorator(func: SelectHandler) -> SelectHandler:
        SELECT_HANDLERS[name] = func
        return func

    return decorator


def load_plugins() -> None:
    from app.plugins import orders, slots  # noqa: F401
