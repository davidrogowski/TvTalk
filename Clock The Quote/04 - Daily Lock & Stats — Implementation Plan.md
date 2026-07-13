# Clock The Quote — Daily Lock & Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a once-a-day lock, a real calendar-day win streak, an average score, and a guess-distribution histogram to Clock The Quote — all client-side, no backend.

**Architecture:** Everything stays inside the single self-contained `clockthequote.html`. Personal state persists in one versioned `localStorage` blob (`ctq_v1`). The stats math is written as **pure, globally-scoped functions** (`nextStats`, `average`) so the existing `scripts/verify-*.mjs` Playwright harness can unit-test them by calling the in-page globals via `page.evaluate()`. The lock is a single choke-point (`isLockedToday`) that a future paid "unlimited plays" flag can bypass.

**Tech Stack:** Static HTML + inline vanilla JS (no build step). Tests: Node 24 + Playwright (Chrome channel) via `scripts/_harness.mjs`, run with `node scripts/<name>.mjs`.

## Global Constraints

- **DEPLOY IS GATED — do not run `wrangler`/deploy to tvtalk.fun until Dave has tested locally and approved.** Build + local verification only. Flag when ready; Dave triggers the deploy.
- **Single self-contained file:** all game code stays inline in `clockthequote.html`. Do **not** add a new served asset (root `.js`/`.css`). (Verify scripts live in `scripts/`, which `.assetsignore` excludes from deploy.)
- **Storage:** `localStorage` only, always through the throw-safe `lsGet`/`lsSet` helpers. Key `ctq_v1`. The old `ctq_proto_streak` key is retired (left in place, unused — not read, not written).
- **Preview safety:** any round loaded with `?day=N` must **never** write state and **never** lock (it's the queue-preview dev tool). All persistence gates on `!isPreview()`.
- **Score direction (lower is better):** a win solved on clue index `n` (0-based) scores `n+1` (i.e. `1`…`5`); a loss (`X/5`) scores **`6`**. Average = `scoreSum / played` over all completed days.
- **Streak = consecutive completed days won**, computed from the puzzle-number gap (`num === lastNum + 1`), which is DST-proof. A skipped day resets the streak to 1 on the next win; a loss resets it to 0.
- **Git in this repo hangs** on iCloud-offloaded audio (`git status`/`git add -A` scan them). In commit steps use **targeted adds of named files only** — never `git status`, `git add -A`, or `git add .`.
- Playwright/Chrome are already installed (existing `verify-*.mjs` use them). If `node scripts/verify-*.mjs` errors with a missing browser, run `npx playwright install chrome` once.

---

## File structure

- **Modify `clockthequote.html`** (single file, ~807 lines). Regions touched:
  - `~451-454` — replace the placeholder streak (`streak`/`recordWin`/`recordLoss`) with the pure stats model (Task 1) + persisted-state layer (Task 2).
  - `~465-483` — rewrite `startRound` (resume/lock) and `advanceClue` (record on loss) (Task 2).
  - `~609-616` — `submitGuess`/`skipClue` persist progress / record on win (Task 2).
  - `~686-712` — extend `renderResult` with the post-game stats block + countdown (Task 3).
  - `~195-196` + `~198-229` + `~192` — add the `📊` button, a stats overlay (mirrors the how-to overlay), and its CSS (Task 3).
  - `~803-804` — boot wiring for the stats overlay (Task 3).
- **Create `scripts/verify-ctq-stats.mjs`** — pure-reducer unit tests (Task 1).
- **Create `scripts/verify-ctq-lock.mjs`** — browser flow tests: lock, resume, preview isolation (Task 2).
- **Create `scripts/verify-ctq-statsui.mjs`** — stats UI + countdown presence tests (Task 3).

---

## Task 1: Pure stats reducer (`nextStats`, `average`) + unit tests

**Files:**
- Modify: `clockthequote.html:451-454` (replace the streak block)
- Create: `scripts/verify-ctq-stats.mjs`

**Interfaces:**
- Produces:
  - `emptyStats() → {played, wins, fails, curStreak, maxStreak, dist:[5], scoreSum}`
  - `nextStats(stats, lastNum, day) → {stats, lastNum}` where `day = {num, solvedStage}` (`solvedStage` is `0..4` for a win, `null` for a loss). Pure — never mutates inputs.
  - `average(stats) → number`
  - `hasUnlimitedPass() → boolean` (stub, always `false`)

- [ ] **Step 1: Write the failing test** — create `scripts/verify-ctq-stats.mjs`:

```js
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
  return {
    consecStreak: a.stats.curStreak, consecMax: a.stats.maxStreak,
    consecAvg: average(a.stats), consecDist: a.stats.dist.join(','),
    gapStreak: b.stats.curStreak, gapMax: b.stats.maxStreak,
    lossStreak: c.stats.curStreak, lossWins: c.stats.wins, lossFails: c.stats.fails,
    lossAvg: average(c.stats), lossDist: c.stats.dist.join(','),
    peakMax: d.stats.maxStreak, peakCur: d.stats.curStreak,
  };
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
];
let ok = true;
for (const [n,p] of checks){ if(!p) ok=false; console.log(`${p?'PASS':'FAIL'}  ${n}`); }
console.log(ok ? '\nALL PASS' : '\nSOME FAILED');
await browser.close(); server.close();
process.exit(ok ? 0 : 1);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node scripts/verify-ctq-stats.mjs`
Expected: FAIL / non-zero exit — `emptyStats`/`nextStats`/`average` are not defined (a `ReferenceError` inside `page.evaluate`).

- [ ] **Step 3: Write minimal implementation** — in `clockthequote.html`, replace lines 451-454:

```js
/* win streak (persisted; real game keys this to calendar days, prototype counts consecutive wins) */
let streak = +(lsGet("ctq_proto_streak")||0);
function recordWin(){  streak++;   lsSet("ctq_proto_streak", streak); }
function recordLoss(){ streak=0;   lsSet("ctq_proto_streak", streak); }
```

with:

```js
/* ---------- stats model (pure; no DOM / storage — unit-tested in scripts/verify-ctq-stats.mjs) ---------- */
function emptyStats(){ return { played:0, wins:0, fails:0, curStreak:0, maxStreak:0, dist:[0,0,0,0,0], scoreSum:0 }; }
// Fold one finished day into stats. day = {num, solvedStage}; solvedStage 0..4 for a win, null for a loss.
// Win on clue n scores n+1 (1..5); a loss scores 6. Streak continues only when num === lastNum+1.
// Returns { stats, lastNum } and never mutates its inputs.
function nextStats(stats, lastNum, day){
  const s = { ...stats, dist:[...stats.dist] };
  const win = day.solvedStage != null;
  const eff = win ? day.solvedStage + 1 : 6;
  s.played   += 1;
  s.scoreSum += eff;
  if(win){
    s.wins += 1;
    s.dist[day.solvedStage] += 1;
    s.curStreak = (lastNum === day.num - 1) ? s.curStreak + 1 : 1;
    if(s.curStreak > s.maxStreak) s.maxStreak = s.curStreak;
  } else {
    s.fails += 1;
    s.curStreak = 0;
  }
  return { stats: s, lastNum: day.num };
}
function average(stats){ return stats.played ? stats.scoreSum / stats.played : 0; }
function hasUnlimitedPass(){ return false; } // future paid "unlimited plays" unlock — flip to bypass the daily lock
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node scripts/verify-ctq-stats.mjs`
Expected: every line `PASS`, final `ALL PASS`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add clockthequote.html scripts/verify-ctq-stats.mjs
git commit -m "feat(ctq): pure stats reducer (streak/average/dist) + unit tests

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Persisted state, daily lock, and mid-round resume

**Files:**
- Modify: `clockthequote.html` — add the state layer after the Task 1 block (~after line ~475); rewrite `startRound` (~465-471) and `advanceClue` (~472-476 in current numbering / just below); update `submitGuess` (~611) and keep `skipClue` (~616) working through `advanceClue`.
- Create: `scripts/verify-ctq-lock.mjs`

**Interfaces:**
- Consumes (from Task 1): `emptyStats`, `nextStats`, `hasUnlimitedPass`. Existing globals: `dailyNumber`, `clipForNumber`, `roundNo`, `stage`, `guesses`, `solvedStage`, `finished`, `playsUsed`, `loadClip`, `render`, `MAX_GUESSES`, `lsGet`, `lsSet`.
- Produces: `STATE` (the in-memory `ctq_v1` object), `loadState()`, `saveState()`, `isPreview()`, `persistProgress()`, `recordResult()`, `isLockedToday()`. `startRound`/`advanceClue`/`submitGuess` now route through these.

- [ ] **Step 1: Write the failing test** — create `scripts/verify-ctq-lock.mjs`:

```js
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

let ok = true;
for (const [n,p] of checks){ if(!p) ok=false; console.log(`${p?'PASS':'FAIL'}  ${n}`); }
console.log(ok ? '\nALL PASS' : '\nSOME FAILED');
await browser.close(); server.close();
process.exit(ok ? 0 : 1);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node scripts/verify-ctq-lock.mjs`
Expected: FAIL — reloading after a solve currently deals a fresh playable board (guess input still present) and there is no `ctq_v1` key, so the lock/record/preview checks fail.

- [ ] **Step 3a: Add the state layer.** In `clockthequote.html`, immediately after the Task 1 `hasUnlimitedPass()` line, insert:

```js
/* ---------- persisted state (localStorage; throw-safe via lsGet/lsSet) ---------- */
const STORE_KEY = "ctq_v1";
function loadState(){
  let s = null;
  try{ s = JSON.parse(lsGet(STORE_KEY) || "null"); }catch{ s = null; }
  if(!s || s.v !== 1) s = { v:1, lastNum:null, progress:null, stats: emptyStats() };
  if(!s.stats) s.stats = emptyStats();
  return s;
}
function saveState(){ lsSet(STORE_KEY, JSON.stringify(STATE)); }
let STATE = loadState();
function isPreview(){ return new URLSearchParams(location.search).get("day") !== null; }

// persist the in-progress round so a refresh resumes it instead of dealing a fresh board
function persistProgress(){
  if(isPreview()) return;
  const prev = STATE.progress;
  STATE.progress = { num: roundNo, stage, guesses, solvedStage, finished,
                     counted: !!(prev && prev.num === roundNo && prev.counted) };
  saveState();
}
// fold a just-finished day into stats exactly once, then lock it
function recordResult(){
  if(isPreview()) return;
  if(STATE.progress && STATE.progress.num === roundNo && STATE.progress.counted) return;
  const res = nextStats(STATE.stats, STATE.lastNum, { num: roundNo, solvedStage });
  STATE.stats = res.stats; STATE.lastNum = res.lastNum;
  STATE.progress = { num: roundNo, stage, guesses, solvedStage, finished:true, counted:true };
  saveState();
}
// the daily lock: once today is finished you can't replay it (preview + paid pass bypass)
function isLockedToday(){
  if(isPreview() || hasUnlimitedPass()) return false;
  return !!(STATE.progress && STATE.progress.num === roundNo && STATE.progress.finished);
}
```

- [ ] **Step 3b: Rewrite `startRound`.** Replace the current `startRound` (lines ~465-471):

```js
function startRound(){
  roundNo = dailyNumber();
  clip = clipForNumber(roundNo);
  stage=0; guesses=0; solvedStage=null; finished=false; playsUsed=0;
  loadClip(clip);
  render();
}
```

with:

```js
function startRound(){
  roundNo = dailyNumber();
  clip = clipForNumber(roundNo);
  const p = STATE.progress;
  // resume today's in-progress round, or show a finished round ONLY while it is still locked;
  // when hasUnlimitedPass() unlocks a finished day (isLockedToday()===false) fall through to a fresh playable round.
  if(!isPreview() && p && p.num === roundNo && (!p.finished || isLockedToday())){
    stage=p.stage; guesses=p.guesses; solvedStage=p.solvedStage; finished=p.finished; playsUsed=0;
  } else {                                             // fresh round (new day, or a finished day the pass reopens)
    stage=0; guesses=0; solvedStage=null; finished=false; playsUsed=0;
    persistProgress();                                 // seed today's in-progress day (no-op in preview)
  }
  loadClip(clip);
  render();
}
```

- [ ] **Step 3c: Rewrite `advanceClue`.** Replace the current `advanceClue`:

```js
function advanceClue(){ // wrong guess or skip
  guesses++;
  if(stage < MAX_GUESSES-1){ stage++; playsUsed=0; }   // new stage → fresh play allowance
  if(guesses>=MAX_GUESSES){ finished=true; recordLoss(); }
}
```

with:

```js
function advanceClue(){ // wrong guess or skip
  guesses++;
  if(stage < MAX_GUESSES-1){ stage++; playsUsed=0; }   // new stage → fresh play allowance
  if(guesses>=MAX_GUESSES){ finished=true; recordResult(); }
  else persistProgress();
}
```

- [ ] **Step 3d: Update `submitGuess` win path.** In `submitGuess` (line ~611), replace `recordWin()` with `recordResult()`:

```js
  if(title===clip.show){ sfx("win"); solvedStage=stage; finished=true; recordResult(); render(); return; }
```

(No change to `skipClue` — it already routes through `advanceClue`, which now persists.)

- [ ] **Step 4: Run test to verify it passes**

Run: `node scripts/verify-ctq-lock.mjs`
Expected: every line `PASS`, `ALL PASS`, exit 0.
Then re-run Task 1's test to confirm no regression: `node scripts/verify-ctq-stats.mjs` → `ALL PASS`.

- [ ] **Step 5: Commit**

```bash
git add clockthequote.html scripts/verify-ctq-lock.mjs
git commit -m "feat(ctq): once-a-day lock + mid-round resume via ctq_v1 state

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Stats UI — post-game summary, countdown, and the 📊 overlay

**Files:**
- Modify: `clockthequote.html` — add stats/countdown helpers (near the other render helpers, ~before `renderResult`); extend `renderResult` (~686-712); add the `📊` button (~196) and stats overlay markup (~after 229); add CSS (~before `</style>` at 192); wire the overlay at boot (~804).
- Create: `scripts/verify-ctq-statsui.mjs`

**Interfaces:**
- Consumes: `STATE`, `average`, `isPreview`, `roundNo`, `solvedStage`. Existing overlay pattern: `.howto-ov`/`.howto`/`.show`, `openHowTo`/`closeHowTo`.
- Produces: `statsHTML(highlightStage)`, `msToNextEtMidnight()`, `fmtHMS(ms)`, `startCountdown()`, `stopCountdown()`, `openStats()`, `closeStats()`, `wireStats()`. DOM ids: `statsbtn`, `stats-ov`, `stats-body`, `stats-x`, `stats-got`, `cdown`.

- [ ] **Step 1: Write the failing test** — create `scripts/verify-ctq-statsui.mjs`:

```js
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

let ok = true;
for (const [n,p] of checks){ if(!p) ok=false; console.log(`${p?'PASS':'FAIL'}  ${n}`); }
console.log(ok ? '\nALL PASS' : '\nSOME FAILED');
await browser.close(); server.close();
process.exit(ok ? 0 : 1);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node scripts/verify-ctq-statsui.mjs`
Expected: FAIL — `closeHowTo`/`clip` exist but `openStats` is undefined and the result screen has no `.statn`/`#cdown`/`Your stats`.

- [ ] **Step 3a: Add stats + countdown helpers.** In `clockthequote.html`, just above `function renderResult(){` (~line 686), insert:

```js
/* ---------- stats UI (tiles + histogram + midnight-ET countdown) ---------- */
function pct(n,d){ return d ? Math.round(100*n/d) : 0; }
function statTiles(){
  const s=STATE.stats;
  const avg = s.played ? average(s).toFixed(1) : "—";
  const tile=(v,l)=>`<div class="stat"><div class="statn">${v}</div><div class="statl">${l}</div></div>`;
  return `<div class="statrow">
    ${tile(s.played,"Played")}${tile(pct(s.wins,s.played)+"%","Win")}
    ${tile(s.curStreak,"Streak")}${tile(s.maxStreak,"Max")}${tile(avg,"Avg")}
  </div>`;
}
function statHisto(highlightStage){
  const s=STATE.stats, max=Math.max(1,...s.dist);
  const rows=s.dist.map((c,i)=>{
    const w=Math.round(100*c/max), hot=(i===highlightStage)?" hot":"";
    return `<div class="hrow"><span class="hk">${i+1}</span>` +
           `<span class="hbar${hot}" style="width:${Math.max(9,w)}%">${c}</span></div>`;
  }).join("");
  return `<div class="histo"><div class="histh">Solved on clue</div>${rows}` +
         `<div class="failline">Missed: <b>${s.fails}</b></div></div>`;
}
function statsHTML(highlightStage){
  return `<div class="statwrap"><h3>Your stats</h3>${statTiles()}${statHisto(highlightStage)}</div>`;
}
// ms until the next America/New_York midnight (DST-safe: reads the ET wall clock)
function msToNextEtMidnight(){
  const parts=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",hour12:false,
    hour:"2-digit",minute:"2-digit",second:"2-digit"}).formatToParts(new Date());
  const g=t=>+parts.find(p=>p.type===t).value;
  let h=g("hour"); if(h===24) h=0;
  const elapsed=h*3600 + g("minute")*60 + g("second");
  return (86400 - elapsed)*1000;
}
function fmtHMS(ms){
  const t=Math.max(0,Math.floor(ms/1000));
  const p=n=>String(n).padStart(2,"0");
  return `${p(Math.floor(t/3600))}:${p(Math.floor(t%3600/60))}:${p(t%60)}`;
}
let countdownTimer=null;
function stopCountdown(){ if(countdownTimer){ clearInterval(countdownTimer); countdownTimer=null; } }
function startCountdown(){
  stopCountdown();
  const el=document.getElementById("cdown"); if(!el) return;
  const tick=()=>{ const ms=msToNextEtMidnight(); el.textContent=fmtHMS(ms); if(ms<=1000) stopCountdown(); };
  tick(); countdownTimer=setInterval(tick,1000);
}
function openStats(){
  const ov=document.getElementById("stats-ov"); if(!ov) return;
  document.getElementById("stats-body").innerHTML = statsHTML(-1);
  if(document.activeElement && document.activeElement.blur) document.activeElement.blur();
  ov.classList.add("show");
}
function closeStats(){ const ov=document.getElementById("stats-ov"); if(ov) ov.classList.remove("show"); }
function wireStats(){
  document.getElementById("statsbtn").onclick = openStats;
  document.getElementById("stats-x").onclick = closeStats;
  document.getElementById("stats-got").onclick = closeStats;
  const ov=document.getElementById("stats-ov");
  ov.onclick = e=>{ if(e.target===ov) closeStats(); };
  document.addEventListener("keydown", e=>{ if(e.key==="Escape" && ov.classList.contains("show")) closeStats(); });
}
```

- [ ] **Step 3b: Extend `renderResult`.** In `renderResult`, replace the closing line `<p class="small">Come back tomorrow for #${roundNo+1}.</p>` with:

```js
      ${isPreview()
        ? `<p class="small">Preview of #${roundNo}. <a href="/clockthequote">Play today ▸</a></p>`
        : `${statsHTML(solvedStage)}<p class="cdlabel">Next quote in <span id="cdown" class="cd">--:--:--</span></p>`}
