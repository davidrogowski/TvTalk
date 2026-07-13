// Verify the daily lock, mid-round resume, and preview isolation.
import { startServer, launch } from './_harness.mjs';
const { server, base } = await startServer();
const browser = await launch();
const checks = [];
const solve = async (page) => {
  const show = await page.evaluate(() => clip.show);
  await page.evaluate(s => submitGuess(s), show);
};

// 1) LOCK: solve today, reload → result screen (no guess input), exactly one played day.
{
  const page = await browser.newPage();
  await page.goto(`${base}/clockthequote`, { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => { try{ localStorage.clear(); }catch{} });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await solve(page);
  await page.reload({ waitUntil: 'domcontentloaded' });
  const r = await page.evaluate(() => ({
    finished, hasInput: !!document.getElementById('guess'),
    played: JSON.parse(localStorage.getItem('ctq_v1')).stats.played,
  }));
  checks.push(['reload after solve → finished/locked', r.finished === true]);
  checks.push(['reload after solve → no guess input',  r.hasInput === false]);
  checks.push(['solve records exactly one played day', r.played === 1]);
  await page.reload({ waitUntil: 'domcontentloaded' });                 // second reload: idempotency guard
  const r2 = await page.evaluate(() => ({
    hasInput: !!document.getElementById('guess'),
    played: JSON.parse(localStorage.getItem('ctq_v1')).stats.played,
  }));
  checks.push(['second reload still no guess input', r2.hasInput === false]);
  checks.push(['second reload does not double-count played', r2.played === 1]);
  await page.close();
}

// 2) RESUME: one wrong guess advances a stage; reload restores it (not reset to 0).
{
  const page = await browser.newPage();
  await page.goto(`${base}/clockthequote`, { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => { try{ localStorage.clear(); }catch{} });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.evaluate(() => submitGuess('__definitely not a real title__'));
  const before = await page.evaluate(() => stage);
  await page.reload({ waitUntil: 'domcontentloaded' });
  const after = await page.evaluate(() => stage);
  checks.push(['wrong guess advanced the stage', before === 1]);
  checks.push(['reload resumes the same stage',  after === 1]);
  await page.close();
}

// 3) PREVIEW isolation: ?day=N solve writes nothing and stays replayable.
{
  const page = await browser.newPage();
  await page.goto(`${base}/clockthequote?day=5`, { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => { try{ localStorage.clear(); }catch{} });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await solve(page);
  const state = await page.evaluate(() => localStorage.getItem('ctq_v1'));
  checks.push(['preview solve writes no state', state === null]);
  await page.reload({ waitUntil: 'domcontentloaded' });
  const playable = await page.evaluate(() => !!document.getElementById('guess'));
  checks.push(['preview day still playable after reload', playable === true]);
  await page.close();
}

// 4) UNLIMITED PASS bypass: a finished day reopens as playable when hasUnlimitedPass() is true.
{
  const page = await browser.newPage();
  await page.goto(`${base}/clockthequote`, { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => { try{ localStorage.clear(); }catch{} });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await solve(page);                                   // finish today → locked
  const lockedInput = await page.evaluate(() => !!document.getElementById('guess'));
  const reopened = await page.evaluate(() => { hasUnlimitedPass = () => true; startRound();
    return { hasInput: !!document.getElementById('guess'), finished }; });
  const played = await page.evaluate(() => JSON.parse(localStorage.getItem('ctq_v1')).stats.played);
  checks.push(['locked before pass (no guess input)', lockedInput === false]);
  checks.push(['pass reopens finished day as playable', reopened.hasInput === true && reopened.finished === false]);
  checks.push(['reopening does not double-count played', played === 1]);
  await page.close();
}

// 5) LISTEN BUDGET survives a refresh: you can't reload to buy fresh listens on the same clue.
{
  const page = await browser.newPage();
  await page.goto(`${base}/clockthequote`, { waitUntil: 'networkidle' });
  await page.evaluate(() => { try{ localStorage.clear(); }catch{} });
  await page.reload({ waitUntil: 'networkidle' });
  const limit = await page.evaluate(() => STAGES[stage].limit);       // clue 1 → 2 listens
  await page.evaluate(() => { playCurrent(); playCurrent(); });        // burn the whole allowance
  const before = await page.evaluate(() => ({ used: playsUsed, can: canPlay() }));
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('ctq_v1')).progress.playsUsed);
  await page.reload({ waitUntil: 'networkidle' });                     // the cheat: refresh mid-round
  const after = await page.evaluate(() => ({ used: playsUsed, can: canPlay(), stage }));
  checks.push(['listens exhausted before refresh', before.used === limit && before.can === false]);
  checks.push(['listen count is persisted', stored === limit]);
  checks.push(['refresh does NOT restore listens', after.used === limit && after.can === false]);
  checks.push(['refresh keeps you on the same clue', after.stage === 0]);
  await page.close();
}

let ok = true;
for (const [n,p] of checks){ if(!p) ok=false; console.log(`${p?'PASS':'FAIL'}  ${n}`); }
console.log(ok ? '\nALL PASS' : '\nSOME FAILED');
await browser.close(); server.close();
process.exit(ok ? 0 : 1);
