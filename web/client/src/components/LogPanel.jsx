import { useEffect, useRef } from 'react';

function classifyLine(stream, line) {
  if (stream === 'stderr') return 'stderr';
  if (/\bNOT FOUND\b/.test(line)) return 'missing';
  if (/\bUNSURE\b/.test(line)) return 'unsure';
  if (/^\s+(matched|closest|best was|->)/.test(line)) return 'detail';
  if (/\bFOUND\b/.test(line)) return 'found';
  if (/^\s*---/.test(line)) return 'progress';
  return '';
}

function LogLine({ stream, line }) {
  const cls = classifyLine(stream, line);
  // Auto-link URLs in log output
  const m = line.match(/(https?:\/\/[^\s]+)/);
  if (!m) return <span className={cls}>{line + '\n'}</span>;
  const url = m[1];
  const idx = line.indexOf(url);
  return (
    <span className={cls}>
      {line.slice(0, idx)}
      <a href={url} target="_blank" rel="noopener noreferrer">{url}</a>
      {line.slice(idx + url.length) + '\n'}
    </span>
  );
}

function AskPrompt({ ask, onAnswer }) {
  const open = ask.state === 'open';
  return (
    <div className="ask">
      <span>
        ? {ask.question}
        {ask.note ? ` [${ask.note}]` : ''}
      </span>
      {ask.state !== 'answered' && (
        <>
          <button className="ask-btn" disabled={!open} onClick={() => onAnswer(ask, 'y', 'add it')}>
            add it
          </button>
          <button className="ask-btn" disabled={!open} onClick={() => onAnswer(ask, 'n', 'skip')}>
            skip
          </button>
        </>
      )}
    </div>
  );
}

export default function LogPanel({ items, status, running, onStop, onClear, onAnswer }) {
  const logRef = useRef(null);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [items]);

  return (
    <section className="card card-dark log-card">
      <div className="log-header">
        <h2>live logs</h2>
        <div className="row">
          <span id="job-status" className={status.cls}>{status.text}</span>
          <button className="secondary" disabled={!running} onClick={onStop}>stop</button>
          <button className="secondary" onClick={onClear}>clear</button>
        </div>
      </div>
      <pre id="log" ref={logRef}>{items.map((it) => (
        it.kind === 'ask'
          ? <AskPrompt key={it.id} ask={it} onAnswer={onAnswer} />
          : <LogLine key={it.id} stream={it.stream} line={it.line} />
      ))}</pre>
    </section>
  );
}