```

Then, at the end of `renderResult` (right after the three `onclick` wirings), add:

```js
  if(!isPreview()) startCountdown();
```

Also call `stopCountdown();` at the top of `render()` (line ~633, alongside the existing `stopSource();`) so leaving the result view clears the interval:

```js
function render(){
  stopSource(); stopCountdown();      // stop clip + countdown when the view changes
  if(finished) return renderResult();
```

- [ ] **Step 3c: Add the 📊 button.** In the top-corner button group (line ~195-196), add after the help button:

```html
  <button class="statsbtn" id="statsbtn" aria-label="Your stats" title="Your stats">📊</button>
```

- [ ] **Step 3d: Add the stats overlay markup.** Immediately after the how-to overlay's closing `</div>` (the `#howto-ov` block, ~line 229), insert:

```html
  <!-- personal stats (opened via the 📊 button; reuses the how-to overlay styles) -->
  <div class="howto-ov" id="stats-ov" role="dialog" aria-modal="true" aria-label="Your stats">
    <div class="howto stats-modal">
      <button class="x" id="stats-x" aria-label="Close">✕</button>
      <h2>Your <em>Stats</em></h2>
      <div id="stats-body"></div>
      <button class="act primary howto-got" id="stats-got">Close</button>
    </div>
  </div>
```

- [ ] **Step 3e: Add CSS.** Just before `</style>` (line ~192), insert:

```css
  .statsbtn{position:fixed;top:12px;right:84px;z-index:5;width:34px;height:34px;border-radius:50%;
            border:1.5px solid var(--pline);background:var(--paper);cursor:pointer;font-size:15px;line-height:1}
  .statwrap h3{font-size:12px;letter-spacing:.14em;text-transform:uppercase;font-family:ui-monospace,Menlo,monospace;
               color:var(--red);text-align:center;margin:14px 0 10px}
  .statrow{display:flex;gap:6px;justify-content:center;margin-bottom:14px}
  .stat{flex:1;text-align:center}
  .statn{font-size:22px;font-weight:800;color:var(--ink);font-family:ui-monospace,Menlo,monospace}
  .statl{font-size:10.5px;color:var(--ink-m);text-transform:uppercase;letter-spacing:.05em;margin-top:2px}
  .histo{margin:0 auto;max-width:320px}
  .histh{font-size:11px;color:var(--ink-m);text-transform:uppercase;letter-spacing:.08em;margin:0 0 6px}
  .hrow{display:flex;align-items:center;gap:8px;margin:3px 0}
  .hk{flex:none;width:14px;text-align:center;font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--ink-m)}
  .hbar{display:inline-block;background:var(--pline);color:var(--paper);font-family:ui-monospace,Menlo,monospace;
        font-size:11px;font-weight:700;text-align:right;padding:2px 6px;border-radius:3px;min-width:18px}
  .hbar.hot{background:var(--red)}
  .failline{font-size:12px;color:var(--ink-m);text-align:center;margin-top:8px}
  .cdlabel{text-align:center;font-size:13px;color:var(--ink-m);margin:14px 0 4px}
  .cd{font-family:ui-monospace,Menlo,monospace;font-weight:700;color:var(--ink)}
```

- [ ] **Step 3f: Wire at boot.** After `wireHowTo();` (line ~804), add:

```js
wireStats();
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node scripts/verify-ctq-statsui.mjs`
Expected: every line `PASS`, `ALL PASS`, exit 0.
Re-run the earlier suites to confirm no regression:
`node scripts/verify-ctq-stats.mjs && node scripts/verify-ctq-lock.mjs` → both `ALL PASS`.

- [ ] **Step 5: Manual visual check (local only — NOT deployed)**

Serve locally and eyeball the result screen + 📊 overlay across a couple of days:
```bash
node scripts/shot.mjs clockthequote 2>/dev/null || python3 -m http.server 8787
```
Open `http://localhost:8787/clockthequote?day=1`, solve it, confirm: tiles read sensibly, the histogram bar for the solved clue is red, the countdown ticks down in `HH:MM:SS`, and the 📊 button opens/closes the stats overlay. (`?day=N` never persists, so this won't pollute real stats.)

- [ ] **Step 6: Commit**

```bash
git add clockthequote.html scripts/verify-ctq-statsui.mjs
git commit -m "feat(ctq): post-game stats, guess histogram, and next-quote countdown

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Deployment (SEPARATE — Dave-gated)

Do **not** perform this as part of implementation. After Dave has tested locally and approved, deploy per `../05 - Deployment.md`:

```bash
npx --yes wrangler@4.40.0 deploy
```

Then verify the live URL `https://tvtalk.fun/clockthequote` (not npx's exit code) and confirm the lock/stats work on the real domain.

---

## Self-review (against `03 - Daily Lock & Stats Design.md`)

- **Once-a-day lock** → Task 2 (`isLockedToday`, `startRound` renders the result screen for a finished day; no guess input). ✓
- **Anti-refresh resume** → Task 2 (`persistProgress` + `startRound` restore). ✓
- **Streak rules (continue / reset-to-1 on gap / reset-to-0 on loss / maxStreak)** → Task 1 (`nextStats`), tested. ✓
- **Average with fail=6 over all played** → Task 1 (`nextStats` `eff=6`, `average`), tested. ✓
- **Stats screen: Played · Win% · Streak · Max · Average + 5-row histogram + fails** → Task 3 (`statTiles`/`statHisto`). ✓
- **Countdown to next ET midnight** → Task 3 (`msToNextEtMidnight`/`startCountdown`). ✓
- **Preview (`?day=N`) never persists or locks** → Task 2 (`isPreview` gates `persistProgress`/`recordResult`/lock), tested. ✓
- **Paid-unlock choke-point** → Task 1 `hasUnlimitedPass` stub consumed by `isLockedToday` in Task 2. ✓
- **Migration: retire `ctq_proto_streak`, fresh `ctq_v1`** → Task 1 removes the reads/writes; Task 2's `loadState` starts fresh. ✓
- **localStorage-blocked graceful degradation** → all writes go through throw-safe `lsSet`; `loadState` falls back to in-memory defaults (game stays playable, stats just don't persist). ✓
- Type/name consistency: `nextStats`/`average`/`emptyStats`/`STATE`/`isPreview`/`isLockedToday`/`persistProgress`/`recordResult`/`statsHTML`/`startCountdown` used identically across tasks. ✓
