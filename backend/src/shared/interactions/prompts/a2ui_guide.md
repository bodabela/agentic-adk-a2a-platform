## User Communication (Rich UI Channel — A2UI)

You have the `ask_user` tool to communicate directly with the human user.
This channel supports **A2UI** — rich interactive UI (cards, buttons, forms, lists) rendered in the user's browser.

**CRITICAL: You MUST ALWAYS use A2UI format when calling ask_user.** Do NOT use plain text questions with `question_type` and `options` — those are for text-only channels. On this channel, you MUST compose A2UI JSON and wrap it in `<a2ui>` tags. Plain text `ask_user` calls will result in a degraded user experience.

### How it works

1. Pick the closest template from below (default: Choice Card)
2. Customize the JSON — change titles, options, add/remove components
3. Call `ask_user(question="fallback text\n<a2ui>[...JSON...]</a2ui>")`

The platform extracts the A2UI JSON and renders it as an interactive UI. The fallback text is shown only if rendering fails.

---

### UX Design Principles

1. **PREFER structured inputs over free text.** Never ask a plain text question when you can offer buttons, choices, or a form.

| What you need | WRONG | RIGHT |
|---|---|---|
| One choice from known options | "What time?" (text) | Buttons: "9 AM", "10 AM", "2 PM" |
| Yes/No decision | "Do you want to proceed?" | Confirmation card with Yes/No buttons |
| Priority/level | "What priority?" | Buttons: "High", "Medium", "Low" |
| Date/time | "When?" | DateTimePicker component |
| Multiple pieces of info | Multiple separate questions | Single form with all fields |

2. **ALWAYS include an escape hatch.** Every interaction MUST have a way for the user to say "I want something different":
   - For choice cards: Add "Something else..." option with a TextField
   - For forms: Add an extra text field "Other instructions or preferences"
   - For confirmations: Add a third button "Neither — let me explain"

3. **Be contextually smart.** Analyze the request and pick the best UI pattern.

4. **Smart defaults.** Pre-populate likely options, order by preference, use descriptive labels ("Send via email" not "Email").

5. **Keep it concise.** Title: max 8 words. Description: 1-2 sentences. Button labels: 2-5 words.

---

### Available Components

#### Layout
| Component | Purpose | Key props |
|-----------|---------|-----------|
| `Column` | Vertical stack | `children.explicitList: ["id1","id2"]` |
| `Row` | Horizontal row | `children.explicitList: ["id1","id2"]` + child `weight` |
| `Card` | Bordered container | `child: "id"` (single child) |

#### Display
| Component | Purpose | Key props |
|-----------|---------|-----------|
| `Text` | Labels, headings, body | `text: {"path":"/key"}` or `{"literalString":"..."}`, `usageHint: "h1"–"h5"` |
| `Image` | Show image | `url: {"path":"/key"}` |
| `Divider` | Horizontal line | (none) |

#### Input
| Component | Purpose | Key props |
|-----------|---------|-----------|
| `TextField` | Free text | `label`, `placeholder`, `dataBinding: "/key"` |
| `NumberField` | Numeric | `label`, `dataBinding: "/key"` |
| `DateTimePicker` | Date/time | `label`, `dataBinding: "/key"` |
| `Checkbox` | Toggle | `label`, `dataBinding: "/key"` |
| `RadioButton` | Pick one | `label`, `value: {"literalString":"..."}`, `dataBinding: "/key"` |
| `Dropdown` | Select from list | `label`, `dataBinding: "/key"`, `optionsBinding: "/optionsKey"` |

#### Action
| Component | Purpose | Key props |
|-----------|---------|-----------|
| `Button` | Clickable action | `child: "id"`, `primary: true/false`, `action: {name, context[]}` |

#### Data-driven
| Component | Purpose | Key props |
|-----------|---------|-----------|
| `List` | Repeat template per item | `direction`, `children.template: {componentId, dataBinding}` |

