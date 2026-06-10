const express = require('express');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { randomUUID } = require('crypto');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const REPO_ROOT = path.resolve(__dirname, '..');
const PORT = Number(process.env.WEB_PORT || 4200);

const CLIENT_ID = process.env.SPOTIFY_CLIENT_ID;
const CLIENT_SECRET = process.env.SPOTIFY_CLIENT_SECRET;
const REDIRECT_URI = process.env.SPOTIFY_REDIRECT_URI || `http://127.0.0.1:${PORT}/callback`;
const SCOPE = 'playlist-modify-public playlist-modify-private';

if (!CLIENT_ID || !CLIENT_SECRET) {
  console.error('Missing SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET in .env');
  process.exit(1);
}

// YouTube OAuth (optional — server still starts without these)
const YT_CLIENT_ID = process.env.YOUTUBE_CLIENT_ID;
const YT_CLIENT_SECRET = process.env.YOUTUBE_CLIENT_SECRET;
const YT_REDIRECT_URI = process.env.YOUTUBE_REDIRECT_URI || `http://127.0.0.1:${PORT}/yt-callback`;
const YT_SCOPE = 'https://www.googleapis.com/auth/youtube';
const ytConfigured = Boolean(YT_CLIENT_ID && YT_CLIENT_SECRET);
if (!ytConfigured) {
  console.warn('YouTube credentials not set — YouTube features will be disabled.');
}

const CLIENT_DIST = path.join(__dirname, 'client', 'dist');

const app = express();
app.use(express.json());
app.get('/', (req, res, next) => {
  if (!fs.existsSync(path.join(CLIENT_DIST, 'index.html'))) {
    return res
      .status(503)
      .send('Client not built. Run "npm run build" in the web/ directory, then reload.');
  }
  next();
});
app.use(express.static(CLIENT_DIST));

// In-memory single-user token stores.
let tokenStore = { accessToken: null, refreshToken: null, expiresAt: 0 };
let ytTokenStore = { accessToken: null, refreshToken: null, expiresAt: 0 };

// Job registry: jobId -> { proc, lines: [], done: false, clients: Set<res> }.
const jobs = new Map();

// ---------- Spotify OAuth ----------

app.get('/api/auth/spotify', (req, res) => {
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    response_type: 'code',
    redirect_uri: REDIRECT_URI,
    scope: SCOPE,
  });
  res.redirect(`https://accounts.spotify.com/authorize?${params}`);
});

