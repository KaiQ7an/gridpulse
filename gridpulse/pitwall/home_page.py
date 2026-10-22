"""The GridPulse series hub: offline-first discovery, resumable workspaces and a circuit map."""

import html
from datetime import UTC, datetime

import streamlit as st

from gridpulse import snapshots
from gridpulse.dtm import data as dtm
from gridpulse.dtm.cars import profile as car_profile
from gridpulse.pitwall import dtm_circuits, home_data, styles, ui
from gridpulse.pitwall.atlas_map import atlas_map
from gridpulse.pitwall.featured import FEATURED
from gridpulse.season.atlas import REGIONS, catalog


def esc(value) -> str:
    return html.escape(str(value), quote=True)


@st.cache_data(show_spinner=False, max_entries=16)
def recent(year: int, revision: tuple, dtm_revision: int, today: str) -> list[dict]:
    return home_data.weekends(year, today)


def events_for(year: int) -> list[dict]:
    path = dtm.ROOT / f'{year}.json'
    return recent(year, snapshots.revision(year), path.stat().st_mtime_ns if path.exists() else 0,
                  datetime.now(UTC).date().isoformat())


def reset_limit():
    st.session_state.home_recent_limit = 6


def pin(event_key: str):
    saved = st.session_state.get('home_pins', [])
    st.session_state.home_pins = [v for v in saved if v != event_key] if event_key in saved else [*saved, event_key][:4]


def section(title: str, detail: str = ''):
    st.html(f'<div class="home-section-title"><h2>{esc(title)}</h2><span>{esc(detail)}</span></div>')


def render(pages: dict) -> None:
    styles.inject('home.css')
    styles.inject('learn.css')
    ui.sidebar_brand('Race replay & results')
    ui.sidebar_footer('All series')
    st.html('''<header class="home-hero"><h1>Understand the race.<br>Or just check the result.</h1>
      <p class="intro">Replay an F1 decision, compare two laps, or catch up on a DTM weekend.
      Choose a question below to get started.</p></header>''')
    with st.container(border=True, key='home-guide'):
        st.html('<div class="learn-entry"><h2>New to racing? Start with one decision.</h2>'
                '<p>Why would the leader stop and give up time? Meet the drivers, try waiting two laps, '
                'and see the trade-off. About two minutes · no race result revealed.</p></div>')
        st.page_link(pages['Race guide'], label='Try your first pit-stop decision', icon=':material/play_arrow:')
    resumes = home_data.resume_targets(st.session_state)
    if resumes:
        section('Pick up where you left off', 'Selections stay in this browser session')
        for col, target in zip(st.columns(len(resumes), gap='medium'), resumes):
            with col, st.container(border=True, key='home-resume-' + target['series'].replace(' ', '-')):
                st.html(f'<div class="home-event-series">{esc(target["series"])}</div>'
                        f'<div class="home-resume-title">{esc(target["title"])}</div>'
                        f'<div class="home-resume-detail">{esc(target["detail"])}</div>')
                st.page_link(pages[target['page']], label='Continue ' + target['series'], icon=':material/play_arrow:',
                             query_params=target['params'], width='stretch')
    section('Choose your series', 'F1 replay and analysis · DTM results and standings')
    year = home_data.years()[0]
    rows = events_for(year)
    series_cards(pages, year, rows)
    render_shortlist(pages)
    section('Around the paddock', 'Recent weekends in the saved archive')
    filters = st.columns([3, 1, 1.5], gap='medium', vertical_alignment='bottom')
    with filters[0]:
        series = st.segmented_control('Show racing series', ['All series', 'Formula 1', 'DTM'],
                                      default='All series', key='home_recent_series', required=True, on_change=reset_limit)
    with filters[1]:
        year = st.selectbox('Season', home_data.years(), key='home_recent_year', on_change=reset_limit)
    with filters[2]:
        show_results = st.toggle('Show results', key='home_show_results', value=False,
                                 help='Reveal podiums. Results are hidden by default to keep the home page spoiler-free.')
    query = st.text_input('Find a weekend', key='home_search', placeholder='Search a race or venue',
                          icon=':material/search:', on_change=reset_limit).strip().casefold()
    rows = [r for r in events_for(year) if (series == 'All series' or r['series'] == series)
            and query in f'{r["title"]} {r["place"]} {r["year"]}'.casefold()]
    limit = st.session_state.get('home_recent_limit', 6)
    st.caption(f'{len(rows)} weekends · dates and results from bundled snapshots · results {"shown" if show_results else "hidden"}')
    if not rows:
        st.info('No matching weekends. Choose another season or clear your search.')
    for i, event in enumerate(rows[:limit]):
        if i % 3 == 0:
            columns = st.columns(3, gap='medium')
        with columns[i % 3], st.container(border=True, height='stretch', key='home-weekend-' + event['key']):
            render_weekend(event, pages, show_results)
    if len(rows) > limit:
        if st.button('Explore more weekends', icon=':material/expand_more:', key='home_more', width='stretch'):
            st.session_state.home_recent_limit = limit + 6
            st.rerun()
    render_map(pages)
    st.html('<footer class="home-foot"><span>GridPulse · Motorsport, lap by lap.<br>Independent project. Not affiliated with a championship or team.</span>'
            '<span>F1: FastF1 / OpenF1 · DTM: official classifications<br>'
            '<a href="https://github.com/KaiQ7an/gridpulse/blob/main/docs/data-validation.md" target="_blank" rel="noopener noreferrer">Data coverage & validation ↗</a></span></footer>')


