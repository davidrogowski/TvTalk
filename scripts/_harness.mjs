// Shared harness for the Playwright verify/screenshot scripts (not runnable itself):
// static file server on an ephemeral port + Chrome launcher + pass/fail reporter.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const MIME = { '.html':'text/html', '.js':'text/javascript', '.mp3':'audio/mpeg', '.css':'text/css',
               '.png':'image/png', '.svg':'image/svg+xml' };

// Serve the repo root; ephemeral port so scripts never collide. Returns { server, base }.
export function startServer() {
  const server = http.createServer((req, res) => {
    let p = decodeURIComponent(req.url.split('?')[0]);
    if (p === '/') p = '/index.html';
    if (p === '/clockthequote') p = '/clockthequote.html';
    const fp = path.join(ROOT, p);
    fs.readFile(fp, (e, data) => {
      if (e) { res.writeHead(404); res.end('nf'); return; }
      res.writeHead(200, { 'content-type': MIME[path.extname(fp)] || 'application/octet-stream' });
      res.end(data);
    });
  });
  return new Promise(resolve => server.listen(0, () =>
    resolve({ server, base: `http://localhost:${server.address().port}` })));
}

export const launch = () => chromium.launch({ channel: 'chrome' });

// Print PASS/FAIL per check (+ any collected JS errors) and exit non-zero on failure.
export function report(checks, errs = []) {
  let ok = true;
  for (const [name, pass] of checks) { if (!pass) ok = false; console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}`); }
  console.log(`JS errors: ${errs.length ? errs.join(' | ') : 'none'}`);
  if (errs.length) ok = false;
  console.log(ok ? '\nALL PASS' : '\nSOME FAILED');
  process.exit(ok ? 0 : 1);
}
