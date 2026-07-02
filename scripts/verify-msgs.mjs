// Verify score-aware result messages resolve for every tier × rotation, no period, has emoji.
import { startServer, launch } from './_harness.mjs';

const { server, base } = await startServer();
const browser = await launch();
const page = await browser.newPage();
await page.goto(`${base}/clockthequote?day=1`, { waitUntil: 'networkidle' });
const out = await page.evaluate(() => {
  const rows = [];
  for (let stage = 0; stage < 5; stage++) {
    const opts = [];
    for (let r = 0; r < 5; r++) { roundNo = r + 1; solvedStage = stage; opts.push(winMsg()); }
    rows.push({ tier: (stage + 1) + '/5', n: new Set(opts).size, opts });
  }
  const fails = []; for (let r = 0; r < 5; r++) { roundNo = r + 1; fails.push(failMsg()); }
  return { rows, fails, failsUnique: new Set(fails).size };
});
let bad = 0;
const check = (m) => {
  const endsPeriod = /\.$/.test(m.trim());
  const hasEmoji = /\p{Extended_Pictographic}/u.test(m);
  if (endsPeriod || !hasEmoji) { bad++; return ' <-- ' + (endsPeriod ? 'PERIOD ' : '') + (!hasEmoji ? 'NO-EMOJI' : ''); }
  return '';
};
for (const row of out.rows) {
  console.log(`\n${row.tier}  (unique ${row.n}/5):`);
  row.opts.forEach(m => console.log('   ' + m + check(m)));
}
console.log(`\nFAIL-tier  (unique ${out.failsUnique}/5):`);
out.fails.forEach(m => console.log('   ' + m + check(m)));
console.log(`\n${bad === 0 ? 'OK — all messages have emoji, no trailing period' : bad + ' PROBLEM(S) FOUND'}`);
await browser.close(); server.close();
process.exit(bad === 0 ? 0 : 1);