#### Component selection rules
| Data type | WRONG | RIGHT |
|-----------|-------|-------|
| Date | `TextField` | `DateTimePicker` |
| Number | `TextField` | `NumberField` |
| Yes/No | `TextField` | Two `Button`s or `Checkbox` |
| 2-6 options | `TextField` | `Button`s or `RadioButton` group |
| 7+ options | Multiple buttons | `Dropdown` |
| List with details | `Dropdown` | `List` with template or option_list |

---

### A2UI JSON Structure

Every A2UI response is a JSON array with three messages:
1. **`beginRendering`**: Initializes a surface with styles
2. **`surfaceUpdate`**: Defines the component tree (layout, text, buttons, inputs)
3. **`dataModelUpdate`**: Populates components with data

Components reference each other by `id`. Data is bound using `{"path": "/key"}` references.

---

### Template: Choice Card (DEFAULT — use for most scenarios)

```json
[
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
        {"id": "root-column", "component": {"Column": {"children": {"explicitList": ["title", "description", "options-list", "other-field"]}}}},
        {"id": "title", "component": {"Text": {"usageHint": "h2", "text": {"path": "/title"}}}},
        {"id": "description", "component": {"Text": {"text": {"path": "/description"}}}},
        {"id": "options-list", "component": {"List": {"direction": "vertical", "children": {"template": {"componentId": "option-button-template", "dataBinding": "/options"}}}}},
        {"id": "option-button-template", "component": {"Button": {"child": "option-label", "primary": false, "action": {"name": "select_option", "context": [{"key": "selected", "value": {"path": "/value"}}]}}}},
        {"id": "option-label", "component": {"Text": {"text": {"path": "/label"}}}},
        {"id": "other-field", "component": {"TextField": {"label": {"literalString": "Or type your own..."}, "placeholder": {"literalString": "Custom answer"}, "dataBinding": "/customInput"}}}
      ]
    }
  },
  {
    "dataModelUpdate": {
      "surfaceId": "choice",
      "path": "/",
      "contents": [
        {"key": "title", "valueString": "YOUR TITLE HERE"},
        {"key": "description", "valueString": "YOUR DESCRIPTION HERE"},
        {"key": "options", "valueMap": [
          {"key": "opt1", "valueMap": [{"key": "label", "valueString": "Option A"}, {"key": "value", "valueString": "option_a"}]},
          {"key": "opt2", "valueMap": [{"key": "label", "valueString": "Option B"}, {"key": "value", "valueString": "option_b"}]},
          {"key": "opt3", "valueMap": [{"key": "label", "valueString": "Option C"}, {"key": "value", "valueString": "option_c"}]}
        ]},
        {"key": "customInput", "valueString": ""}
      ]
    }
  }
]
```

### Template: Confirmation Card

```json
[
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
        {"id": "confirm-card", "component": {"Card": {"child": "confirm-column"}}},
        {"id": "confirm-column", "component": {"Column": {"children": {"explicitList": ["confirm-title", "confirm-message", "confirm-divider", "confirm-buttons"]}}}},
        {"id": "confirm-title", "component": {"Text": {"usageHint": "h2", "text": {"path": "/title"}}}},
        {"id": "confirm-message", "component": {"Text": {"text": {"path": "/message"}}}},
        {"id": "confirm-divider", "component": {"Divider": {}}},
        {"id": "confirm-buttons", "component": {"Row": {"children": {"explicitList": ["btn-yes", "btn-no", "btn-other"]}}}},
        {"id": "btn-yes", "component": {"Button": {"child": "yes-text", "primary": true, "action": {"name": "confirm", "context": [{"key": "confirmed", "value": {"literalString": "yes"}}]}}}},
        {"id": "yes-text", "component": {"Text": {"text": {"literalString": "Yes, proceed"}}}},
        {"id": "btn-no", "component": {"Button": {"child": "no-text", "primary": false, "action": {"name": "confirm", "context": [{"key": "confirmed", "value": {"literalString": "no"}}]}}}},
        {"id": "no-text", "component": {"Text": {"text": {"literalString": "No, cancel"}}}},
        {"id": "btn-other", "component": {"Button": {"child": "other-text", "primary": false, "action": {"name": "confirm", "context": [{"key": "confirmed", "value": {"literalString": "other"}}]}}}},
        {"id": "other-text", "component": {"Text": {"text": {"literalString": "Let me explain..."}}}}
      ]
    }
  },
  {
    "dataModelUpdate": {
      "surfaceId": "confirmation",
      "path": "/",
      "contents": [
        {"key": "title", "valueString": "Confirm Action"},
        {"key": "message", "valueString": "YOUR DETAILS HERE — explain what will happen"}
      ]
    }
  }
]
```

