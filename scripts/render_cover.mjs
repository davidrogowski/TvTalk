// Regenerates scripts/cover_tvtalk.jpg — the album art embedded in every clip.
// Renders icon-tvtalk.svg (the big red button) on the site's backdrop.
//
//   node scripts/render_cover.mjs
//
// Needs the Nunito webfont, so it must run online (the SVG @imports it).

import { chromium } from 'playwright';
import { readFileSync } from 'fs';
import { execFileSync } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'scripts', 'cover_tvtalk.jpg');
const PNG = join(ROOT, 'scripts', '.cover_tvtalk.png');
const SIZE = 400;     // art size embedded in the mp3s
const RENDER = 1200;  // render big, downscale for clean edges

const svg = readFileSync(join(ROOT, 'icon-tvtalk.svg'), 'utf8');

const html = `<!doctype html><meta charset="utf-8">
<style>
  html,body{margin:0;padding:0;width:${RENDER}px;height:${RENDER}px;overflow:hidden}
  body{
    background: radial-gradient(ellipse at center, #2a0a0a 0%, #0a0000 70%);
    display:flex;align-items:center;justify-content:center;
  }
  svg{width:${Math.round(RENDER * 0.8)}px;height:${Math.round(RENDER * 0.8)}px;display:block}
</style>
${svg}`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: RENDER, height: RENDER } });
await page.setContent(html, { waitUntil: 'networkidle' });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(400);
await page.screenshot({ path: PNG });
await browser.close();

execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', PNG,
  '-vf', `scale=${SIZE}:${SIZE}:flags=lanczos`, '-q:v', '6', OUT]);
execFileSync('rm', [PNG]);
console.log(`wrote ${OUT}`);