def series_cards(pages: dict, year: int, rows: list[dict]):
    dtm_year = max(y for y in dtm.YEARS if y <= datetime.now(UTC).year)
    dtm_season = dtm.saved(dtm_year)
    photo = car_profile(dtm_year, 'Porsche')['photo']
    details = [
        ('Formula 1', home_data.F1_PHOTO, 'Open-wheel, single-seater racing.',
         'Choose F1 to understand a pit-stop decision or compare how two drivers complete a lap.',
         [(len([r for r in rows if r['series'] == 'Formula 1']), f'{year} saved GPs'),
          (len(catalog()), 'Circuit files')],
         [('Race replay', 'Open Formula 1', {'mode': 'replay', 'view': 'Strategy'}),
          ('Season', 'Championship', {}), ('Onboard', 'Compare laps', {})]),
        ('DTM', photo, 'GT racing with recognisable car brands.',
         'Choose DTM for race results and the title fight. Each weekend has two separate races, each with its own qualifying.',
         [(len(dtm_season['events']), f'{dtm_year} weekends'),
          (sum(s['kind'] == 'race' for e in dtm_season['events'] for s in e['sessions']), 'Published races')],
         [('DTM', 'Open DTM', {'year': str(dtm_year), 'view': 'championship'}),
          ('DTM', 'Race weekends', {'year': str(dtm_year), 'view': 'weekend'}),
          ('DTM', 'Teams & cars', {'year': str(dtm_year), 'view': 'teams'})]),
    ]
    for col, (series, image, headline, description, counts, links) in zip(st.columns(2, gap='large'), details):
        with col, st.container(border=True, height='stretch', key='home-series-' + series.replace(' ', '-')):
            # The photo is a background over a local SVG silhouette: failed CDN requests leave
            # the fallback visible, without inline onerror handlers (st.html sanitises scripts).
            st.html(f'<div class="home-series-cover {"f1" if series == "Formula 1" else "gt"}" '
                    f'role="img" aria-label="{esc(image["credit"])}">'
                    f'<div class="home-series-photo" style="background-image:url(&quot;{esc(image["url"])}&quot;)"></div>'
                    f'<span class="series-name">{esc(series)}</span></div>'
                    f'<div class="home-series-caption"><a href="{esc(image["source"])}" target="_blank" rel="noopener noreferrer">'
                    f'Photo: {esc(image["credit"])} ↗</a></div>')
            page, label, params = links[0]
            st.html(f'<strong>{esc(headline)}</strong><div class="home-series-description">{esc(description)}</div>')
            with st.container(key='home-enter-' + series.replace(' ', '-')):
                st.page_link(pages[page], label=label, icon=':material/arrow_forward:', query_params=params, width='stretch')
            if series == 'Formula 1':
                st.html('<div class="home-featured-caption">Featured strategy moments</div>')
                with st.container(key='home-strategy-moments'):
                    for moment in FEATURED:
                        st.page_link(pages['Race replay'], label=moment.question, query_params=moment.params,
                                     help=moment.context, icon=':material/play_arrow:')
                        st.caption(moment.context)
            st.html('<div class="home-series-meta">' + ''.join(f'<div><b>{n}</b><small>{esc(label)}</small></div>' for n, label in counts) + '</div>')
            for page, label, params in links[1:]:
                st.page_link(pages[page], label=label, icon=':material/north_east:',
                             query_params=params, width='stretch')


