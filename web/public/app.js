const $ = (sel) => document.querySelector(sel);

const authStatusEl = $('#auth-status');
const ytAuthStatusEl = $('#yt-auth-status');
const csvSelect = $('#csv-select');
const logEl = $('#log');
const jobStatusEl = $('#job-status');
const stopBtn = $('#stop-job');
const clearBtn = $('#clear-log');
const connectBtn = $('#connect-spotify');
const connectYtBtn = $('#connect-youtube');
const runPlaylistBtn = $('#run-playlist');
const runNtsBtn = $('#run-nts');
const refreshCsvsBtn = $('#refresh-csvs');
const ytRadio = $('#yt-radio');
const platformRadios = document.querySelectorAll('input[name="platform"]');

let currentJobId = null;
let currentSource = null;

// ---------- Auth status ----------

async function refreshAuth() {
  try {
    const r = await fetch('/api/auth/status');
    const d = await r.json();
    if (d.authenticated) {
      authStatusEl.textContent = 'Spotify connected';
      authStatusEl.className = 'auth ok';
      connectBtn.textContent = 'Reconnect Spotify';
    } else {
      authStatusEl.textContent = 'Not connected to Spotify';
      authStatusEl.className = 'auth bad';
      connectBtn.textContent = 'Connect Spotify';
    }
  } catch {
    authStatusEl.textContent = 'Auth check failed';
    authStatusEl.className = 'auth bad';
  }
}

connectBtn.addEventListener('click', () => {
  window.location.href = '/api/auth/spotify';
});

// ---------- YouTube auth status ----------

async function refreshYtAuth() {
  try {
    const r = await fetch('/api/auth/yt-status');
    const d = await r.json();
    if (!d.configured) {
      ytAuthStatusEl.textContent = 'YouTube not configured';
      ytAuthStatusEl.className = 'auth disabled';
      ytRadio.disabled = true;
      ytRadio.parentElement.style.opacity = '0.4';
      return;
    }
    if (d.authenticated) {
      ytAuthStatusEl.textContent = 'YouTube connected';
      ytAuthStatusEl.className = 'auth ok';
      connectYtBtn.textContent = 'Reconnect YouTube';
    } else {
      ytAuthStatusEl.textContent = 'Not connected to YouTube';
      ytAuthStatusEl.className = 'auth bad';
      connectYtBtn.textContent = 'Connect YouTube';
    }
  } catch {
    ytAuthStatusEl.textContent = 'YT auth check failed';
    ytAuthStatusEl.className = 'auth bad';
  }
}

connectYtBtn.addEventListener('click', () => {
  window.location.href = '/api/auth/youtube';
});

// ---------- Platform toggle ----------

function getSelectedPlatform() {
  return document.querySelector('input[name="platform"]:checked').value;
}

function updatePlatformUI() {
  const platform = getSelectedPlatform();
  if (platform === 'youtube') {
    connectBtn.style.display = 'none';
    connectYtBtn.style.display = '';
  } else {
    connectBtn.style.display = '';
    connectYtBtn.style.display = 'none';
  }
}

platformRadios.forEach((r) => r.addEventListener('change', updatePlatformUI));
updatePlatformUI();

// ---------- CSV listing ----------

async function loadCsvs() {
  csvSelect.innerHTML = '<option>Loading...</option>';
  try {
    const r = await fetch('/api/csvs');
    const d = await r.json();
    csvSelect.innerHTML = '';
    if (!d.files.length) {
      csvSelect.innerHTML = '<option value="">(no CSVs found)</option>';
      return;
    }
    for (const f of d.files) {
      const opt = document.createElement('option');
      opt.value = f.path;
      const kb = (f.size / 1024).toFixed(1);
      opt.textContent = `${f.path}  (${kb} KB)`;
      csvSelect.appendChild(opt);
    }
  } catch (e) {
    csvSelect.innerHTML = `<option value="">Error: ${e.message}</option>`;
  }
}

refreshCsvsBtn.addEventListener('click', loadCsvs);

// ---------- Log panel ----------

function appendLog(stream, line) {
  const cls = classifyLine(stream, line);
  const span = document.createElement('span');
  if (cls) span.className = cls;
  span.textContent = line + '\n';
  logEl.appendChild(span);
  logEl.scrollTop = logEl.scrollHeight;
}

function classifyLine(stream, line) {
  if (stream === 'stderr') return 'stderr';
  if (/\bFOUND\b/.test(line)) return 'found';
  if (/\bNOT FOUND\b/.test(line)) return 'missing';
  if (/^\s*---/.test(line)) return 'progress';
  return '';
}

clearBtn.addEventListener('click', () => {
  logEl.textContent = '';
});

// ---------- Job streaming ----------

function setJobStatus(text, cls = '') {
  jobStatusEl.textContent = text;
  jobStatusEl.className = cls;
}

