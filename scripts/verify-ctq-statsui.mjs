// Verify the post-game stats block, countdown format, and the 📊 overlay.
import { startServer, launch } from './_harness.mjs';
const { server, base } = await startServer();
const browser = await launch();
const page = await browser.newPage();
await page.goto(`${base}/clockthequote`, { waitUntil: 'domcontentloaded' });
await page.evaluate(() => { try{ localStorage.clear(); }catch{} });
await page.reload({ waitUntil: 'domcontentloaded' });
await page.evaluate(() => closeHowTo());
const show = await page.evaluate(() => clip.show);
await page.evaluate(s => submitGuess(s), show);   // solve on clue 1 → highlight row 1, played 1

const r = await page.evaluate(() => {
  const card = document.getElementById('card').innerText;
  const cd = document.getElementById('cdown');
  const hot = document.querySelector('.hbar.hot');
  return {
    hasStats: /Your stats/i.test(card),
    played: (document.querySelector('.statn') || {}).textContent,
    cd: cd ? cd.textContent : null,
    hotRow: hot ? hot.parentElement.querySelector('.hk').textContent : null,
  };
});
const checks = [
  ['result screen shows stats',      r.hasStats === true],
  ['first stat tile (Played) reads 1', r.played === '1'],
  ['countdown is HH:MM:SS',          /^\d{2}:\d{2}:\d{2}$/.test(r.cd || '')],
  ['histogram highlights clue 1',    r.hotRow === '1'],
];

await page.evaluate(() => openStats());
const ov = await page.evaluate(() => ({
  shown: document.getElementById('stats-ov').classList.contains('show'),
  played: (document.querySelector('#stats-body .statn') || {}).textContent,
}));
checks.push(['📊 overlay opens', ov.shown === true]);
checks.push(['overlay Played reads 1', ov.played === '1']);

// countdown timer must not accumulate across repeated result-screen renders
const timer = await page.evaluate(() => {
  let si=0, ci=0; const _si=window.setInterval, _ci=window.clearInterval;
  window.setInterval=(...a)=>{si++;return _si(...a);}; window.clearInterval=(...a)=>{ci++;return _ci(...a);};
  render(); render(); render();                 // three re-renders of the finished result screen
  window.setInterval=_si; window.clearInterval=_ci;
  return { si, ci, live: countdownTimer !== null };
});
// invariant: at most one live interval (each render stops before it starts) and exactly one currently live
checks.push(['countdown timer does not stack (<=1 net live)', (timer.si - timer.ci) <= 1]);
checks.push(['countdown timer is live on result screen', timer.live === true]);

// Preview finish must NOT leak the stats block or countdown.
{
  const page = await browser.newPage();
  await page.goto(`${base}/clockthequote?day=3`, { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => { try{ localStorage.clear(); }catch{} });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.evaluate(() => closeHowTo());
  const show = await page.evaluate(() => clip.show);
  await page.evaluate(s => submitGuess(s), show);
  const r = await page.evaluate(() => ({
    hasCountdown: !!document.getElementById('cdown'),
    hasStats: !!document.querySelector('.statwrap'),
    isPreviewLine: /Preview of #/i.test(document.getElementById('card').innerText),
    storage: localStorage.getItem('ctq_v1'),
  }));
  checks.push(['preview finish shows no countdown', r.hasCountdown === false]);
  checks.push(['preview finish shows no stats block', r.hasStats === false]);
  checks.push(['preview finish shows the Preview line', r.isPreviewLine === true]);
  checks.push(['preview finish writes no state', r.storage === null]);
  await page.close();
}

// Blocked storage: game still playable + friendly "storage blocked" note on the stats screen.
{
  const page = await browser.newPage();
  await page.addInitScript(() => {
    try{ Object.defineProperty(Storage.prototype, 'setItem', { configurable:true, value(){ throw new Error('blocked'); } }); }catch(e){}
  });
  await page.goto(`${base}/clockthequote`, { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => closeHowTo());
  const playable = await page.evaluate(() => !!document.getElementById('guess'));
  const show = await page.evaluate(() => clip.show);
  await page.evaluate(s => submitGuess(s), show);      // finish → result screen renders statsHTML
  const r = await page.evaluate(() => ({
    storeOk: typeof STORAGE_OK !== 'undefined' ? STORAGE_OK : null,
    hasNote: !!document.querySelector('.storenote'),
    hasTiles: !!document.querySelector('.statn'),
  }));
  checks.push(['blocked storage: game still playable', playable === true]);
  checks.push(['blocked storage: STORAGE_OK is false', r.storeOk === false]);
  checks.push(['blocked storage: shows the storage-blocked note', r.hasNote === true]);
  checks.push(['blocked storage: hides the zeroed tiles', r.hasTiles === false]);
  await page.close();
}

let ok = true;
for (const [n,p] of checks){ if(!p) ok=false; console.log(`${p?'PASS':'FAIL'}  ${n}`); }
console.log(ok ? '\nALL PASS' : '\nSOME FAILED');
await browser.close(); server.close();
process.exit(ok ? 0 : 1);
