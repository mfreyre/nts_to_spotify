import CsvCombo from './CsvCombo.jsx';
import UploadZone from './UploadZone.jsx';
import usePersistentState from '../usePersistentState.js';

export default function PlaylistCard({
  platform,
  onPlatformChange,
  spotifyAuth,
  ytAuth,
  csvFiles,
  csvError,
  selectedCsv,
  onSelectCsv,
  onRefreshCsvs,
  onUploaded,
  onConnect,
  onRun,
}) {
  const [name, setName] = usePersistentState('nts.playlist.name', '');
  const [description, setDescription] = usePersistentState('nts.playlist.desc', '');

  const comboPlaceholder = csvError
    ? `Error: ${csvError}`
    : csvFiles.length ? 'search csvs...' : '(no CSVs found)';

  const build = () => {
    if (!selectedCsv) {
      alert('Please select a CSV');
      return;
    }
    if (!name.trim()) {
      alert('Please enter a playlist name');
      return;
    }
    const endpoint = platform === 'youtube' ? '/api/run/youtube' : '/api/run/spotify';
    const service = platform === 'youtube' ? 'YouTube' : 'Spotify';
    onRun(endpoint, { csv: selectedCsv, name: name.trim(), description: description.trim() }, { service });
  };

  return (
    <section className="card card-pink">
      <h2>build the playlist</h2>
      <div className="field">
        <label>platform</label>
        <div className="radio-group">
          <label>
            <input
              type="radio"
              name="platform"
              value="spotify"
              checked={platform === 'spotify'}
              onChange={() => onPlatformChange('spotify')}
            />
            {' '}Spotify
          </label>
          <label style={ytAuth.configured ? undefined : { opacity: 0.4 }}>
            <input
              type="radio"
              name="platform"
              value="youtube"
              disabled={!ytAuth.configured}
              checked={platform === 'youtube'}
              onChange={() => onPlatformChange('youtube')}
            />
            {' '}YouTube
          </label>
        </div>
      </div>
      <div className="field">
        <label htmlFor="csv-search">pick a csv</label>
        <div className="row">
          <CsvCombo
            files={csvFiles}
            value={selectedCsv}
            onSelect={onSelectCsv}
            placeholder={comboPlaceholder}
          />
          <button className="secondary" title="Refresh list" onClick={onRefreshCsvs}>&#8635;</button>
        </div>
      </div>
      <UploadZone onUploaded={onUploaded} />
      <div className="field">
        <label htmlFor="playlist-name">playlist name</label>
        <input
          type="text"
          id="playlist-name"
          placeholder="my nts playlist <3"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="playlist-desc">description (optional)</label>
        <input
          type="text"
          id="playlist-desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      <div className="row">
        <button onClick={build}>build playlist &rarr;</button>
        {platform === 'spotify' ? (
          <button className="secondary" onClick={() => onConnect('spotify')}>
            {spotifyAuth.connected ? 'reconnect spotify' : 'connect spotify'}
          </button>
        ) : (
          <button className="secondary" onClick={() => onConnect('youtube')}>
            {ytAuth.connected ? 'reconnect youtube' : 'connect youtube'}
          </button>
        )}
      </div>
    </section>
  );
}
