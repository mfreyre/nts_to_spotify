import usePersistentState from '../usePersistentState.js';

const MODES = [
  { value: 'episode', label: 'single episode (URL)' },
  { value: 'show', label: 'full show, one combined CSV (slug)' },
  { value: 'shows', label: 'full show, one CSV per episode (slug)' },
];

const INPUT_HINTS = {
  episode: { label: 'episode URL', placeholder: 'https://www.nts.live/shows/56-djs/episodes/...' },
  show: { label: 'show slug', placeholder: 'the-breakfast-show-flo' },
  shows: { label: 'show slug or URL', placeholder: 'the-breakfast-show-flo' },
};

// 'episode' for episode URLs, 'show' for show URLs, null when it's a slug or not an NTS URL
function detectModeFromUrl(value) {
  if (/nts\.live\/shows\/[^/?#]+\/episodes\/./.test(value)) return 'episode';
  if (/nts\.live\/shows\/[^/?#]+/.test(value)) return 'show';
  return null;
}

export default function ScrapeCard({ onRun }) {
  const [mode, setMode] = usePersistentState('nts.scrape.mode', 'episode');
  const [input, setInput] = usePersistentState('nts.scrape.input', '');
  const [output, setOutput] = usePersistentState('nts.scrape.output', '');
  const hint = INPUT_HINTS[mode];
  const hasOutput = mode !== 'shows';

  const handleInput = (value) => {
    setInput(value);
    const detected = detectModeFromUrl(value.trim());
    if (detected === 'episode' && mode !== 'episode') {
      setMode('episode');
    } else if (detected === 'show' && mode === 'episode') {
      // can't tell 'show' vs 'shows' apart from the URL, so only switch away from episode
      setMode('show');
    }
  };

  const run = () => {
    const value = input.trim();
    if (!value) {
      alert('Please enter a URL or show slug');
      return;
    }
    const detected = detectModeFromUrl(value);
    if (mode === 'episode' && detected === 'show') {
      alert('That looks like a show URL, not an episode URL — pick one of the "full show" modes.');
      return;
    }
    if (mode !== 'episode' && detected === 'episode') {
      alert('That looks like a single episode URL — pick the "single episode" mode.');
      return;
    }
    let endpoint, body;
    if (mode === 'episode') {
      endpoint = '/api/run/episode-to-csv';
      body = { url: value };
    } else if (mode === 'show') {
      endpoint = '/api/run/show-to-csv';
      body = { slug: value };
    } else {
      endpoint = '/api/run/show-to-csvs';
      body = { slug: value };
    }
    if (hasOutput && output.trim()) body.output = output.trim();
    onRun(endpoint, body, { refreshCsvs: true });
  };

  return (
    <section className="card card-lime">
      <h2>scrape nts</h2>
      <div className="field">
        <label>mode</label>
        <div className="radio-group">
          {MODES.map((m) => (
            <label key={m.value}>
              <input
                type="radio"
                name="mode"
                value={m.value}
                checked={mode === m.value}
                onChange={() => setMode(m.value)}
              />
              {' '}{m.label}
            </label>
          ))}
        </div>
      </div>
      <div className="field">
        <label htmlFor="nts-input">{hint.label}</label>
        <input
          type="text"
          id="nts-input"
          placeholder={hint.placeholder}
          value={input}
          onChange={(e) => handleInput(e.target.value)}
        />
      </div>
      {hasOutput && (
        <div className="field">
          <label htmlFor="nts-output">output filename (optional)</label>
          <input
            type="text"
            id="nts-output"
            placeholder="auto-generated if empty"
            value={output}
            onChange={(e) => setOutput(e.target.value)}
          />
        </div>
      )}
      <button onClick={run}>generate csv &rarr;</button>
    </section>
  );
}
