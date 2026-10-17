"""Native driver selectors: full names on the left, season teams aligned right."""

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
