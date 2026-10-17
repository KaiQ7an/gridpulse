"""Friendly picker labels must preserve driver codes, teammate defaults and source teams."""

import pandas as pd
from streamlit.testing.v1 import AppTest


def test_full_names_keep_driver_codes_and_teammate_selection():
    source = pd.DataFrame([
        {"Driver": "LEC", "FullName": "Charles Leclerc", "Team": "Ferrari"},
        {"Driver": "VER", "FullName": "Max Verstappen", "Team": "Red Bull Racing"},
        {"Driver": "HAM", "FullName": "Lewis Hamilton", "Team": "Ferrari"},
    ])

    def page():
        import pandas as pd
        import streamlit as st

        from pitlens.pitwall.onboard_page import pick_drivers

        drivers = pd.DataFrame(st.session_state.test_drivers)
        st.write(pick_drivers(drivers))

    at = AppTest.from_function(page)
    at.session_state.test_drivers = source.to_dict("records")
    at.run()
    assert not at.exception
    assert at.selectbox(key="ob_a").value == "LEC"
    assert at.selectbox(key="ob_b").value == "HAM"
    assert at.selectbox(key="ob_a").options == ["Charles Leclerc", "Max Verstappen", "Lewis Hamilton"]
    assert at.selectbox(key="ob_b").options == ["Max Verstappen", "Lewis Hamilton"]
    markup = ''.join(h.proto.body for h in at.get('html'))
    assert 'content:"Ferrari"' in markup and 'margin-left:auto' in markup
    at.selectbox(key="ob_a").set_value("VER").run()
    assert not at.exception
    assert at.selectbox(key="ob_a").value == "VER"
    assert at.selectbox(key="ob_b").value != "VER"


def test_code_only_source_falls_back_to_verified_full_name():
    at = AppTest.from_string('''
import pandas as pd
from pitlens.pitwall.onboard_page import pick_drivers
pick_drivers(pd.DataFrame({"Driver": ["LEC", "HAM"], "Team": ["Ferrari", "Ferrari"]}))
''')
    at.run()
    assert not at.exception
    assert at.selectbox(key="ob_a").options == ["Charles Leclerc", "Lewis Hamilton"]
