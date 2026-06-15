// End-to-end verification on the LIVE deployed site.
// Tests:
//  3a. No login redirect (fresh profile, no cookies)
//  3b. Prospects render
//  3c. State from migration visible (graveyard cards, broken flags)
//  3d. Clicking a seller button writes a prospect_action row
//  4.  Same state visible from a fully independent fresh browser context
//  5.  Activity feed renders recent actions

import { chromium } from 'playwright';

const URL = 'https://highlife-crm.vercel.app/';

async function loadFresh(label) {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    // Brand new profile per launch — guarantees no shared state
    extraHTTPHeaders: { 'Cache-Control': 'no-cache' },
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(`PAGEERROR: ${e.message}`));
  page.on('console', m => {
    if (m.type() === 'error') errors.push(`CONSOLE: ${m.text()}`);
  });
  const response = await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
  const finalUrl = page.url();
  console.log(`[${label}] initial status: ${response?.status()} final URL: ${finalUrl}`);

  // Wait up to 10s for HLDB.boot to populate the cache
  try {
    await page.waitForFunction(
      () => window.HLDB && (window.HLDB.getProspects() || []).length > 0,
      { timeout: 12000 }
    );
  } catch (e) {
    console.log(`[${label}] WAIT FAILED:`, e.message.slice(0, 200));
  }

  await page.waitForTimeout(1500);

  const state = await page.evaluate(() => {
    const all = window.HLDB?.getProspects() || [];
    const actions = window.HLDB?.getActions() || [];
    return {
      url: location.href,
      title: document.title,
      hlDb: !!window.HLDB,
      prospectCount: all.length,
      cardCount: document.querySelectorAll('.prospect-card').length,
      columnCount: document.querySelectorAll('.column').length,
      graveyardCount: all.filter(p => p.status === 'graveyard').length,
      inCrmCount: all.filter(p => p.status === 'added_to_crm').length,
      brokenFlagsCount: all.filter(p =>
        p.linkedin_status === 'broken' || p.instagram_status === 'broken' || p.youtube_status === 'broken'
      ).length,
      actionsCount: actions.length,
      sampleGraveyardIds: all.filter(p => p.status === 'graveyard').slice(0, 3).map(p => p.id + ':' + (p.name || '')),
      activityFabPresent: !!document.getElementById('activityFab'),
      actorPillPresent: !!document.getElementById('actorPill'),
    };
  });

  return { browser, ctx, page, state, errors };
}

// ── TEST 1: First fresh browser ────────────────────────────────────
console.log('\n=== Fresh browser #1 ===');
const r1 = await loadFresh('B1');
console.log('State:', JSON.stringify(r1.state, null, 2));
console.log('Errors:', r1.errors.length);
r1.errors.forEach(e => console.log('  ', e));

// Verify: no login redirect (URL stays at root, not /login.html)
const noRedirect = !r1.state.url.includes('/login');
console.log('Test 3a — no login redirect:', noRedirect ? 'PASS' : 'FAIL');
console.log('Test 3b — prospects render:', r1.state.cardCount > 0 ? `PASS (${r1.state.cardCount} cards)` : 'FAIL');
console.log('Test 3c — graveyard state visible:', r1.state.graveyardCount > 0 ? `PASS (${r1.state.graveyardCount})` : 'FAIL');
console.log('Test 3c — broken flags visible:', r1.state.brokenFlagsCount > 0 ? `PASS (${r1.state.brokenFlagsCount})` : 'FAIL');

// Test 3d: click a seller button and verify a new action row appears
console.log('\n=== Test 3d: seller-button writes prospect_action ===');
// Set actor first to avoid the prompt
await r1.page.evaluate(() => window.HLDB.setActor('James'));
const actionsBefore = await r1.page.evaluate(() => (window.HLDB.getActions() || []).length);
console.log('Actions before click:', actionsBefore);

// Find a seller button on the first card and click it
const sellerBtnClicked = await r1.page.evaluate(() => {
  const btn = document.querySelector('.seller-btn');
  if (!btn) return false;
  btn.click();
  return true;
});
console.log('Seller button clicked:', sellerBtnClicked);

// Wait for the optimistic local prepend + DB write
await r1.page.waitForTimeout(2000);
// Force refresh to pull from DB
await r1.page.evaluate(() => window.HLDB.refresh());
await r1.page.waitForTimeout(2000);

const actionsAfter = await r1.page.evaluate(() => {
  const a = window.HLDB.getActions() || [];
  return { count: a.length, latest: a.slice(0, 3).map(x => ({ type: x.action_type, actor: x.actor_name, pid: x.prospect_id })) };
});
console.log('Actions after click:', JSON.stringify(actionsAfter, null, 2));
console.log('Test 3d — new action row written:', (actionsAfter.count > actionsBefore) ? 'PASS' : 'FAIL');

// ── TEST 4: Second fully independent browser ──────────────────────
console.log('\n=== Fresh browser #2 (independent) ===');
const r2 = await loadFresh('B2');
console.log('State:', JSON.stringify(r2.state, null, 2));
console.log('Errors:', r2.errors.length);

const sharedBackendVisible = r2.state.prospectCount === r1.state.prospectCount;
console.log('Test 4 — shared backend:', sharedBackendVisible
  ? `PASS (both see ${r2.state.prospectCount} prospects)`
  : `FAIL (B1=${r1.state.prospectCount} B2=${r2.state.prospectCount})`);

// Test 5: activity feed UI
console.log('\n=== Test 5: activity panel ===');
const feedHTML = await r2.page.evaluate(() => {
  document.getElementById('activityFab').click();
  return document.getElementById('activityList').innerHTML.length;
});
console.log('Activity feed renders:', feedHTML > 50 ? `PASS (${feedHTML} chars)` : 'FAIL');

await r1.browser.close();
await r2.browser.close();
console.log('\n=== DONE ===');
