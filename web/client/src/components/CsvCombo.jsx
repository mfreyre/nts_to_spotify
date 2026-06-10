import { useEffect, useRef, useState } from 'react';

export default function CsvCombo({ files, value, onSelect, placeholder }) {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const wrapRef = useRef(null);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const lastValueRef = useRef(value);

  // Sync the input text with selections committed from outside (an upload,
  // a refresh that dropped the selected file) without stomping on typing.
  useEffect(() => {
    if (value === lastValueRef.current) return;
    lastValueRef.current = value;
    if (value) setQuery(value);
    else if (document.activeElement !== inputRef.current) setQuery('');
  }, [value]);

  useEffect(() => {
    const onDocClick = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  }, []);

  useEffect(() => {
    listRef.current?.querySelector('.active')?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  // With a committed selection in the box, show the full list rather than
  // filtering down to just the selected file.
  const filterText = value && query === value ? '' : query.trim().toLowerCase();
  const matches = filterText
    ? files.filter((f) => f.path.toLowerCase().includes(filterText))
    : files;

  const pick = (path) => {
    lastValueRef.current = path;
    setQuery(path);
    setOpen(false);
    setActive(-1);
    onSelect(path);
  };

  const onChange = (e) => {
    const text = e.target.value;
    setQuery(text);
    setOpen(true);
    setActive(-1);
    // Typing invalidates the previous selection until a new pick is made.
    if (text !== value) {
      lastValueRef.current = '';
      onSelect('');
    }
  };

  const onKeyDown = (e) => {
    if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) setOpen(true);
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((a) => (matches.length ? (a + 1 + matches.length) % matches.length : -1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => (matches.length ? (a - 1 + matches.length) % matches.length : -1));
    } else if (e.key === 'Enter') {
      if (open && active >= 0 && matches[active]) {
        e.preventDefault();
        pick(matches[active].path);
      } else if (open && matches.length === 1) {
        e.preventDefault();
        pick(matches[0].path);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div className="combo" ref={wrapRef}>
      <input
        type="text"
        id="csv-search"
        ref={inputRef}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-controls="csv-options"
        placeholder={placeholder}
        value={query}
        onChange={onChange}
        onFocus={() => { setOpen(true); setActive(-1); }}
        onKeyDown={onKeyDown}
      />
      {open && (
        <ul id="csv-options" className="combo-options" role="listbox" ref={listRef}>
          {matches.length === 0 ? (
            <li className="combo-empty">{files.length ? 'no matches' : 'no CSVs found'}</li>
          ) : (
            matches.map((f, i) => (
              <li
                key={f.path}
                role="option"
                aria-selected={f.path === value}
                className={[
                  f.path === value ? 'selected' : '',
                  i === active ? 'active' : '',
                ].join(' ').trim()}
                onMouseDown={(e) => {
                  e.preventDefault(); // keep focus on the input
                  pick(f.path);
                }}
              >
                {f.path}  ({(f.size / 1024).toFixed(1)} KB)
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
