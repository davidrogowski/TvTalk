// Verify the How-to-Play overlay: visuals + first-visit caching behavior.
// Usage: node scripts/verify-howto.mjs
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, startServer, launch, report } from './_harness.mjs';

const outDir = path.join(ROOT, '.superpowers', 'shots');
fs.mkdirSync(outDir, { recursive: true });

const { server, base } = await startServer();
const URL = `${base}/clockthequote?day=2`;
const isShown = (page) => page.evaluate(() => document.getElementById('howto-ov').classList.contains('show'));
const seenFlag = (page) => page.evaluate(() => { try { return localStorage.getItem('ctq_howto_seen'); } catch { return 'ERR'; } });

const browser = await launch();
const checks = [];

// --- visual: fresh device, desktop + mobile ---
for (const s of [{name:'desktop',w:900,h:1300},{name:'mobile',w:390,h:844}]) {
  const ctx = await browser.newContext({ viewport: { width: s.w, height: s.h } });
  const page = await ctx.newPage();
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(300);
  checks.push([`first-visit auto-shows (${s.name})`, await isShown(page) === true]);
  await page.screenshot({ path: path.join(outDir, `howto-${s.name}.png`), fullPage: true });
  await ctx.close();
}

// --- behavior: one persistent context across reloads ---
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await ctx.newPage();
await page.goto(URL, { waitUntil: 'networkidle' });
await page.waitForTimeout(200);
checks.push(['fresh load shows modal', await isShown(page) === true]);
checks.push(['flag unset before dismiss', await seenFlag(page) === null]);

await page.click('#howto-got');
await page.waitForTimeout(150);
checks.push(['Got it hides modal', await isShown(page) === false]);
checks.push(['flag set after dismiss', await seenFlag(page) === '1']);

// reload same context — should NOT auto-show
await page.goto(URL, { waitUntil: 'networkidle' });
await page.waitForTimeout(200);
checks.push(['reload does NOT auto-show', await isShown(page) === false]);

// ? button reopens
await page.click('#helpbtn');
await page.waitForTimeout(150);
checks.push(['? button reopens', await isShown(page) === true]);

// backdrop click dismisses
await page.mouse.click(10, 10);
await page.waitForTimeout(150);
checks.push(['backdrop click dismisses', await isShown(page) === false]);

// Esc reopens? no — Esc only closes. reopen then Esc.
await page.click('#helpbtn');
await page.waitForTimeout(120);
await page.keyboard.press('Escape');
await page.waitForTimeout(150);
checks.push(['Esc closes', await isShown(page) === false]);

await ctx.close();
await browser.close();
server.close();
console.log(`shots in ${outDir}/howto-*.png`);
report(checks);
