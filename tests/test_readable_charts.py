"""Readable chart labels must preserve callback IDs and original timing data."""

import plotly.graph_objects as go

from gridpulse.pitwall import charts, explain


def test_display_expansion_preserves_raw_ids_and_escapes_names():
    names = {'LEC': 'Charles Leclerc', 'PIA': 'Oscar <Piastri>'}
    fig = go.Figure(go.Scatter(x=[1, 2], y=['LEC → PIA', 'LEC → PIA'], name='LEC',
                               customdata=[['LEC'], ['LEC']], hovertemplate='LEC versus PIA'))
    charts.readable(fig, names)
    assert fig.data[0].customdata[0][0] == 'LEC'
    assert fig.data[0].y[0] == 'LEC → PIA' and fig.data[0].name == 'Charles Leclerc'
    assert fig.layout.yaxis.ticktext[0] == 'Charles Leclerc → Oscar &lt;Piastri&gt;'
    assert 'Oscar &lt;Piastri&gt;' in fig.data[0].hovertemplate
    assert explain.expand_codes('LEC passed PIA. SELECT is unchanged.', names) == 'Charles Leclerc passed Oscar <Piastri>. SELECT is unchanged.'


def test_category_hover_gets_a_readable_label_without_shifting_callback_fields():
    fig = go.Figure(go.Bar(x=[12], y=['LEC'], customdata=[['original-id', 4]], hovertemplate='%{y} · %{customdata[1]}'))
    charts.readable(fig, {'LEC': 'Charles Leclerc'})
    assert tuple(fig.data[0].customdata[0]) == ('original-id', 4, 'Charles Leclerc')
    assert fig.data[0].hovertemplate == '%{customdata[2]} · %{customdata[1]}'