function streamJob(jobId) {
  currentJobId = jobId;
  stopBtn.disabled = false;
  setJobStatus('running...', 'running');

  if (currentSource) currentSource.close();
  const src = new EventSource(`/api/jobs/${jobId}/stream`);
  currentSource = src;

  src.addEventListener('line', (e) => {
    const { stream, line } = JSON.parse(e.data);
    appendLog(stream, line);
  });

  src.addEventListener('done', (e) => {
    const { exitCode } = JSON.parse(e.data);
    if (exitCode === 0) {
      setJobStatus('done');
    } else {
      setJobStatus(`exited with code ${exitCode}`, 'failed');
    }
    stopBtn.disabled = true;
    src.close();
    currentSource = null;
    currentJobId = null;
  });

  src.addEventListener('error', () => {
    // SSE will auto-retry; if we're done, server closed the stream already.
  });
}

stopBtn.addEventListener('click', async () => {
  if (!currentJobId) return;
  await fetch(`/api/jobs/${currentJobId}/stop`, { method: 'POST' });
});

// ---------- NTS form ----------

const modeRadios = document.querySelectorAll('input[name="mode"]');
const ntsInput = $('#nts-input');
const ntsInputLabel = $('#nts-input-label');
const outputField = $('#output-field');
const ntsOutput = $('#nts-output');

function updateNtsForm() {
  const mode = document.querySelector('input[name="mode"]:checked').value;
  if (mode === 'episode') {
    ntsInputLabel.textContent = 'Episode URL';
    ntsInput.placeholder = 'https://www.nts.live/shows/56-djs/episodes/...';
    outputField.style.display = '';
  } else if (mode === 'show') {
    ntsInputLabel.textContent = 'Show slug';
    ntsInput.placeholder = 'the-breakfast-show-flo';
    outputField.style.display = '';
  } else {
    ntsInputLabel.textContent = 'Show slug or URL';
    ntsInput.placeholder = 'the-breakfast-show-flo';
    outputField.style.display = 'none';
  }
}
modeRadios.forEach((r) => r.addEventListener('change', updateNtsForm));
updateNtsForm();

runNtsBtn.addEventListener('click', async () => {
  const mode = document.querySelector('input[name="mode"]:checked').value;
  const input = ntsInput.value.trim();
  const output = ntsOutput.value.trim();
  if (!input) {
    alert('Please enter a URL or show slug');
    return;
  }
  let endpoint, body;
  if (mode === 'episode') {
    endpoint = '/api/run/episode-to-csv';
    body = { url: input };
    if (output) body.output = output;
  } else if (mode === 'show') {
    endpoint = '/api/run/show-to-csv';
    body = { slug: input };
    if (output) body.output = output;
  } else {
    endpoint = '/api/run/show-to-csvs';
    body = { slug: input };
  }
  try {
    const r = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (!r.ok) {
      alert(d.error || 'Failed to start job');
      return;
    }
    logEl.textContent = '';
    streamJob(d.jobId);
    // After job completes, refresh CSV list so it shows up in dropdown.
    const watcher = setInterval(() => {
      if (!currentJobId) {
        clearInterval(watcher);
        loadCsvs();
      }
    }, 1000);
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
});

// ---------- Playlist form (Spotify or YouTube) ----------

runPlaylistBtn.addEventListener('click', async () => {
  const platform = getSelectedPlatform();
  const csv = csvSelect.value;
  const name = $('#playlist-name').value.trim();
  const description = $('#playlist-desc').value.trim();
  if (!csv) {
    alert('Please select a CSV');
    return;
  }
  if (!name) {
    alert('Please enter a playlist name');
    return;
  }
  const endpoint = platform === 'youtube' ? '/api/run/youtube' : '/api/run/spotify';
  try {
    const r = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ csv, name, description }),
    });
    const d = await r.json();
    if (!r.ok) {
      if (r.status === 401) {
        const svc = platform === 'youtube' ? 'YouTube' : 'Spotify';
        alert(`Not connected to ${svc}. Click "Connect ${svc}" first.`);
      } else {
        alert(d.error || 'Failed to start job');
      }
      return;
    }
    logEl.textContent = '';
    streamJob(d.jobId);
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
});

// ---------- Init ----------

refreshAuth();
refreshYtAuth();
loadCsvs();

// If we just came back from the Spotify OAuth callback, strip the query param.
if (new URLSearchParams(location.search).get('auth') === 'ok') {
  history.replaceState(null, '', '/');
  refreshAuth();
}

// If we just came back from the YouTube OAuth callback, auto-select YouTube.
if (new URLSearchParams(location.search).get('ytauth') === 'ok') {
  history.replaceState(null, '', '/');
  refreshYtAuth();
  const ytOpt = document.querySelector('input[name="platform"][value="youtube"]');
  if (ytOpt && !ytOpt.disabled) {
    ytOpt.checked = true;
    updatePlatformUI();
  }
}
