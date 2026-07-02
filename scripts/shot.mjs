// Headless screenshots of clockthequote.html — play + result, desktop + mobile.
// Usage: node scripts/shot.mjs <label>   (e.g. "before" / "after")
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, startServer, launch } from './_harness.mjs';

const label = process.argv[2] || 'shot';
const outDir = path.join(ROOT, '.superpowers', 'shots');
fs.mkdirSync(outDir, { recursive: true });

const { server, base } = await startServer();
const browser = await launch();
const shots = [
  { name: 'play-desktop', w: 900, h: 1300, result: false },
  { name: 'play-mobile',  w: 390, h: 844,  result: false },
  { name: 'result-desktop', w: 900, h: 1300, result: true },
  { name: 'result-mobile',  w: 390, h: 844,  result: true },
];
for (const s of shots) {
  const page = await browser.newPage({ viewport: { width: s.w, height: s.h } });
  await page.goto(`${base}/clockthequote?day=2`, { waitUntil: 'networkidle' });
  if (s.result) {
    await page.evaluate(() => { solvedStage = 1; finished = true; renderResult(); });
  }
  await page.waitForTimeout(250);
  await page.screenshot({ path: path.join(outDir, `${label}-${s.name}.png`), fullPage: true });
  await page.close();
}
await browser.close();
server.close();
console.log('shots written to', outDir);
