"""Native driver selectors: full names on the left, season teams aligned right."""

import html
import json

import streamlit as st


def css_string(text: str) -> str:
    return json.dumps(str(text), ensure_ascii=False).replace("<", r"\3c ")


def decorate(label: str, options: list[str], teams: dict[str, str], *, key: str,
             selected: str | None = None) -> None:
    """Keep native search, selection and keyboard controls; style only the team metadata."""
    menu = f'[role="listbox"][aria-label={css_string(label)}]'
    rules = [f'{menu} [data-item-hl]{{display:flex;gap:16px;width:100%;box-sizing:border-box}}',
             f'{menu} [data-item-hl]::after{{margin-left:auto;flex:0 1 auto;min-width:0;max-width:48%;'
             'overflow:hidden;text-overflow:ellipsis;font-size:.82em;opacity:.62;text-align:right}',
             f'{menu} [data-item-hl]{{padding-right:12px}}']
    for index, driver in enumerate(options):
        team = teams.get(driver, "")
        if team:
            rules.append(f'{menu} [role="option"][data-key="{index}"] [data-item-hl]::after'
                         f'{{content:{css_string(team)}}}')
    if selected is not None and teams.get(selected):
        group = f'.st-key-{key} [role="group"]:has(> input[role="combobox"])'
        rules.extend([
            f'{group}{{display:flex;align-items:center}}',
            f'{group}>input{{flex:1 1 0;min-width:0;width:0;order:0}}',
            f'{group}::after{{content:{css_string(teams[selected])};order:1;flex:0 1 auto;max-width:45%;'
            'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.75rem;opacity:.62;'
            'pointer-events:none;margin-left:8px;text-align:right}',
            f'{group}>button{{order:2;flex-shrink:0}}',
        ])
    st.html("<style>" + "".join(rules) + "</style>")


def _ink_for(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return "#111111" if 0.299 * r + 0.587 * g + 0.114 * b > 150 else "#ffffff"


def team_colored_picker(label: str, options: list[str], colors: dict[str, str], teams: dict[str, str]) -> None:
    """Colour a multiselect's chips and options by team (Streamlit can't, so CSS keyed on the DOM).

    Chips carry aria-label=<driver>; options carry data-key=<index in options> inside
    a listbox labelled with the widget's label.
    """
    rules = []
    for i, d in enumerate(options):
        c = colors.get(d, "#999999")
        team = html.escape(teams.get(d, "") or "").replace('"', "")
        rules.append(
            f'[data-testid="stMultiSelectTagsContainer"] [data-tag][aria-label="{d}"] '
            f"{{ background: {c} !important; color: {_ink_for(c)} !important; }}"
            f'[data-testid="stMultiSelectTagsContainer"] [data-tag][aria-label="{d}"] button '
            f"{{ color: {_ink_for(c)} !important; }}"
            f'[role="listbox"][aria-label="{label}"] [role="option"][data-key="{i}"] [data-item-hl]::before '
            f'{{ content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 9px; '
            f"background: {c}; vertical-align: -1px; }}"
            f'[role="listbox"][aria-label="{label}"] [role="option"][data-key="{i}"] [data-item-hl]::after '
            f'{{ content: "{team}"; opacity: .5; font-size: .8em; margin-left: 8px; }}'
        )
    st.html("<style>" + "".join(rules) + "</style>")