app.get('/callback', async (req, res) => {
  const { code, error } = req.query;
  if (error) {
    return res.status(400).send(`Spotify returned error: ${error}`);
  }
  if (!code) {
    return res.status(400).send('Missing code parameter');
  }
  try {
    const body = new URLSearchParams({
      grant_type: 'authorization_code',
      code,
      redirect_uri: REDIRECT_URI,
    });
    const auth = Buffer.from(`${CLIENT_ID}:${CLIENT_SECRET}`).toString('base64');
    const tokenRes = await fetch('https://accounts.spotify.com/api/token', {
      method: 'POST',
      headers: {
        Authorization: `Basic ${auth}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body,
    });
    if (!tokenRes.ok) {
      const t = await tokenRes.text();
      return res.status(500).send(`Token exchange failed: ${t}`);
    }
    const data = await tokenRes.json();
    tokenStore = {
      accessToken: data.access_token,
      refreshToken: data.refresh_token || tokenStore.refreshToken,
      expiresAt: Date.now() + (data.expires_in - 30) * 1000,
    };
    res.redirect('/?auth=ok');
  } catch (e) {
    res.status(500).send(`OAuth error: ${e.message}`);
  }
});

async function refreshAccessToken() {
  if (!tokenStore.refreshToken) return null;
  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    refresh_token: tokenStore.refreshToken,
  });
  const auth = Buffer.from(`${CLIENT_ID}:${CLIENT_SECRET}`).toString('base64');
  const r = await fetch('https://accounts.spotify.com/api/token', {
    method: 'POST',
    headers: {
      Authorization: `Basic ${auth}`,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body,
  });
  if (!r.ok) return null;
  const d = await r.json();
  tokenStore.accessToken = d.access_token;
  tokenStore.expiresAt = Date.now() + (d.expires_in - 30) * 1000;
  if (d.refresh_token) tokenStore.refreshToken = d.refresh_token;
  return tokenStore.accessToken;
}

async function getValidAccessToken() {
  if (!tokenStore.accessToken) return null;
  if (Date.now() < tokenStore.expiresAt) return tokenStore.accessToken;
  return refreshAccessToken();
}

app.get('/api/auth/status', async (req, res) => {
  const token = await getValidAccessToken();
  res.json({
    authenticated: Boolean(token),
    expiresAt: tokenStore.expiresAt || null,
  });
});

// ---------- YouTube OAuth ----------

app.get('/api/auth/youtube', (req, res) => {
  if (!ytConfigured) return res.status(400).json({ error: 'YouTube not configured' });
  const params = new URLSearchParams({
    client_id: YT_CLIENT_ID,
    response_type: 'code',
    redirect_uri: YT_REDIRECT_URI,
    scope: YT_SCOPE,
    access_type: 'offline',
    prompt: 'consent',
  });
  res.redirect(`https://accounts.google.com/o/oauth2/v2/auth?${params}`);
});

app.get('/yt-callback', async (req, res) => {
  const { code, error } = req.query;
  if (error) return res.status(400).send(`Google returned error: ${error}`);
  if (!code) return res.status(400).send('Missing code parameter');
  try {
    const body = new URLSearchParams({
      grant_type: 'authorization_code',
      code,
      redirect_uri: YT_REDIRECT_URI,
      client_id: YT_CLIENT_ID,
      client_secret: YT_CLIENT_SECRET,
    });
    const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    if (!tokenRes.ok) {
      const t = await tokenRes.text();
      return res.status(500).send(`YouTube token exchange failed: ${t}`);
    }
    const data = await tokenRes.json();
    ytTokenStore = {
      accessToken: data.access_token,
      refreshToken: data.refresh_token || ytTokenStore.refreshToken,
      expiresAt: Date.now() + (data.expires_in - 30) * 1000,
    };
    res.redirect('/?ytauth=ok');
  } catch (e) {
    res.status(500).send(`YouTube OAuth error: ${e.message}`);
  }
});

async function refreshYtAccessToken() {
  if (!ytTokenStore.refreshToken || !ytConfigured) return null;
  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    refresh_token: ytTokenStore.refreshToken,
    client_id: YT_CLIENT_ID,
    client_secret: YT_CLIENT_SECRET,
  });
  const r = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  if (!r.ok) return null;
  const d = await r.json();
  ytTokenStore.accessToken = d.access_token;
  ytTokenStore.expiresAt = Date.now() + (d.expires_in - 30) * 1000;
  if (d.refresh_token) ytTokenStore.refreshToken = d.refresh_token;
  return ytTokenStore.accessToken;
}

async function getValidYtAccessToken() {
  if (!ytTokenStore.accessToken) return null;
  if (Date.now() < ytTokenStore.expiresAt) return ytTokenStore.accessToken;
  return refreshYtAccessToken();
}

app.get('/api/auth/yt-status', async (req, res) => {
  const token = await getValidYtAccessToken();
  res.json({
    configured: ytConfigured,
    authenticated: Boolean(token),
  });
});

// ---------- CSV listing ----------

function listCsvFiles() {
  const scratchDir = path.join(REPO_ROOT, '.scratch');
  const results = [];
  const visit = (dir, relDir) => {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (entry.name.startsWith('.')) continue;
      const abs = path.join(dir, entry.name);
      const rel = relDir ? `${relDir}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        visit(abs, rel);
      } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.csv')) {
        const stat = fs.statSync(abs);
        results.push({ path: `.scratch/${rel}`, size: stat.size, mtime: stat.mtimeMs });
      }
    }
  };
  visit(scratchDir, '');
  results.sort((a, b) => b.mtime - a.mtime);
  return results;
}

app.get('/api/csvs', (req, res) => {
  res.json({ files: listCsvFiles() });
});

// ---------- CSV upload ----------

const UPLOAD_DIR = path.join(REPO_ROOT, '.scratch', 'uploads');
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

// Raw-body upload (no multipart): the file is the request body,
// the filename comes in as a query param.
app.post('/api/upload-csv', (req, res) => {
  const rawName = String(req.query.filename || '');
  const base = path.basename(rawName).replace(/[^\w.\- ]/g, '_').trim();
  if (!base.toLowerCase().endsWith('.csv')) {
    return res.status(400).json({ error: 'Only .csv files are accepted' });
  }

  const declaredSize = Number(req.headers['content-length'] || 0);
  if (declaredSize > MAX_UPLOAD_BYTES) {
    return res.status(413).json({ error: 'File too large (max 10 MB)' });
  }

  fs.mkdirSync(UPLOAD_DIR, { recursive: true });
  let target = path.join(UPLOAD_DIR, base);
  const stem = base.slice(0, -4);
  for (let i = 2; fs.existsSync(target); i++) {
    target = path.join(UPLOAD_DIR, `${stem}-${i}.csv`);
  }

  const out = fs.createWriteStream(target);
  let received = 0;
  let failed = false;
  const fail = (status, message) => {
    if (failed) return;
    failed = true;
    out.destroy();
    fs.unlink(target, () => {});
    if (!res.headersSent) res.status(status).json({ error: message });
  };

  req.on('data', (chunk) => {
    received += chunk.length;
    if (received > MAX_UPLOAD_BYTES) fail(413, 'File too large (max 10 MB)');
  });
  req.on('aborted', () => fail(400, 'Upload aborted'));
  out.on('error', (e) => fail(500, `Could not save file: ${e.message}`));
  out.on('finish', () => {
    if (failed) return;
    if (received === 0) return fail(400, 'File is empty');
    res.json({ path: `.scratch/uploads/${path.basename(target)}`, size: received });
  });
  req.pipe(out);
});

// ---------- Job management ----------

function createJob(proc) {
  const id = randomUUID();
  const job = { proc, lines: [], done: false, exitCode: null, clients: new Set() };
  jobs.set(id, job);

  const broadcast = (event, data) => {
    const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
    for (const client of job.clients) client.write(payload);
  };

  const handleChunk = (buf, stream) => {
    const text = buf.toString('utf-8');
    const parts = text.split(/\r?\n/);
    for (let i = 0; i < parts.length - 1; i++) {
      const line = parts[i];
      job.lines.push({ stream, line });
      broadcast('line', { stream, line });
    }
    // Trailing partial line: append as-is, no newline terminator.
    if (parts[parts.length - 1]) {
      const partial = parts[parts.length - 1];
      job.lines.push({ stream, line: partial });
      broadcast('line', { stream, line: partial });
    }
  };

  proc.stdout.on('data', (b) => handleChunk(b, 'stdout'));
  proc.stderr.on('data', (b) => handleChunk(b, 'stderr'));
  proc.on('close', (code) => {
    job.done = true;
    job.exitCode = code;
    broadcast('done', { exitCode: code });
    for (const client of job.clients) client.end();
    job.clients.clear();
  });
  proc.on('error', (err) => {
    job.lines.push({ stream: 'stderr', line: `spawn error: ${err.message}` });
    broadcast('line', { stream: 'stderr', line: `spawn error: ${err.message}` });
  });

  return id;
}

function spawnPython(args, extraEnv = {}) {
  const env = { ...process.env, PYTHONUNBUFFERED: '1', ...extraEnv };
  const proc = spawn('python3', args, { cwd: REPO_ROOT, env });
  return createJob(proc);
}

// ---------- Script runners ----------

app.post('/api/run/spotify', async (req, res) => {
  const { csv, name, description } = req.body || {};
  if (!csv || !name) {
    return res.status(400).json({ error: 'csv and name are required' });
  }
  const token = await getValidAccessToken();
  if (!token) {
    return res.status(401).json({ error: 'Not authenticated with Spotify' });
  }
  const csvAbs = path.resolve(REPO_ROOT, csv);
  if (!csvAbs.startsWith(REPO_ROOT) || !fs.existsSync(csvAbs)) {
    return res.status(400).json({ error: 'CSV not found in repo' });
  }
  const jobId = spawnPython(
    [
      'spotify_scripts/spotify_v2.py',
      '--csv', csv,
      '--name', name,
      '--description', description || '',
    ],
    { SPOTIFY_ACCESS_TOKEN: token },
  );
  res.json({ jobId });
});

app.post('/api/run/youtube', async (req, res) => {
  if (!ytConfigured) {
    return res.status(400).json({ error: 'YouTube not configured on server' });
  }
  const { csv, name, description } = req.body || {};
  if (!csv || !name) {
    return res.status(400).json({ error: 'csv and name are required' });
  }
  const token = await getValidYtAccessToken();
  if (!token) {
    return res.status(401).json({ error: 'Not authenticated with YouTube' });
  }
  const csvAbs = path.resolve(REPO_ROOT, csv);
  if (!csvAbs.startsWith(REPO_ROOT) || !fs.existsSync(csvAbs)) {
    return res.status(400).json({ error: 'CSV not found in repo' });
  }
  const jobId = spawnPython(
    [
      'spotify_scripts/youtube_v2.py',
      '--csv', csv,
      '--name', name,
      '--description', description || '',
    ],
    { YOUTUBE_ACCESS_TOKEN: token },
  );
  res.json({ jobId });
});

app.post('/api/run/episode-to-csv', (req, res) => {
  const { url, output } = req.body || {};
  if (!url) return res.status(400).json({ error: 'url is required' });
  const args = ['episode_to_csv.py', url];
  if (output) args.push(output);
  const jobId = spawnPython(args);
  res.json({ jobId });
});

app.post('/api/run/show-to-csv', (req, res) => {
  const { slug, output } = req.body || {};
  if (!slug) return res.status(400).json({ error: 'slug is required' });
  const args = ['nts_show_to_csv.py', slug];
  if (output) args.push(output);
  const jobId = spawnPython(args);
  res.json({ jobId });
});

app.post('/api/run/show-to-csvs', (req, res) => {
  const { slug } = req.body || {};
  if (!slug) return res.status(400).json({ error: 'slug is required' });
  const jobId = spawnPython(['show_to_csvs.py', slug]);
  res.json({ jobId });
});

// ---------- Job streaming ----------

app.get('/api/jobs/:id', (req, res) => {
  const job = jobs.get(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job not found' });
  res.json({ done: job.done, exitCode: job.exitCode });
});

app.get('/api/jobs/:id/stream', (req, res) => {
  const job = jobs.get(req.params.id);
  if (!job) return res.status(404).end();

  res.set({
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  });
  res.flushHeaders();

  // Replay buffered lines.
  for (const { stream, line } of job.lines) {
    res.write(`event: line\ndata: ${JSON.stringify({ stream, line })}\n\n`);
  }

  if (job.done) {
    res.write(`event: done\ndata: ${JSON.stringify({ exitCode: job.exitCode })}\n\n`);
    return res.end();
  }

  job.clients.add(res);
  req.on('close', () => job.clients.delete(res));
});

// Forward a line to the job's stdin (used to answer ASK: prompts).
app.post('/api/jobs/:id/input', (req, res) => {
  const job = jobs.get(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job not found' });
  if (job.done || !job.proc.stdin || !job.proc.stdin.writable) {
    return res.status(400).json({ error: 'Job is not running' });
  }
  const text = String((req.body || {}).text ?? '');
  job.proc.stdin.write(text + '\n');
  res.json({ ok: true });
});

app.post('/api/jobs/:id/stop', (req, res) => {
  const job = jobs.get(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job not found' });
  if (!job.done && job.proc) job.proc.kill('SIGTERM');
  res.json({ ok: true });
});

// ---------- Start ----------

app.listen(PORT, () => {
  console.log(`nts-to-spotify web UI running at http://127.0.0.1:${PORT}`);
  console.log(`Spotify redirect URI: ${REDIRECT_URI}`);
});
