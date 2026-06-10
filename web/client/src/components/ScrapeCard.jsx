import { useState } from 'react';

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

export default function ScrapeCard({ onRun }) {
  const [mode, setMode] = useState('episode');
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const hint = INPUT_HINTS[mode];
  const hasOutput = mode !== 'shows';

  const run = () => {
    const value = input.trim();
    if (!value) {
      alert('Please enter a URL or show slug');
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
          onChange={(e) => setInput(e.target.value)}
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
