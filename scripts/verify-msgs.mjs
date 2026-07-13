// Verify the loss-screen quips (failMsg) resolve for every rotation, have an emoji, and no trailing period.
// (Win messages were removed — the result screen now conveys a win via the stats sheet + share strip.)
import { startServer, launch } from './_harness.mjs';

const { server, base } = await startServer();
const browser = await launch();
const page = await browser.newPage();
await page.goto(`${base}/clockthequote?day=1`, { waitUntil: 'networkidle' });
const out = await page.evaluate(() => {
  const fails = []; for (let r = 0; r < 5; r++) { roundNo = r + 1; fails.push(failMsg()); }
  return { fails, failsUnique: new Set(fails).size };
});
let bad = 0;
const check = (m) => {
  const endsPeriod = /\.$/.test(m.trim());
  const hasEmoji = /\p{Extended_Pictographic}/u.test(m);
  if (endsPeriod || !hasEmoji) { bad++; return ' <-- ' + (endsPeriod ? 'PERIOD ' : '') + (!hasEmoji ? 'NO-EMOJI' : ''); }
  return '';
};
console.log(`FAIL-tier  (unique ${out.failsUnique}/5):`);
out.fails.forEach(m => console.log('   ' + m + check(m)));
console.log(`\n${bad === 0 ? 'OK — all fail messages have emoji, no trailing period' : bad + ' PROBLEM(S) FOUND'}`);
await browser.close(); server.close();
process.exit(bad === 0 ? 0 : 1);
