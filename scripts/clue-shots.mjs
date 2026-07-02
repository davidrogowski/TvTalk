// Screenshot clue 4 (blurred title) and clue 5 (initials + type).
import path from 'node:path';
import { ROOT, startServer, launch } from './_harness.mjs';

const out = path.join(ROOT, '.superpowers', 'shots');
const { server, base } = await startServer();
const browser = await launch();
for (const stage of [3, 4]) {
  const page = await browser.newPage({ viewport: { width: 390, height: 900 } });
  await page.goto(`${base}/clockthequote?day=6`, { waitUntil: 'networkidle' });
  await page.evaluate(s => { stage = s; render(); }, stage);
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(out, `clue${stage + 1}-mobile.png`), fullPage: true });
  await page.close();
}
await browser.close(); server.close(); console.log('clue shots written');