def render_weekend(event: dict, pages: dict, show_results: bool):
    st.html(f'<div class="home-event-series">{esc(event["series"])} · R{event["round"]}<span>{esc(event["date"])}</span></div>'
            f'<div class="home-event-title">{esc(event["title"])}</div><div class="home-event-place">{esc(event["place"])}</div>'
            f'<div class="home-event-description">{esc(event["summary"])}</div>')
    if event.get('venue_note'):
        st.caption(event['venue_note'])
        st.link_button('Why Malaysia? · Official announcement', event['venue_source'], icon=':material/open_in_new:')
    if show_results:
        for label, names in home_data.podiums(event):
            st.html(f'<div class="home-podium"><small>{esc(label)} · classified podium</small>' + ''.join(
                f'<div><span class="position">{i}</span>{esc(name)}</div>' for i, name in enumerate(names, 1)) + '</div>')
    st.page_link(pages[event['page']], label='Open weekend', icon=':material/arrow_forward:',
                 query_params=event['params'], width='stretch')
    saved = event['key'] in st.session_state.get('home_pins', [])
    st.button('Pinned' if saved else 'Pin weekend', icon=':material/bookmark:' if saved else ':material/bookmark_add:',
              key='home-pin-' + event['key'], on_click=pin, args=(event['key'],), width='stretch',
              disabled=not saved and len(st.session_state.get('home_pins', [])) >= 4,
              help='Keep up to four weekends in your shortlist for this browser session.')
    st.caption(event['source'])


def render_shortlist(pages: dict):
    saved = st.session_state.get('home_pins', [])
    if not saved:
        return
    section('Your shortlist', 'Pinned weekends · this session')
    years = {int(key.split('-')[1]) for key in saved}
    lookup = {r['key']: r for year in years for r in events_for(year)}
    for col, key in zip(st.columns(min(len(saved), 4), gap='medium'), saved):
        event = lookup.get(key)
        if event:
            with col, st.container(border=True, height='stretch'):
                st.caption(f'{event["series"]} · {event["year"]}')
                st.page_link(pages[event['page']], label=event['title'], query_params=event['params'])
                st.button('Unpin', icon=':material/bookmark_remove:', key='home-unpin-' + key, on_click=pin, args=(key,))


def render_map(pages: dict):
    section('Racing, around the world', 'Drag · hover · zoom · open a circuit')
    series = st.segmented_control('Circuit atlas series', ['Formula 1', 'DTM'], key='home_map_series',
                                  default='Formula 1', required=True)
    if series == 'DTM':
        year = max(y for y in dtm.YEARS if y <= datetime.now(UTC).year)
        season = dtm.saved(year)
        facts = dtm_circuits.facts_for(year, season['fetched_at'], season)
        regions = dtm_circuits.REGIONS
    else:
        facts, regions = catalog(), REGIONS
    ss = st.session_state
    if 'home_map_requested' in ss:
        ss.home_map_region = ss.pop('home_map_requested')
    default_region = 'europe' if series == 'DTM' else 'world'
    if ss.get('home_map_last_series') != series or ss.get('home_map_region') not in regions:
        ss.home_map_region = default_region
    ss.home_map_last_series = series
    region = st.pills('Map region', list(regions), key='home_map_region', format_func=lambda r: regions[r]['name']) or default_region
    key = f'home-atlas-{series}-{region}'
    # The map needs venue facts only, never entire DTM race classifications.
    fields = ('slug', 'name', 'city', 'country', 'region', 'lat', 'lon', 'length_km',
              'opened', 'preview', 'record', 'laps', 'first_gp')
    pins = [{k: c[k] for k in fields if k in c} for c in facts]
    if series == 'Formula 1':
        for pin, fact in zip(pins, facts):
            pin['history'] = {'races': fact.get('history', {}).get('races')}
    event = atlas_map(region, key=key, circuit_data=pins, regions=regions, series=series, height=430)
    st.caption('Select a marker to open sourced circuit facts, history and records. Maps and reference facts work offline.')
    if not isinstance(event, dict) or not event.get('id') or ss.get('home_map_clicks', {}).get(key) == event['id']:
        return
    ss.home_map_clicks = {**ss.get('home_map_clicks', {}), key: event['id']}
    if event.get('kind') == 'region' and event.get('value') in regions:
        ss.home_map_requested = event['value']
        st.rerun()
    if event.get('kind') == 'circuit' and event.get('value') in {c['slug'] for c in facts}:
        if series == 'DTM':
            st.switch_page(pages['DTM'], query_params={'year': str(year), 'view': 'circuits', 'circuit': event['value']})
        st.switch_page(pages['Circuits'], query_params={'circuit': event['value']})
