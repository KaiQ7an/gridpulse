"""Small, offline summaries for the landing page; never build full race telemetry here."""

from datetime import UTC, datetime

import pandas as pd

from gridpulse import snapshots
from gridpulse.dtm import data as dtm

F1_PHOTO = {
    'url': 'https://images.ctfassets.net/1fvlg6xqnm65/37RkMYDyiaINawxj6ERovv/84fe31514293e2bb57afd7fc92922989/W17_On_Track_Desktop_Wallpaper_2.jpg?w=960&q=80&fm=webp',
    'source': 'https://www.mercedesamgf1.com/car/2026',
    'credit': 'Mercedes-AMG PETRONAS F1 Team · W17, 2026',
}


def years() -> list[int]:
    current = datetime.now(UTC).year
    saved = {int(p.name) for p in snapshots.SNAPSHOT_DIR.iterdir() if p.is_dir() and p.name.isdigit()} \
        if snapshots.SNAPSHOT_DIR.exists() else set()
    return sorted({y for y in saved | set(dtm.YEARS) if y <= current}, reverse=True)


def weekends(year: int, today: str) -> list[dict]:
    rows = []
    for event in snapshots.races(year).itertuples():
        date = event.EventDate.date().isoformat()
        if date > today:
            continue
        rows.append({'series': 'Formula 1', 'year': year, 'round': int(event.RoundNumber),
                     'title': event.EventName, 'place': event.Location, 'date': date,
                     'key': f'f1-{year}-{event.RoundNumber}', 'page': 'Race replay',
                     'params': {'year': str(year), 'round': str(event.RoundNumber), 'mode': 'replay', 'view': 'Strategy'},
                     'summary': 'Lap replay · telemetry · strategy', 'source': 'Bundled F1 timing snapshot'})
    if year in dtm.YEARS:
        season = dtm.saved(year)
        for event in season['events']:
            races = [s for s in event['sessions'] if s['kind'] == 'race' and s['rows']]
            if not races or event['end'] > today:
                continue
            rows.append({'series': 'DTM', 'year': year, 'round': event['round'], 'title': event['name'],
                         'place': event['country'], 'date': event['end'], 'key': f'dtm-{year}-{event["round"]}',
                         'page': 'DTM', 'params': {'year': str(year), 'view': 'weekend', 'event': str(event['round']),
                                                  'session': 'race-1'},
                         'summary': f'{len(races)} races · qualifying · weekend overview',
                         'source': f'Official DTM snapshot · fetched {season["fetched_at"][:10]}',
                         'races': races})
    return sorted(rows, key=lambda r: (r['date'], r['series'], r['round']), reverse=True)


def podiums(event: dict) -> list[tuple[str, list[str]]]:
    if event['series'] == 'DTM':
        return [(race['name'], [r['name'] for r in sorted(race['rows'], key=lambda r: r['position'] or 999)
                               if r['position'] in (1, 2, 3) and not r['status']])
                for race in event['races']]
    path = snapshots.SNAPSHOT_DIR / str(event['year']) / f'{event["round"]:02d}-R' / 'results.parquet'
    results = pd.read_parquet(path).sort_values('Position')
    top = results[results.Position.isin([1, 2, 3])]
    return [('Grand Prix', [str(r['FullName']) if pd.notna(r.get('FullName')) and r.get('FullName')
                            else str(r['Abbreviation']) for _, r in top.iterrows()])]


def resume_targets(state: dict) -> list[dict]:
    targets = []
    saved = state.get('saved_replay', {})
    if saved.get('race_year') and saved.get('race_pick'):
        year, round_ = saved['race_year'], saved['race_pick']
        meta = snapshots.race_metadata(year, round_, 'S' if saved.get('race_session') == 'Sprint' else 'R') or {}
        params = {'year': str(year), 'round': str(round_), 'lap': str(saved.get('lap', 1)),
                  'drivers': ','.join(saved.get('focus', [])), 'view': saved.get('view', 'Gaps')}
        if saved.get('race_session') == 'Sprint':
            params['session'] = 'sprint'
        if saved.get('no_spoilers'):
            params['mode'] = 'replay'
        targets.append({'series': 'Formula 1', 'title': meta.get('event_name', f'{year} · Round {round_}'),
                        'detail': f'Lap {saved.get("lap", 1)} · {saved.get("view", "Gaps")} · {year}',
                        'page': 'Race replay', 'params': params})
    saved = state.get('dtm_saved', {})
    if saved.get('dtm_year'):
        params = {'year': str(saved['dtm_year']), 'view': saved.get('dtm_view', 'championship')}
        fields = {'weekend': ('event', 'session'), 'drivers': ('driver',), 'teams': ('team',),
                  'circuits': ('circuit', 'region'), 'compare': ('drivers',)}
        keys = {'driver': 'dtm_profile', 'drivers': 'dtm_drivers'}
        for field in fields.get(params['view'], ()):
            value = saved.get(keys.get(field, 'dtm_' + field))
            if value is not None:
                params[field] = ','.join(value) if isinstance(value, list) else str(value)
        targets.append({'series': 'DTM', 'title': 'Your DTM workspace',
                        'detail': f'{saved["dtm_year"]} · {params["view"].replace("weekend", "Race weekend").title()}',
                        'page': 'DTM', 'params': params})
    return targets
