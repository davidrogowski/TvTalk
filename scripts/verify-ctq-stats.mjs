// Unit-test the pure stats reducer (nextStats/average) via the in-page globals.
import { startServer, launch } from './_harness.mjs';
const { server, base } = await startServer();
const browser = await launch();
const page = await browser.newPage();
await page.goto(`${base}/clockthequote?day=1`, { waitUntil: 'domcontentloaded' });

const r = await page.evaluate(() => {
  // fold a sequence of {num, solvedStage} days from an empty stats object
  const run = (days) => days.reduce(
    (acc, d) => nextStats(acc.stats, acc.lastNum, d),
    { stats: emptyStats(), lastNum: null });

  const a = run([{num:1,solvedStage:0},{num:2,solvedStage:1}]);      // two consecutive wins
  const b = run([{num:1,solvedStage:0},{num:3,solvedStage:0}]);      // a gap day
  const c = run([{num:1,solvedStage:0},{num:2,solvedStage:null}]);   // win then loss
  const d = run([{num:1,solvedStage:0},{num:2,solvedStage:0},
                 {num:3,solvedStage:null},{num:4,solvedStage:0}]);   // peak then reset

  const out = {
    consecStreak: a.stats.curStreak, consecMax: a.stats.maxStreak,
    consecAvg: average(a.stats), consecDist: a.stats.dist.join(','),
    gapStreak: b.stats.curStreak, gapMax: b.stats.maxStreak,
    lossStreak: c.stats.curStreak, lossWins: c.stats.wins, lossFails: c.stats.fails,
    lossAvg: average(c.stats), lossDist: c.stats.dist.join(','),
    peakMax: d.stats.maxStreak, peakCur: d.stats.curStreak,
  };
  // no-mutation probe: nextStats must not mutate its input stats or dist
  (() => { const base0 = emptyStats(); const dref = base0.dist;
           nextStats(base0, null, {num:1, solvedStage:0});
           out.mutOk = (base0.played===0 && base0.dist===dref && dref.join(',')==='0,0,0,0,0'); })();
  return out;
});

const checks = [
  ['consecutive wins → streak 2',        r.consecStreak === 2],
  ['consecutive wins → maxStreak 2',     r.consecMax === 2],
  ['avg 1/5 then 2/5 = 1.5',             r.consecAvg === 1.5],
  ['dist counts each solved clue',       r.consecDist === '1,1,0,0,0'],
  ['gap day → streak resets to 1',       r.gapStreak === 1],
  ['gap day → maxStreak stays 1',        r.gapMax === 1],
  ['loss → streak 0',                    r.lossStreak === 0],
  ['loss → wins unchanged (1)',          r.lossWins === 1],
  ['loss → fails 1',                     r.lossFails === 1],
  ['loss counts as 6 → avg 3.5',         r.lossAvg === 3.5],
  ['loss → dist unchanged',              r.lossDist === '1,0,0,0,0'],
  ['maxStreak remembers peak (2)',       r.peakMax === 2],
  ['curStreak after reset (1)',          r.peakCur === 1],
  ['nextStats does not mutate input',    r.mutOk === true],
];
let ok = true;
for (const [n,p] of checks){ if(!p) ok=false; console.log(`${p?'PASS':'FAIL'}  ${n}`); }
console.log(ok ? '\nALL PASS' : '\nSOME FAILED');
await browser.close(); server.close();
process.exit(ok ? 0 : 1);
