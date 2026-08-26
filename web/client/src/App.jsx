import { useCallback, useEffect, useRef, useState } from 'react';
import { NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import ScrapeCard from './components/ScrapeCard.jsx';
import PlaylistCard from './components/PlaylistCard.jsx';
import PartitionCard from './components/PartitionCard.jsx';
import DedupCard from './components/DedupCard.jsx';
import EnrichCard from './components/EnrichCard.jsx';
import LogPanel from './components/LogPanel.jsx';
import usePersistentState from './usePersistentState.js';

const PAGES = [
  { to: '/scrape', label: 'scrape nts' },
  { to: '/build', label: 'build playlist' },
  { to: '/partition', label: 'partition' },
  { to: '/dedupe', label: 'de-dupe' },
  { to: '/enrich', label: 'enrich csv' },
];

export default function App() {
  const navigate = useNavigate();

  // The OAuth round-trip lands us on "/?auth=ok"; capture the query during the
  // first render, before the router (or our own cleanup) can strip it.
  const initialSearch = useRef(window.location.search);

  // ---------- Hamburger nav ----------

  const [navOpen, setNavOpen] = useState(false);

  // ---------- Auth status ----------

  const [spotifyAuth, setSpotifyAuth] = useState({
    cls: 'pending', label: 'checking spotify...', connected: false,
  });
  const [ytAuth, setYtAuth] = useState({
    cls: 'pending', label: 'checking youtube...', configured: true, connected: false,
  });

  const refreshSpotifyAuth = useCallback(async () => {
    try {
      const d = await (await fetch('/api/auth/status')).json();
      setSpotifyAuth(d.authenticated
        ? { cls: 'ok', label: 'Spotify connected', connected: true }
        : { cls: 'bad', label: 'Not connected to Spotify', connected: false });
      return d;
    } catch {
      setSpotifyAuth({ cls: 'bad', label: 'Auth check failed', connected: false });
      return {};
    }
  }, []);

  const refreshYtAuth = useCallback(async () => {
    try {
      const d = await (await fetch('/api/auth/yt-status')).json();
      if (!d.configured) {
        setYtAuth({ cls: 'disabled', label: 'YouTube not configured', configured: false, connected: false });
      } else if (d.authenticated) {
        setYtAuth({ cls: 'ok', label: 'YouTube connected', configured: true, connected: true });
      } else {
        setYtAuth({ cls: 'bad', label: 'Not connected to YouTube', configured: true, connected: false });
      }
      return d;
    } catch {
      setYtAuth({ cls: 'bad', label: 'YT auth check failed', configured: true, connected: false });
      return {};
    }
  }, []);

  // ---------- Platform ----------

  const [platform, setPlatform] = usePersistentState('nts.platform', 'spotify');

  // ---------- CSV listing ----------

  const [csvFiles, setCsvFiles] = useState([]);
  const [csvError, setCsvError] = useState('');
  const [selectedCsv, setSelectedCsv] = usePersistentState('nts.selectedCsv', '');

  const loadCsvs = useCallback(async () => {
    setCsvError('');
    try {
      const d = await (await fetch('/api/csvs')).json();
      setCsvFiles(d.files);
      // If the previously selected CSV disappeared, clear the selection.
      setSelectedCsv((cur) => (cur && !d.files.some((f) => f.path === cur) ? '' : cur));
      return d.files;
    } catch (e) {
      setCsvFiles([]);
      setCsvError(e.message);
      return [];
    }
  }, []);

  // ---------- Job streaming + log ----------

  const [logItems, setLogItems] = useState([]);
  const [jobStatus, setJobStatus] = useState({ text: '', cls: '' });
  const [jobRunning, setJobRunning] = useState(false);
  const jobIdRef = useRef(null);
  const sourceRef = useRef(null);
  const nextItemIdRef = useRef(0);
  const afterDoneRef = useRef(null);

  const appendLine = useCallback((stream, line, jobId) => {
    if (stream === 'stdin') {
      // An answer reached the job's stdin (from this tab, another tab, or a
      // replay after reload) — close the ask prompt it was answering.
      const note = ['y', 'yes'].includes(line.trim().toLowerCase()) ? 'add it' : 'skip';
      setLogItems((items) => {
        const idx = items.findLastIndex(
          (it) => it.kind === 'ask' && (it.state === 'open' || it.state === 'sending'),
        );
        if (idx === -1) return items;
        return items.map((it, i) => (i === idx ? { ...it, state: 'answered', note } : it));
      });
      return;
    }
    const id = nextItemIdRef.current++;
    setLogItems((items) => {
      if (stream === 'stdout' && line.startsWith('ASK: ')) {
        const question = line.slice(5).replace(/\s*\(y\/n\)\s*$/, '');
        return [...items, { kind: 'ask', id, jobId, question, state: 'open', note: '' }];
      }
      return [...items, { kind: 'line', id, stream, line }];
    });
  }, []);

  const closeOpenAsks = useCallback(() => {
    setLogItems((items) => items.map((it) => (
      it.kind === 'ask' && it.state === 'open' ? { ...it, state: 'closed' } : it
    )));
  }, []);

  const finishJob = useCallback((src) => {
    src.close();
    if (sourceRef.current === src) sourceRef.current = null;
    jobIdRef.current = null;
    sessionStorage.removeItem('nts.jobId');
    setJobRunning(false);
    const after = afterDoneRef.current;
    afterDoneRef.current = null;
    if (after) after();
  }, []);

  const streamJob = useCallback((jobId) => {
    jobIdRef.current = jobId;
    sessionStorage.setItem('nts.jobId', jobId);
    setLogItems([]);
    setJobRunning(true);
    setJobStatus({ text: 'running...', cls: 'running' });

    if (sourceRef.current) sourceRef.current.close();
    const src = new EventSource(`/api/jobs/${jobId}/stream`);
    sourceRef.current = src;

    src.addEventListener('line', (e) => {
      const { stream, line } = JSON.parse(e.data);
      appendLine(stream, line, jobId);
    });

    src.addEventListener('done', (e) => {
      const { exitCode } = JSON.parse(e.data);
      // Job is over — any unanswered ASK prompts can no longer be answered.
      closeOpenAsks();
      setJobStatus(exitCode === 0
        ? { text: 'done', cls: '' }
        : { text: `exited with code ${exitCode}`, cls: 'failed' });
      finishJob(src);
    });

    src.addEventListener('error', async () => {
      // SSE auto-retries on transient drops. But if the job no longer exists
      // (server restarted — jobs live in memory), give up and lock the UI so
      // stale ASK prompts can't be clicked into a 404.
      if (jobIdRef.current !== jobId) return;
      try {
        const r = await fetch(`/api/jobs/${jobId}`);
        if (r.status === 404) {
          appendLine('stderr', 'job lost — the server restarted, please start again', jobId);
          closeOpenAsks();
          setJobStatus({ text: 'job lost', cls: 'failed' });
          finishJob(src);
        }
      } catch {
        // Server unreachable right now — let SSE keep retrying.
      }
    });
  }, [appendLine, closeOpenAsks, finishJob]);

  const runJob = useCallback(async (endpoint, body, opts = {}) => {
    try {
      const r = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        if (r.status === 401 && opts.service) {
          alert(`Not connected to ${opts.service}. Click "Connect ${opts.service}" first.`);
        } else {
          alert(d.error || 'Failed to start job');
        }
        return;
      }
      afterDoneRef.current = opts.refreshCsvs ? loadCsvs : null;
      streamJob(d.jobId);
    } catch (e) {
      alert(`Error: ${e.message}`);
    }
  }, [loadCsvs, streamJob]);

  const stopJob = useCallback(async () => {
    if (!jobIdRef.current) return;
    await fetch(`/api/jobs/${jobIdRef.current}/stop`, { method: 'POST' });
  }, []);

  const clearLog = useCallback(() => setLogItems([]), []);

  const answerAsk = useCallback(async (ask, value, label) => {
    const update = (patch) => setLogItems((items) => items.map((it) => (
      it.id === ask.id ? { ...it, ...patch } : it
    )));
    update({ state: 'sending' });
    try {
      const r = await fetch(`/api/jobs/${ask.jobId}/input`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: value }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        update({ state: 'closed', note: `could not answer: ${d.error || r.status}` });
        return;
      }
      update({ state: 'answered', note: label });
    } catch (e) {
      update({ state: 'closed', note: `error: ${e.message}` });
    }
  }, []);

  // ---------- Connect (OAuth) ----------

  // Remember the current page so the OAuth round-trip returns here instead of
  // always dumping the user on /build.
  const connect = useCallback((service) => {
    sessionStorage.setItem('nts.returnTo', window.location.pathname);
    window.location.href = service === 'youtube' ? '/api/auth/youtube' : '/api/auth/spotify';
  }, []);

  // ---------- Upload ----------

  const handleUploaded = useCallback(async (path) => {
    await loadCsvs();
    setSelectedCsv(path);
  }, [loadCsvs]);

  // ---------- Init ----------

  useEffect(() => {
    refreshSpotifyAuth();
    loadCsvs();

    // If a job was running before the page navigated away (OAuth round-trip,
    // reload), re-attach to it — the server replays its buffered log lines.
    const savedJob = sessionStorage.getItem('nts.jobId');
    if (savedJob) {
      fetch(`/api/jobs/${savedJob}`)
        .then((r) => {
          if (r.ok) streamJob(savedJob);
          else sessionStorage.removeItem('nts.jobId');
        })
        .catch(() => {});
    }

    const params = new URLSearchParams(initialSearch.current);
    // If we just came back from an OAuth callback, drop the query param by
    // routing back to whatever page the user kicked the connect off from
    // (saved before the redirect; falls back to /build).
    const popReturnTo = () => {
      const back = sessionStorage.getItem('nts.returnTo') || '/build';
      sessionStorage.removeItem('nts.returnTo');
      return back;
    };
    if (params.get('auth') === 'ok') navigate(popReturnTo(), { replace: true });
    refreshYtAuth().then((d) => {
      // Back from the YouTube OAuth callback: auto-select YouTube, then return.
      if (params.get('ytauth') === 'ok') {
        if (d.configured) setPlatform('youtube');
        navigate(popReturnTo(), { replace: true });
      }
    });

    // A drop outside the dropzone would navigate the browser to the file —
    // swallow it so a missed drop doesn't blow away the app.
    const prevent = (e) => e.preventDefault();
    document.addEventListener('dragover', prevent);
    document.addEventListener('drop', prevent);
    return () => {
      document.removeEventListener('dragover', prevent);
      document.removeEventListener('drop', prevent);
    };
    // Bootstrap once on mount. Notably NOT depending on `navigate`: react-router
    // gives it a fresh identity on every location change, so listing it here
    // would re-run this effect after each navigation and re-fire the one-shot
    // OAuth redirect, hijacking every nav click back to the landing page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <div className="bg-blobs" aria-hidden="true">
        <span className="blob b1"></span>
        <span className="blob b2"></span>
        <span className="blob b3"></span>
      </div>

      <header>
        <button
          type="button"
          className={`hamburger${navOpen ? ' open' : ''}`}
          aria-label="Toggle menu"
          aria-expanded={navOpen}
          onClick={() => setNavOpen((o) => !o)}
        >
          <span></span>
          <span></span>
          <span></span>
        </button>
        <h1>
          <span className="logo-main">nts</span>
          <span className="logo-arrow">&#8594;</span>
          <span className="logo-sub">spotify</span>
        </h1>
        <div className="auth-pills">
          <button
            type="button"
            className={`auth auth-btn ${spotifyAuth.cls}`}
            title={spotifyAuth.connected ? 'Reconnect Spotify' : 'Connect Spotify'}
            onClick={() => connect('spotify')}
          >
            {spotifyAuth.cls === 'bad' ? 'connect spotify' : spotifyAuth.label}
          </button>
          {ytAuth.configured ? (
            <button
              type="button"
              className={`auth auth-btn ${ytAuth.cls}`}
              title={ytAuth.connected ? 'Reconnect YouTube' : 'Connect YouTube'}
              onClick={() => connect('youtube')}
            >
              {ytAuth.cls === 'bad' ? 'connect youtube' : ytAuth.label}
            </button>
          ) : (
            <div className={`auth ${ytAuth.cls}`}>{ytAuth.label}</div>
          )}
        </div>
      </header>

      {navOpen && <div className="nav-scrim" onClick={() => setNavOpen(false)} />}
      <nav className={`side-nav${navOpen ? ' open' : ''}`}>
        {PAGES.map((p) => (
          <NavLink
            key={p.to}
            to={p.to}
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            onClick={() => setNavOpen(false)}
          >
            {p.label}
          </NavLink>
        ))}
      </nav>

      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/scrape" replace />} />
          <Route path="/scrape" element={<ScrapeCard onRun={runJob} />} />
          <Route
            path="/build"
            element={(
              <PlaylistCard
                platform={platform}
                onPlatformChange={setPlatform}
                spotifyAuth={spotifyAuth}
                ytAuth={ytAuth}
                csvFiles={csvFiles}
                csvError={csvError}
                selectedCsv={selectedCsv}
                onSelectCsv={setSelectedCsv}
                onRefreshCsvs={loadCsvs}
                onUploaded={handleUploaded}
                onConnect={connect}
                onRun={runJob}
              />
            )}
          />
          <Route path="/partition" element={<PartitionCard onRun={runJob} />} />
          <Route path="/dedupe" element={<DedupCard onRun={runJob} />} />
          <Route path="/enrich" element={<EnrichCard csvFiles={csvFiles} onRun={runJob} />} />
          <Route path="*" element={<Navigate to="/scrape" replace />} />
        </Routes>

        {/* Shared across every page so a running job stays visible while you
            navigate between tools. */}
        <LogPanel
          items={logItems}
          status={jobStatus}
          running={jobRunning}
          onStop={stopJob}
          onClear={clearLog}
          onAnswer={answerAsk}
        />
      </main>
    </>
  );
}
