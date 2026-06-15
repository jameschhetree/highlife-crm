// Quick local check — load page in Playwright, capture console errors, verify HLDB.boot ran and prospects rendered.
import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext();
const page = await ctx.newPage();

const errors = [];
page.on('pageerror', e => errors.push(`PAGEERROR: ${e.message}`));
page.on('console', m => {
  if (m.type() === 'error') errors.push(`CONSOLE: ${m.text()}`);
});

await page.goto('http://localhost:8765/index.html', { waitUntil: 'domcontentloaded', timeout: 15000 });

// Wait for HLDB boot
await page.waitForFunction(() => window.HLDB && (window.HLDB.getProspects() || []).length > 0, { timeout: 15000 }).catch(() => null);

const summary = await page.evaluate(() => ({
  hlDbLoaded: !!window.HLDB,
  prospectCount: (window.HLDB?.getProspects() || []).length,
  actionsCount: (window.HLDB?.getActions() || []).length,
  cardCount: document.querySelectorAll('.prospect-card').length,
  hasActivityFab: !!document.getElementById('activityFab'),
  hasActorPill: !!document.getElementById('actorPill'),
  title: document.title,
}));

console.log('Summary:', JSON.stringify(summary, null, 2));
console.log('Errors caught:', errors.length);
errors.forEach(e => console.log('  -', e));

await browser.close();
process.exit(errors.length ? 1 : 0);
