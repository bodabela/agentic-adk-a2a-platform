"""A2UI MCP tool server for user_agent.

Provides tools to generate and validate A2UI declarative UI payloads,
enabling rich graphical interactions instead of plain text questions.

The a2ui-agent SDK is optional — when unavailable the server falls back
to built-in templates and basic JSON validation.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("user_agent.a2ui")

# --------------------------------------------------------------------------- #
# Try importing A2UI SDK; fall back gracefully if not installed                #
# --------------------------------------------------------------------------- #
_HAS_A2UI_SDK = False
_schema_manager = None

A2UI_OPEN_TAG = "<a2ui>"
A2UI_CLOSE_TAG = "</a2ui>"
A2UI_VERSION = "0.8"

try:
    from a2ui.core.schema.constants import VERSION_0_8, A2UI_OPEN_TAG, A2UI_CLOSE_TAG  # type: ignore[assignment]
    from a2ui.core.schema.manager import A2uiSchemaManager
    from a2ui.basic_catalog.provider import BasicCatalog
    from a2ui.core.schema.common_modifiers import remove_strict_validation

    A2UI_VERSION = VERSION_0_8
    _HAS_A2UI_SDK = True
    logger.info("a2ui SDK loaded successfully")
except ImportError:
    logger.warning("a2ui SDK not available — using built-in templates only")


mcp = FastMCP("user_agent_a2ui")

# Resolve the examples directory relative to this file
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

# Initialize A2UI schema manager (only if SDK is available)
if _HAS_A2UI_SDK:
    try:
        _schema_manager = A2uiSchemaManager(
            A2UI_VERSION,
            catalogs=[
                BasicCatalog.get_config(
                    version=A2UI_VERSION,
                    examples_path=str(EXAMPLES_DIR) if EXAMPLES_DIR.is_dir() else None,
                )
            ],
            schema_modifiers=[remove_strict_validation],
        )
    except Exception as e:
        logger.warning(f"Failed to init A2uiSchemaManager: {e}")
        _schema_manager = None


@mcp.tool()
def get_a2ui_component_catalog() -> str:
    """Get the available A2UI component catalog and schema.

    Returns a description of all available UI components (Card, Button, Text,
    TextField, List, Column, Row, Image, Divider, etc.) and how to compose
    them into A2UI JSON payloads.

    Use this at the start of a conversation to understand what UI components
    are available before generating A2UI responses.

    Returns:
        JSON string with component catalog info and usage guidelines.
    """
    has_schema = False
    if _schema_manager:
        catalog = _schema_manager.get_selected_catalog()
        has_schema = bool(catalog and catalog.catalog_schema)

    return json.dumps({
        "version": A2UI_VERSION,
        "open_tag": A2UI_OPEN_TAG,
        "close_tag": A2UI_CLOSE_TAG,
        "sdk_available": _HAS_A2UI_SDK,
        "guidelines": (
            "A2UI responses are JSON arrays wrapped in special tags. "
            "Each response contains: beginRendering (sets up surface), "
            "surfaceUpdate (defines component tree), and dataModelUpdate "
            "(populates data). Components reference each other by ID. "
            "Data is bound via {\"path\": \"/key\"} references."
        ),
        "available_components": [
            "Card", "Column", "Row", "Text", "Button", "TextField",
            "Image", "List", "Divider", "DateTimePicker", "NumberField",
            "Checkbox", "RadioButton", "Dropdown",
        ],
        "component_schema_available": has_schema,
    }, indent=2)


@mcp.tool()
def validate_a2ui_payload(payload_json: str) -> str:
    """Validate an A2UI JSON payload against the schema.

    Call this after generating A2UI JSON to ensure it conforms to the
    A2UI specification before sending it to the user.

    Args:
        payload_json: The A2UI JSON string (the content between a2ui tags).

    Returns:
        JSON with 'valid' boolean and optional 'errors' list.
    """
    try:
        parsed = json.loads(payload_json)
    except json.JSONDecodeError as e:
        return json.dumps({"valid": False, "errors": [f"Invalid JSON: {e}"]})

    if not isinstance(parsed, list):
        return json.dumps({"valid": False, "errors": ["A2UI payload must be a JSON array"]})

    # Basic structural checks (works without SDK)
    errors = []
    has_begin = any("beginRendering" in msg for msg in parsed if isinstance(msg, dict))
    has_surface = any("surfaceUpdate" in msg for msg in parsed if isinstance(msg, dict))
    has_data = any("dataModelUpdate" in msg for msg in parsed if isinstance(msg, dict))

    if not has_begin:
        errors.append("Missing 'beginRendering' message")
    if not has_surface:
        errors.append("Missing 'surfaceUpdate' message")
    if not has_data:
        errors.append("Missing 'dataModelUpdate' message")

    if errors:
        return json.dumps({"valid": False, "errors": errors})

    # Full schema validation if SDK is available
    if _schema_manager:
        catalog = _schema_manager.get_selected_catalog()
        if catalog and catalog.catalog_schema:
            try:
                catalog.validator.validate(parsed)
            except Exception as e:
                return json.dumps({"valid": False, "errors": [str(e)]})

    return json.dumps({"valid": True})


@mcp.tool()
def get_a2ui_example(example_name: str) -> str:
    """Get a specific A2UI example template.

    Available examples (use "choice_with_other" as default for most scenarios):
    - "choice_with_other": **DEFAULT** — Buttons for options + free text field for custom input. Use this for preferences, priorities, approaches.
    - "choice_card": Simple buttons without free text escape hatch
    - "confirmation_card": A confirmation dialog with Yes/No/Neither buttons
    - "input_form": A form with text fields for collecting structured information
    - "info_card": An informational card with details display
    - "option_list": A list of items with descriptions the user can choose from

    Args:
        example_name: Name of the example to retrieve.

    Returns:
        The A2UI JSON example as a string, or an error message.
    """
    # Try file-based examples first
    example_file = EXAMPLES_DIR / f"{example_name}.json"
    if example_file.is_file():
        return example_file.read_text(encoding="utf-8")

    # Fall back to built-in examples
    builtin = _BUILTIN_EXAMPLES.get(example_name)
    if builtin:
        return json.dumps(builtin, indent=2)

    available = list(_BUILTIN_EXAMPLES.keys())
    if EXAMPLES_DIR.is_dir():
        available.extend(p.stem for p in EXAMPLES_DIR.glob("*.json"))
    return json.dumps({
        "error": f"Example '{example_name}' not found",
        "available": sorted(set(available)),
    })


@mcp.tool()
def wrap_a2ui_response(a2ui_json: str, fallback_text: str = "") -> str:
    """Wrap A2UI JSON in the proper tags for transport.

    Takes raw A2UI JSON and wraps it in the required <a2ui> tags so it
    can be embedded in the ask_user question parameter.

    Args:
        a2ui_json: The A2UI JSON payload string.
        fallback_text: Plain text fallback for clients that don't support A2UI.

    Returns:
        The properly tagged A2UI response string.
    """
    text_parts = []
    if fallback_text:
        text_parts.append(fallback_text)
    text_parts.append(f"{A2UI_OPEN_TAG}{a2ui_json}{A2UI_CLOSE_TAG}")
    return "\n".join(text_parts)


# ---------------------------------------------------------------------------
# Built-in example templates for common user_agent interactions
# ---------------------------------------------------------------------------

_BUILTIN_EXAMPLES: dict[str, list] = {
    "choice_card": [
        {
            "beginRendering": {
                "surfaceId": "choice",
                "root": "root-column",
                "styles": {"primaryColor": "#1976D2", "font": "Roboto"}
            }
        },
        {
            "surfaceUpdate": {
                "surfaceId": "choice",
                "components": [
                    {
                        "id": "root-column",
                        "component": {
                            "Column": {
                                "children": {"explicitList": ["title", "description", "options-list"]}
                            }
                        }
                    },
                    {
                        "id": "title",
                        "component": {
                            "Text": {"usageHint": "h2", "text": {"path": "/title"}}
                        }
                    },
                    {
                        "id": "description",
                        "component": {
                            "Text": {"text": {"path": "/description"}}
                        }
                    },
                    {
                        "id": "options-list",
                        "component": {
                            "List": {
                                "direction": "vertical",
                                "children": {
                                    "template": {
                                        "componentId": "option-button-template",
                                        "dataBinding": "/options"
                                    }
                                }
                            }
                        }
                    },
                    {
                        "id": "option-button-template",
                        "component": {
                            "Button": {
                                "child": "option-label",
                                "primary": False,
                                "action": {
                                    "name": "select_option",
                                    "context": [
                                        {"key": "selected", "value": {"path": "/value"}}
                                    ]
                                }
                            }
                        }
                    },
                    {
                        "id": "option-label",
                        "component": {
                            "Text": {"text": {"path": "/label"}}
                        }
                    }
                ]
            }
        },
        {
            "dataModelUpdate": {
                "surfaceId": "choice",
                "path": "/",
                "contents": [
                    {"key": "title", "valueString": "Please choose an option"},
                    {"key": "description", "valueString": "Select one of the following:"},
                    {
                        "key": "options",
                        "valueMap": [
                            {"key": "opt1", "valueMap": [
                                {"key": "label", "valueString": "Option A"},
                                {"key": "value", "valueString": "option_a"}
                            ]},
                            {"key": "opt2", "valueMap": [
                                {"key": "label", "valueString": "Option B"},
                                {"key": "value", "valueString": "option_b"}
                            ]}
                        ]
                    }
                ]
            }
        }
    ],

    "confirmation_card": [
        {
            "beginRendering": {
                "surfaceId": "confirmation",
                "root": "confirm-card",
                "styles": {"primaryColor": "#388E3C", "font": "Roboto"}
            }
        },
        {
            "surfaceUpdate": {
                "surfaceId": "confirmation",
                "components": [
                    {
                        "id": "confirm-card",
                        "component": {"Card": {"child": "confirm-column"}}
                    },
                    {
                        "id": "confirm-column",
                        "component": {
                            "Column": {
                                "children": {"explicitList": [
                                    "confirm-title", "confirm-message",
                                    "confirm-divider", "confirm-buttons"
                                ]}
                            }
                        }
                    },
                    {
                        "id": "confirm-title",
                        "component": {
                            "Text": {"usageHint": "h2", "text": {"path": "/title"}}
                        }
                    },
                    {
                        "id": "confirm-message",
                        "component": {
                            "Text": {"text": {"path": "/message"}}
                        }
                    },
                    {
                        "id": "confirm-divider",
                        "component": {"Divider": {}}
                    },
                    {
                        "id": "confirm-buttons",
                        "component": {
                            "Row": {
                                "children": {"explicitList": ["btn-yes", "btn-no"]}
                            }
                        }
                    },
                    {
                        "id": "btn-yes",
                        "component": {
                            "Button": {
                                "child": "yes-text", "primary": True,
                                "action": {"name": "confirm", "context": [
                                    {"key": "confirmed", "value": {"literalString": "yes"}}
                                ]}
                            }
                        }
                    },
                    {
                        "id": "yes-text",
                        "component": {"Text": {"text": {"literalString": "Yes, proceed"}}}
                    },
                    {
                        "id": "btn-no",
                        "component": {
                            "Button": {
                                "child": "no-text", "primary": False,
                                "action": {"name": "confirm", "context": [
                                    {"key": "confirmed", "value": {"literalString": "no"}}
                                ]}
                            }
                        }
                    },
                    {
                        "id": "no-text",
                        "component": {"Text": {"text": {"literalString": "No, cancel"}}}
                    }
                ]
            }
        },
        {
            "dataModelUpdate": {
                "surfaceId": "confirmation",
                "path": "/",
                "contents": [
                    {"key": "title", "valueString": "Confirm Action"},
                    {"key": "message", "valueString": "Are you sure you want to proceed?"}
                ]
            }
        }
    ],

    "input_form": [
        {
            "beginRendering": {
                "surfaceId": "form",
                "root": "form-card",
                "styles": {"primaryColor": "#1976D2", "font": "Roboto"}
            }
        },
        {
            "surfaceUpdate": {
                "surfaceId": "form",
                "components": [
                    {
                        "id": "form-card",
                        "component": {"Card": {"child": "form-column"}}
                    },
                    {
                        "id": "form-column",
                        "component": {
                            "Column": {
                                "children": {"explicitList": [
                                    "form-title", "form-description",
                                    "field-input", "submit-btn"
                                ]}
                            }
                        }
                    },
                    {
                        "id": "form-title",
                        "component": {
                            "Text": {"usageHint": "h2", "text": {"path": "/title"}}
                        }
                    },
                    {
                        "id": "form-description",
                        "component": {
                            "Text": {"text": {"path": "/description"}}
                        }
                    },
                    {
                        "id": "field-input",
                        "component": {
                            "TextField": {
                                "label": {"path": "/fieldLabel"},
                                "placeholder": {"path": "/fieldPlaceholder"},
                                "dataBinding": "/userInput"
                            }
                        }
                    },
                    {
                        "id": "submit-btn",
                        "component": {
                            "Button": {
                                "child": "submit-text", "primary": True,
                                "action": {
                                    "name": "submit_form",
                                    "context": [
                                        {"key": "input", "value": {"path": "/userInput"}}
                                    ]
                                }
                            }
                        }
                    },
                    {
                        "id": "submit-text",
                        "component": {"Text": {"text": {"literalString": "Submit"}}}
                    }
                ]
            }
        },
        {
            "dataModelUpdate": {
                "surfaceId": "form",
                "path": "/",
                "contents": [
                    {"key": "title", "valueString": "Provide Information"},
                    {"key": "description", "valueString": "Please fill in the details below."},
                    {"key": "fieldLabel", "valueString": "Your response"},
                    {"key": "fieldPlaceholder", "valueString": "Type here..."},
                    {"key": "userInput", "valueString": ""}
                ]
            }
        }
    ],

    "info_card": [
        {
            "beginRendering": {
                "surfaceId": "info",
                "root": "info-card",
                "styles": {"primaryColor": "#7B1FA2", "font": "Roboto"}
            }
        },
        {
            "surfaceUpdate": {
                "surfaceId": "info",
                "components": [
                    {
                        "id": "info-card",
                        "component": {"Card": {"child": "info-column"}}
                    },
                    {
                        "id": "info-column",
                        "component": {
                            "Column": {
                                "children": {"explicitList": [
                                    "info-title", "info-divider", "info-body", "ok-btn"
                                ]}
                            }
                        }
                    },
                    {
                        "id": "info-title",
                        "component": {
                            "Text": {"usageHint": "h2", "text": {"path": "/title"}}
                        }
                    },
                    {
                        "id": "info-divider",
                        "component": {"Divider": {}}
                    },
                    {
                        "id": "info-body",
                        "component": {
                            "Text": {"text": {"path": "/body"}}
                        }
                    },
                    {
                        "id": "ok-btn",
                        "component": {
                            "Button": {
                                "child": "ok-text", "primary": True,
                                "action": {"name": "acknowledge", "context": [
                                    {"key": "ack", "value": {"literalString": "ok"}}
                                ]}
                            }
                        }
                    },
                    {
                        "id": "ok-text",
                        "component": {"Text": {"text": {"literalString": "OK"}}}
                    }
                ]
            }
        },
        {
            "dataModelUpdate": {
                "surfaceId": "info",
                "path": "/",
                "contents": [
                    {"key": "title", "valueString": "Information"},
                    {"key": "body", "valueString": "Here are the details..."}
                ]
            }
        }
    ],

    "option_list": [
        {
            "beginRendering": {
                "surfaceId": "option-list",
                "root": "root-column",
                "styles": {"primaryColor": "#E65100", "font": "Roboto"}
            }
        },
        {
            "surfaceUpdate": {
                "surfaceId": "option-list",
                "components": [
                    {
                        "id": "root-column",
                        "component": {
                            "Column": {
                                "children": {"explicitList": ["title", "item-list"]}
                            }
                        }
                    },
                    {
                        "id": "title",
                        "component": {
                            "Text": {"usageHint": "h2", "text": {"path": "/title"}}
                        }
                    },
                    {
                        "id": "item-list",
                        "component": {
                            "List": {
                                "direction": "vertical",
                                "children": {
                                    "template": {
                                        "componentId": "item-card",
                                        "dataBinding": "/items"
                                    }
                                }
                            }
                        }
                    },
                    {
                        "id": "item-card",
                        "component": {"Card": {"child": "item-row"}}
                    },
                    {
                        "id": "item-row",
                        "component": {
                            "Row": {
                                "children": {"explicitList": ["item-info", "item-select-btn"]}
                            }
                        }
                    },
                    {
                        "id": "item-info",
                        "weight": 3,
                        "component": {
                            "Column": {
                                "children": {"explicitList": ["item-name", "item-desc"]}
                            }
                        }
                    },
                    {
                        "id": "item-name",
                        "component": {
                            "Text": {"usageHint": "h3", "text": {"path": "/name"}}
                        }
                    },
                    {
                        "id": "item-desc",
                        "component": {
                            "Text": {"text": {"path": "/description"}}
                        }
                    },
                    {
                        "id": "item-select-btn",
                        "weight": 1,
                        "component": {
                            "Button": {
                                "child": "select-text", "primary": True,
                                "action": {
                                    "name": "select_item",
                                    "context": [
                                        {"key": "selected", "value": {"path": "/id"}}
                                    ]
                                }
                            }
                        }
                    },
                    {
                        "id": "select-text",
                        "component": {"Text": {"text": {"literalString": "Select"}}}
                    }
                ]
            }
        },
        {
            "dataModelUpdate": {
                "surfaceId": "option-list",
                "path": "/",
                "contents": [
                    {"key": "title", "valueString": "Choose an item"},
                    {
                        "key": "items",
                        "valueMap": [
                            {"key": "item1", "valueMap": [
                                {"key": "id", "valueString": "1"},
                                {"key": "name", "valueString": "Item One"},
                                {"key": "description", "valueString": "Description of item one"}
                            ]},
                            {"key": "item2", "valueMap": [
                                {"key": "id", "valueString": "2"},
                                {"key": "name", "valueString": "Item Two"},
                                {"key": "description", "valueString": "Description of item two"}
                            ]}
                        ]
                    }
                ]
            }
        }
    ],
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=".")
    args = parser.parse_args()

    logger.info("Starting user_agent A2UI MCP server (SDK available: %s)", _HAS_A2UI_SDK)
    mcp.run(transport="stdio")
