import { useRef, useState } from 'react';

const MAX_BYTES = 10 * 1024 * 1024;

export default function UploadZone({ onUploaded }) {
  const [dragover, setDragover] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [bar, setBar] = useState(null); // { pct, error } or null
  const [status, setStatus] = useState(null); // { cls, text } or null
  const fileRef = useRef(null);
  const hideTimerRef = useRef(null);

  const upload = (file) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setStatus({ cls: 'error', text: `✗ "${file.name}" is not a .csv file` });
      return;
    }
    if (file.size > MAX_BYTES) {
      setStatus({ cls: 'error', text: `✗ "${file.name}" is too large (max 10 MB)` });
      return;
    }

    clearTimeout(hideTimerRef.current);
    setStatus(null);
    setBar({ pct: 0, error: false });
    setUploading(true);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/api/upload-csv?filename=${encodeURIComponent(file.name)}`);

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        setBar({ pct: Math.round((e.loaded / e.total) * 100), error: false });
      }
    });

    const finish = () => {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    };

    const showError = (message) => {
      setBar({ pct: 100, error: true });
      setStatus({ cls: 'error', text: `✗ upload failed: ${message}` });
      finish();
    };

    xhr.addEventListener('load', async () => {
      let d = {};
      try { d = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) {
        setBar({ pct: 100, error: false });
        const kb = (d.size / 1024).toFixed(1);
        setStatus({ cls: 'ok', text: `✓ uploaded ${d.path} (${kb} KB) — selected below` });
        await onUploaded(d.path);
        finish();
        hideTimerRef.current = setTimeout(() => setBar(null), 1200);
      } else {
        showError(d.error || `server returned ${xhr.status}`);
      }
    });
    xhr.addEventListener('error', () => showError('network error — is the server running?'));
    xhr.addEventListener('timeout', () => showError('timed out'));

    xhr.setRequestHeader('Content-Type', 'text/csv');
    xhr.send(file);
  };

  return (
    <div className="field">
      <label>or upload your own</label>
      <div
        className={`dropzone${dragover ? ' dragover' : ''}${uploading ? ' uploading' : ''}`}
        tabIndex={0}
        onClick={() => fileRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileRef.current?.click();
          }
        }}
        onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
        onDragLeave={() => setDragover(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragover(false);
          if (e.dataTransfer.files.length) upload(e.dataTransfer.files[0]);
        }}
      >
        drag a .csv here or click to browse
        <input
          type="file"
          ref={fileRef}
          accept=".csv,text/csv"
          hidden
          onChange={(e) => {
            if (e.target.files.length) upload(e.target.files[0]);
          }}
        />
      </div>
      {bar && (
        <div className="upload-progress">
          <div
            className={`upload-bar${bar.error ? ' error' : ''}`}
            style={{ width: `${bar.pct}%` }}
          />
        </div>
      )}
      {status && <div className={`upload-status ${status.cls}`}>{status.text}</div>}
    </div>
  );
}
