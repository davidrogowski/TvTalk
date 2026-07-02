// Verify Clock The Quote UI sounds: triggers fire, mute suppresses + persists.
// Counts oscillator creations (only the tonal wrong/win sounds use them; clip
// playback + iOS unlock use buffer sources, so the count isolates SFX tones).
import { startServer, launch, report } from './_harness.mjs';

const { server, base } = await startServer();
const URL = `${base}/clockthequote?day=2`;

const browser = await launch();
const checks = [];
const errs = [];

async function freshPage() {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await ctx.addInitScript(() => {
    window.__osc = 0;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC) { const o = AC.prototype.createOscillator; AC.prototype.createOscillator = function(){ window.__osc++; return o.apply(this, arguments); }; }
  });
  const page = await ctx.newPage();
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push(m.text()); });  // ignore 404s for clip/favicon — not code errors
  page.on('pageerror', e => errs.push('PAGEERR: ' + e.message));
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(150);
  await page.evaluate(() => { try { closeHowTo(); } catch {} });   // dismiss the auto-shown how-to (no sound; frees the buttons)
  return { ctx, page };
}
const osc = (page) => page.evaluate(() => window.__osc);

// --- 1. sounds fire when unmuted ---
{
  const { ctx, page } = await freshPage();
  checks.push(['default: mute flag off', await page.evaluate(() => { try { return localStorage.getItem('ctq_muted'); } catch { return 'ERR'; } }) === null]);
  checks.push(['default: icon is 🔊', (await page.textContent('#mutebtn')) === '🔊']);
  await page.evaluate(() => { window.__osc = 0; });
  await page.evaluate(() => submitGuess('zzz-not-a-real-title'));        // wrong → 1 oscillator
  checks.push(['wrong guess plays pop (1 osc)', await osc(page) === 1]);
  await page.evaluate(() => submitGuess(clip.show));                     // right → 3 oscillators (bell ding)
  checks.push(['right guess plays win (total 4 osc)', await osc(page) === 4]);
  checks.push(['win actually registered', await page.evaluate(() => solvedStage !== null && finished === true)]);
  await ctx.close();
}

// --- 2. skip plays pop; play/replay are silent ---
{
  const { ctx, page } = await freshPage();
  await page.evaluate(() => { window.__osc = 0; });
  await page.click('#skip');                                  // skip → pop (1 osc)
  checks.push(['skip clue plays pop (1 osc)', await osc(page) === 1]);
  checks.push(['skip advanced the clue', await page.evaluate(() => stage === 1 && guesses === 1)]);
  await page.evaluate(() => { window.__osc = 0; });
  await page.click('#play');                                  // play → no sound
  await page.waitForTimeout(60);
  checks.push(['play button is silent (0 osc)', await osc(page) === 0]);
  await ctx.close();
}

// --- 2b. dropdown pick fills the box but does NOT submit; Guess locks it in ---
{
  const { ctx, page } = await freshPage();
  await page.fill('#guess', 'Frie');                          // matches "Friends" (not the day-2 answer)
  await page.waitForTimeout(80);
  await page.click('.opt');                                   // click the match
  const sel = await page.evaluate(() => ({ val: document.getElementById('guess').value, guesses, finished }));
  checks.push(['dropdown pick fills the input', sel.val === 'Friends']);
  checks.push(['dropdown pick does NOT submit', sel.guesses === 0 && sel.finished === false]);
  await page.evaluate(() => { window.__osc = 0; });
  await page.click('#go');                                    // Guess → submit the wrong pick → pop
  checks.push(['Guess locks in the selection', await page.evaluate(() => guesses) === 1]);
  checks.push(['locked-in wrong guess plays pop (1 osc)', await osc(page) === 1]);
  await ctx.close();
}

// --- 3. mute suppresses sound + persists across reload ---
{
  const { ctx, page } = await freshPage();
  await page.click('#mutebtn');
  checks.push(['toggle sets flag = 1', await page.evaluate(() => { try { return localStorage.getItem('ctq_muted'); } catch { return 'ERR'; } }) === '1']);
  checks.push(['toggle sets icon 🔇', (await page.textContent('#mutebtn')) === '🔇']);
  await page.evaluate(() => { window.__osc = 0; });
  await page.evaluate(() => { submitGuess('zzz'); submitGuess(clip.show); });   // muted → no oscillators
  checks.push(['muted: no sound on guesses (0 osc)', await osc(page) === 0]);
  checks.push(['muted: game logic still works', await page.evaluate(() => finished === true)]);
  // reload same context → flag + icon persist
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(150);
  checks.push(['reload: still muted (icon 🔇)', (await page.textContent('#mutebtn')) === '🔇']);
  // unmute → flag 0, icon 🔊
  await page.click('#mutebtn');
  checks.push(['unmute: flag = 0', await page.evaluate(() => { try { return localStorage.getItem('ctq_muted'); } catch { return 'ERR'; } }) === '0']);
  checks.push(['unmute: icon 🔊', (await page.textContent('#mutebtn')) === '🔊']);
  await ctx.close();
}

await browser.close();
server.close();
report(checks, errs);
