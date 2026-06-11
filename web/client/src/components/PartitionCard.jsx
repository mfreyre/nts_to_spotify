import usePersistentState from '../usePersistentState.js';

export default function PartitionCard({ onRun }) {
  const [platform, setPlatform] = usePersistentState('nts.partition.platform', 'spotify');
  const [link, setLink] = usePersistentState('nts.partition.link', '');
  const [parts, setParts] = usePersistentState('nts.partition.parts', '2');

  const run = () => {
    const value = link.trim();
    if (!value) {
      alert('Please paste a playlist link');
      return;
    }
    const n = Number(parts);
    if (!Number.isInteger(n) || n < 2) {
      alert('Number of partitions must be a whole number of at least 2');
      return;
    }
    onRun('/api/run/partition', { platform, link: value, parts: n }, { service: 'Spotify' });
  };

  return (
    <section className="card card-cyan">
      <h2>partition a playlist</h2>
      <div className="field">
        <label>platform</label>
        <div className="radio-group">
          <label>
            <input
              type="radio"
              name="partition-platform"
              value="spotify"
              checked={platform === 'spotify'}
              onChange={() => setPlatform('spotify')}
            />
            {' '}Spotify
          </label>
          <label style={{ opacity: 0.4 }}>
            <input type="radio" name="partition-platform" value="youtube" disabled />
            {' '}YouTube (coming soon)
          </label>
        </div>
      </div>
      <div className="field">
        <label htmlFor="partition-link">playlist link</label>
        <input
          type="text"
          id="partition-link"
          placeholder="https://open.spotify.com/playlist/..."
          value={link}
          onChange={(e) => setLink(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="partition-parts">number of partitions</label>
        <input
          type="number"
          id="partition-parts"
          min="2"
          max="100"
          step="1"
          value={parts}
          onChange={(e) => setParts(e.target.value)}
        />
      </div>
      <button onClick={run}>split playlist &rarr;</button>
    </section>
  );
}
