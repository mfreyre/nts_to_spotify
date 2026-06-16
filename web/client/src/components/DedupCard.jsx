import usePersistentState from '../usePersistentState.js';

export default function DedupCard({ onRun }) {
  const [platform, setPlatform] = usePersistentState('nts.dedup.platform', 'spotify');
  const [link, setLink] = usePersistentState('nts.dedup.link', '');
  const [nearDuplicates, setNearDuplicates] = usePersistentState('nts.dedup.near', false);

  const run = () => {
    const value = link.trim();
    if (!value) {
      alert('Please paste a playlist link');
      return;
    }
    onRun(
      '/api/run/dedup',
      { platform, link: value, nearDuplicates },
      { service: 'Spotify' },
    );
  };

  return (
    <section className="card card-purple">
      <h2>de-dupe a playlist</h2>
      <div className="field">
        <label>platform</label>
        <div className="radio-group">
          <label>
            <input
              type="radio"
              name="dedup-platform"
              value="spotify"
              checked={platform === 'spotify'}
              onChange={() => setPlatform('spotify')}
            />
            {' '}Spotify
          </label>
          <label style={{ opacity: 0.4 }}>
            <input type="radio" name="dedup-platform" value="youtube" disabled />
            {' '}YouTube (coming soon)
          </label>
        </div>
      </div>
      <div className="field">
        <label htmlFor="dedup-link">playlist link</label>
        <input
          type="text"
          id="dedup-link"
          placeholder="https://open.spotify.com/playlist/..."
          value={link}
          onChange={(e) => setLink(e.target.value)}
        />
      </div>
      <div className="field">
        <label className="checkbox-line">
          <input
            type="checkbox"
            checked={nearDuplicates}
            onChange={(e) => setNearDuplicates(e.target.checked)}
          />
          {' '}also catch near-duplicates (same song, different version) — asks before each
        </label>
      </div>
      <button onClick={run}>remove duplicates &rarr;</button>
    </section>
  );
}
