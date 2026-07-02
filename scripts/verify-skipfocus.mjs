// Verify Skip does NOT auto-focus the guess input on touch devices (which would
// pop the on-screen keyboard), but desktop still auto-focuses for type-to-play.
import { startServer, launch, report } from './_harness.mjs';

const { server, base } = await startServer();
const URL = `${base}/clockthequote?day=2`;
const browser = await launch();
const checks = [];

// force the (hover/pointer) media query to a known value BEFORE any page script runs
async function page(isDesktop){
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await ctx.addInitScript((desktop) => {
    try { localStorage.setItem('ctq_howto_seen','1'); } catch {}   // returning visitor: no overlay stealing focus
    const real = window.matchMedia.bind(window);
    window.matchMedia = (q) => {
      if (/hover:hover|pointer:fine/.test(q)) return { matches: desktop, media: q, addListener(){}, removeListener(){}, addEventListener(){}, removeEventListener(){} };
      return real(q);
    };
  }, isDesktop);
  const p = await ctx.newPage();
  await p.goto(URL, { waitUntil: 'networkidle' });
  await p.evaluate(() => { try { closeHowTo(); } catch {} });
  return { ctx, p };
}
const focused = (p) => p.evaluate(() => document.activeElement && document.activeElement.id === 'guess');

// --- touch device: no programmatic focus (keyboard stays down) ---
{
  const { ctx, p } = await page(false);
  await p.evaluate(() => { if(document.activeElement && document.activeElement.blur) document.activeElement.blur(); });
  checks.push(['touch: input NOT focused on load', await focused(p) === false]);
  await p.click('#skip');
  await p.waitForTimeout(80);
  checks.push(['touch: Skip does NOT focus input (no keyboard)', await focused(p) === false]);
  checks.push(['touch: skip still advanced clue', await p.evaluate(() => stage === 1 && guesses === 1)]);
  await p.click('#guess');                                   // tapping the box still focuses (normal typing)
  checks.push(['touch: tapping input focuses it', await focused(p) === true]);
  await ctx.close();
}

// --- desktop: auto-focus for type-to-play ---
{
  const { ctx, p } = await page(true);
  checks.push(['desktop: input auto-focused on load', await focused(p) === true]);
  await p.click('#skip');
  await p.waitForTimeout(80);
  checks.push(['desktop: input re-focused after Skip', await focused(p) === true]);
  await ctx.close();
}

await browser.close();
server.close();
report(checks);
