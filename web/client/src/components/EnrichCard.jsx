import usePersistentState from '../usePersistentState.js';

// CSVs exported by the enrich job land here (see /api/run/enrich).
const EXPORT_DIR = '.scratch/enriched/';

export default function EnrichCard({ csvFiles, onRun }) {
  const [link, setLink] = usePersistentState('nts.enrich.link', '');
  const [skipDetails, setSkipDetails] = usePersistentState('nts.enrich.skipDetails', false);
  const [previewFallback, setPreviewFallback] = usePersistentState('nts.enrich.previewFallback', true);

  const exports_ = csvFiles.filter((f) => f.path.startsWith(EXPORT_DIR));

  const run = () => {
    const value = link.trim();
    if (!value) {
      alert('Please paste a playlist link');
      return;
    }
    onRun(
      '/api/run/enrich',
      { link: value, skipDetails, noPreviewFallback: !previewFallback },
      { refreshCsvs: true },
    );
  };

  return (
    <section className="card card-cyan">
      <h2>export enriched csv</h2>
      <p className="hint">
        turns a playlist into a csv with valence, energy, danceability, bpm,
        camelot key, genres and label — audio features via ReccoBeats (Spotify
        stopped sharing them with small apps)
      </p>
      <div className="field">
        <label htmlFor="enrich-link">playlist link</label>
        <input
          type="text"
          id="enrich-link"
          placeholder="https://open.spotify.com/playlist/..."
          value={link}
          onChange={(e) => setLink(e.target.value)}
        />
      </div>
      <div className="field">
        <label className="checkbox-line">
          <input
            type="checkbox"
            checked={previewFallback}
            onChange={(e) => setPreviewFallback(e.target.checked)}
          />
          {' '}analyze preview clips for tracks ReccoBeats doesn&apos;t know (slower, much better coverage)
        </label>
        <label className="checkbox-line">
          <input
            type="checkbox"
            checked={skipDetails}
            onChange={(e) => setSkipDetails(e.target.checked)}
          />
          {' '}skip genres &amp; label lookups (faster on big playlists)
        </label>
      </div>
      <button onClick={run}>generate csv &rarr;</button>

      {exports_.length > 0 && (
        <div className="field" style={{ marginTop: '1rem' }}>
          <label>exported csvs</label>
          <ul className="export-list">
            {exports_.map((f) => (
              <li key={f.path}>
                <a href={`/api/download?path=${encodeURIComponent(f.path)}`}>
                  {f.path.slice(EXPORT_DIR.length)}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