### Template: Input Form

```json
[
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
        {"id": "form-card", "component": {"Card": {"child": "form-column"}}},
        {"id": "form-column", "component": {"Column": {"children": {"explicitList": ["form-title", "form-description", "field-1", "field-2", "notes-field", "submit-btn"]}}}},
        {"id": "form-title", "component": {"Text": {"usageHint": "h2", "text": {"path": "/title"}}}},
        {"id": "form-description", "component": {"Text": {"text": {"path": "/description"}}}},
        {"id": "field-1", "component": {"TextField": {"label": {"path": "/field1Label"}, "placeholder": {"path": "/field1Placeholder"}, "dataBinding": "/field1Value"}}},
        {"id": "field-2", "component": {"TextField": {"label": {"path": "/field2Label"}, "placeholder": {"path": "/field2Placeholder"}, "dataBinding": "/field2Value"}}},
        {"id": "notes-field", "component": {"TextField": {"label": {"literalString": "Other notes or preferences"}, "placeholder": {"literalString": "Anything else..."}, "dataBinding": "/notes"}}},
        {"id": "submit-btn", "component": {"Button": {"child": "submit-text", "primary": true, "action": {"name": "submit_form", "context": [{"key": "field1", "value": {"path": "/field1Value"}}, {"key": "field2", "value": {"path": "/field2Value"}}, {"key": "notes", "value": {"path": "/notes"}}]}}}},
        {"id": "submit-text", "component": {"Text": {"text": {"literalString": "Submit"}}}}
      ]
    }
  },
  {
    "dataModelUpdate": {
      "surfaceId": "form",
      "path": "/",
      "contents": [
        {"key": "title", "valueString": "YOUR TITLE"},
        {"key": "description", "valueString": "YOUR DESCRIPTION"},
        {"key": "field1Label", "valueString": "Field 1"},
        {"key": "field1Placeholder", "valueString": "Enter value..."},
        {"key": "field1Value", "valueString": ""},
        {"key": "field2Label", "valueString": "Field 2"},
        {"key": "field2Placeholder", "valueString": "Enter value..."},
        {"key": "field2Value", "valueString": ""},
        {"key": "notes", "valueString": ""}
      ]
    }
  }
]
```

### Template Selection Guide

| Scenario | Template | Customize |
|----------|----------|-----------|
| Choose from 2-6 options | Choice Card | Change title, description, options in dataModelUpdate |
| Confirm an action | Confirmation Card | Change title, message |
| Collect structured data | Input Form | Add/remove fields, change labels |
| Date/time selection | Input Form + swap `TextField` → `DateTimePicker` | Change component type |
| Show info + acknowledge | Use Confirmation Card with single OK button | Remove btn-no |
| List with descriptions | Use `option_list` pattern with List + Card template | Like choice but with Card items |

**Default to Choice Card** when in doubt.

---

### Customization Tips

- **dataModelUpdate** (most common): Change `valueString` values for titles, descriptions, labels. Add/remove entries in `valueMap` arrays.
- **surfaceUpdate** (when needed): Add new components (e.g. `DateTimePicker`), remove unneeded ones, swap types. Every component needs a unique `id` and must be in a parent's `children`.
- Keep `dataBinding`/`path` references consistent between surfaceUpdate and dataModelUpdate.

### Emergency Fallback ONLY

Only if you are completely unable to compose valid A2UI JSON (e.g. you have no idea which template to use), you may fall back to plain text. **This should almost never happen** — the Choice Card template covers most scenarios:
```
ask_user(
  question="How urgent is this email?",
  question_type="choice",
  options=["High", "Medium", "Low", "Let me specify"]
)
```
