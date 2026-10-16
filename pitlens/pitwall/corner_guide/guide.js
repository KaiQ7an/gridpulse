'use strict';
const svgNS = 'http://www.w3.org/2000/svg';
const $ = id => document.getElementById(id);
const points = rows => rows.map(p => p.join(',')).join(' ');
let tour = null, args = null, identity = '', lastRequested = null;
let selected = 0, position = 0, pinned = {kind: 'corner', index: 0};
let playing = false, frame = null, lastTick = null, lastSample = -1, sequence = 0;

function send(type, extra = {}) {
  parent.postMessage({isStreamlitMessage: true, type, ...extra}, '*');
}
function resize() {
  send('streamlit:setFrameHeight', {height: document.body.scrollHeight + 5});
}
function metric(id, value) { $(id).textContent = value == null ? '—' : String(value); }
function mark(index) {
  document.querySelectorAll('.corner').forEach((g, i) => {
    g.classList.toggle('active', i === index);
    g.setAttribute('aria-pressed', String(i === index));
  });
}
function probe(index) {
  const p = tour.samples[index].point;
  $('probe').setAttribute('cx', p[0]);
  $('probe').setAttribute('cy', p[1]);
}
function updateProgress() {
  const percent = Math.round(position / Math.max(1, tour.samples.length - 1) * 100);
  $('progress').value = Math.round(position);
  $('progress').setAttribute('aria-valuetext', percent + '% of sampled lap');
  $('progress-label').textContent = percent + '%';
}
function pause() {
  playing = false;
  cancelAnimationFrame(frame);
  lastTick = null;
  $('play').textContent = position > 0 && position < (tour?.samples.length || 1) - 1 ? '▶ Resume tour' : '▶ Tour lap';
  $('play').setAttribute('aria-label', 'Play reference lap tour');
  $('detail').setAttribute('aria-live', 'polite');
}
function showCorner(index) {
  if (!tour?.corners.length) return;
  const c = tour.corners[index];
  $('title').textContent = c.label + ' · ' + c.name;
  $('kind').textContent = 'Corner reference';
  metric('speed', c.speed); metric('gear', c.gear); metric('brake', c.brake_m);
  $('speed-label').textContent = 'Minimum speed · km/h';
  $('gear-label').textContent = 'Lowest gear';
  $('brake-label').textContent = 'Brake-on approach · m';
  $('note').textContent = tour.telemetry
    ? 'Speed and gear: within ±60 m of the marker. Braking: sampled brake-on distance in the 250 m approach; approximate, not brake pressure.'
    : 'Telemetry is unavailable for this reference. Numbered geometry remains interactive; missing values are shown as —.';
  $('arc').setAttribute('points', points(tour.points.slice(Math.max(0, c.sample - 9), c.sample + 10)));
  probe(c.sample); mark(index);
}
function showSample(index) {
  const s = tour.samples[index];
  $('title').textContent = playing ? 'Reference lap tour' : 'Racing-line sample';
  $('kind').textContent = Math.round(index / Math.max(1, tour.samples.length - 1) * 100) + '% of sampled lap';
  metric('speed', s.speed); metric('gear', s.gear); metric('brake', s.brake == null ? null : s.brake ? 'ON' : 'OFF');
  $('speed-label').textContent = 'Sample speed · km/h';
  $('gear-label').textContent = 'Sample gear';
  $('brake-label').textContent = 'Brake signal';
  $('note').textContent = 'Values from the labelled reference lap. Preview motion follows sampled positions, not real lap time.';
  probe(index);
  $('arc').setAttribute('points', points(tour.points.slice(Math.max(0, index - 8), index + 1)));
  mark(-1);
}
function restorePinned() {
  if (pinned.kind === 'corner') showCorner(pinned.index);
  else showSample(pinned.index);
}
function pinCorner(index, publish = true) {
  pause(); selected = index; position = tour.corners[index].sample;
  pinned = {kind: 'corner', index};
  $('corners').value = index;
  $('copy').disabled = !args.share_path;
  $('copy').textContent = 'Copy ' + tour.corners[index].label + ' link';
  $('copy-status').textContent = '';
  $('copy-url').hidden = true;
  showCorner(index); updateProgress(); pause();
  if (publish) send('streamlit:setComponentValue', {
    value: {corner: tour.corners[index].label, id: Date.now() + ':' + (++sequence)}, dataType: 'json'
  });
}
function moveCorner(offset) {
  if (tour?.corners.length) pinCorner((selected + offset + tour.corners.length) % tour.corners.length);
}
function seek(index) {
  pause(); position = Math.max(0, Math.min(tour.samples.length - 1, index));
  pinned = {kind: 'sample', index: Math.round(position)};
  showSample(pinned.index); updateProgress(); pause();
}
function togglePlayback() {
  if (!tour?.samples.length) return;
  if (playing) { seek(Math.round(position)); return; }
  if (position >= tour.samples.length - 1) position = 0;
  playing = true; lastTick = null; lastSample = -1;
  $('play').textContent = 'Ⅱ Pause tour';
  $('play').setAttribute('aria-label', 'Pause reference lap tour');
  $('detail').setAttribute('aria-live', 'off');
  function tick(now) {
    if (!playing) return;
    if (lastTick != null) position = Math.min(tour.samples.length - 1,
      position + (now - lastTick) / 22000 * Number($('rate').value) * (tour.samples.length - 1));
    lastTick = now;
    const index = Math.round(position);
    if (index !== lastSample) { showSample(index); updateProgress(); lastSample = index; }
    if (position >= tour.samples.length - 1) { seek(tour.samples.length - 1); return; }
    frame = requestAnimationFrame(tick);
  }
  frame = requestAnimationFrame(tick);
}
$('prev').onclick = () => moveCorner(-1);
$('next').onclick = () => moveCorner(1);
$('corners').onchange = () => pinCorner(Number($('corners').value));
$('progress').oninput = () => seek(Number($('progress').value));
$('play').onclick = togglePlayback;
$('map').addEventListener('keydown', e => {
  if (e.defaultPrevented) return;
  if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
    e.preventDefault(); moveCorner(e.key === 'ArrowRight' ? 1 : -1);
  } else if (e.key === 'Escape') {
    if (pinned.kind === 'corner') pinCorner(pinned.index, false); else seek(pinned.index);
  }
  else if (e.key === ' ' && e.target === $('map')) { e.preventDefault(); togglePlayback(); }
});
$('map').addEventListener('pointermove', e => {
  if (!tour || playing || e.pointerType === 'touch' || e.target.closest('.corner')) return;
  const p = $('map').createSVGPoint(); p.x = e.clientX; p.y = e.clientY;
  const matrix = $('map').getScreenCTM();
  if (!matrix) return;
  const q = p.matrixTransform(matrix.inverse());
  let nearest = 0, minimum = Infinity;
  tour.points.forEach((p, i) => {
    const d = (p[0] - q.x) ** 2 + (p[1] - q.y) ** 2;
    if (d < minimum) { minimum = d; nearest = i; }
  });
  if (minimum < 45 ** 2) showSample(nearest); else restorePinned();
});
$('map').addEventListener('pointerleave', () => { if (!playing && tour) restorePinned(); });
$('copy').onclick = async () => {
  if (!tour?.corners.length || !args.share_path) return;
  // Community Cloud wraps the app in /~/+/. Shared links use its public page URL.
  let base;
  try { base = window.top.location.href; } catch { base = document.referrer; }
  const link = new URL(args.share_path, base);
  link.pathname = link.pathname.replace(/^\/~\/\+\//, '/');
  link.searchParams.set('corner', tour.corners[selected].label);
  try {
    await navigator.clipboard.writeText(link.href);
    $('copy-status').textContent = 'Corner link copied';
    $('copy-url').hidden = true;
  } catch {
    $('copy-url').value = link.href; $('copy-url').hidden = false;
    $('copy-url').focus(); $('copy-url').select();
    $('copy-status').textContent = 'Select and copy this link';
  }
};
function render(nextArgs) {
  args = nextArgs;
  const nextTour = args.tour;
  if (!nextTour?.points?.length || !nextTour.samples?.length) return;
  const nextIdentity = args.name + JSON.stringify(nextTour.reference);
  if (identity !== nextIdentity) {
    pause(); identity = nextIdentity; tour = nextTour; selected = 0; position = 0; lastRequested = null;
    $('map').setAttribute('aria-label', args.name + ' interactive circuit corner guide');
    $('road').setAttribute('points', points(tour.points));
    $('line').setAttribute('points', points(tour.points));
    $('progress').max = tour.samples.length - 1;
    $('corners').replaceChildren(); $('markers').replaceChildren();
    tour.corners.forEach((c, i) => {
      const option = document.createElement('option'); option.value = i; option.textContent = c.label + ' · ' + c.name;
      $('corners').append(option);
      const g = document.createElementNS(svgNS, 'g');
      g.setAttribute('class', 'corner'); g.setAttribute('transform', 'translate(' + c.point + ')');
      g.setAttribute('role', 'button'); g.setAttribute('tabindex', '0'); g.setAttribute('aria-label', c.label + ' ' + c.name);
      const circle = document.createElementNS(svgNS, 'circle'); circle.setAttribute('r', '19');
      const text = document.createElementNS(svgNS, 'text'); text.textContent = c.label; g.append(circle, text);
      g.onpointerenter = () => { if (!playing) showCorner(i); };
      g.onfocus = () => { if (!playing) showCorner(i); };
      g.onclick = () => pinCorner(i);
      g.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pinCorner(i); } };
      $('markers').append(g);
    });
    const p = tour.points[0], q = tour.points[1], dx = q[0] - p[0], dy = q[1] - p[1], length = Math.hypot(dx, dy) || 1;
    $('finish').setAttribute('d', 'M' + (p[0] - dy / length * 10) + ',' + (p[1] + dx / length * 10)
      + ' L' + (p[0] + dy / length * 10) + ',' + (p[1] - dx / length * 10));
    ['prev', 'next', 'corners'].forEach(id => $(id).disabled = !tour.corners.length);
    if (tour.corners.length) pinCorner(0, false);
    else {
      const option = document.createElement('option'); option.textContent = 'Numbered markers unavailable'; $('corners').append(option);
      $('copy').disabled = true; $('hint').textContent = 'Drag the progress bar or hover the racing line. Numbered markers are unavailable.';
      seek(0);
    }
  }
  if (args.selected !== lastRequested) {
    const index = tour.corners.findIndex(c => c.label === args.selected);
    if (index >= 0 && (index !== selected || pinned.kind !== 'corner')) pinCorner(index, false);
    lastRequested = args.selected;
  }
  resize();
}
window.addEventListener('message', e => {
  if (e.source === parent && e.data?.type === 'streamlit:render') render(e.data.args);
});
document.addEventListener('visibilitychange', () => { if (document.hidden && playing) seek(Math.round(position)); });
new ResizeObserver(resize).observe(document.body);
send('streamlit:componentReady', {apiVersion: 1}); resize();
