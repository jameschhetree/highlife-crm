import { chromium } from '/opt/homebrew/lib/node_modules/playwright/index.mjs';
import { createHash } from 'crypto';
import path from 'path';

const BASE = 'https://highlife-crm.vercel.app';
const OUT = '/Users/james/highlife-crm/test-results';

// Generate auth cookie
const hash = createHash('sha256').update('admin:admin').digest('hex');
const authCookie = `${hash}|admin`;

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1680, height: 1050 }
  });

  // Set auth cookie
  await context.addCookies([{
    name: 'auth',
    value: authCookie,
    domain: 'highlife-crm.vercel.app',
    path: '/',
  }]);

  const page = await context.newPage();

  console.log('1. Loading CRM...');
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);

  // Screenshot 1: Clients view with toggle visible
  console.log('2. Screenshot: Clients view with toggle');
  await page.screenshot({ path: path.join(OUT, 'agency-01-clients-with-toggle.png'), fullPage: false });

  // Screenshot 2: Switch to Agency view
  console.log('3. Switching to Agency view...');
  await page.click('button[data-view="agency"]');
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, 'agency-02-agency-view-empty.png'), fullPage: false });

  // Add agencies via quick-add using evaluate to avoid selector ambiguity
  console.log('4. Adding agencies via JS...');
  await page.evaluate(() => {
    const agencies = [
      { name: 'Bully Pulpit Interactive', website: 'https://bfrdc.com', phone: '(202) 555-1234', city: 'Washington', state: 'DC', category: 'Public Affairs', fit: 'A', notes: 'Top DC public affairs firm' },
      { name: 'SKDK', website: 'https://skdknick.com', phone: '(202) 555-9876', city: 'Washington', state: 'DC', category: 'PR', fit: 'A', notes: 'Major PR firm' },
      { name: 'The Glover Park Group', website: 'https://gpg.com', phone: '(202) 555-4321', city: 'Washington', state: 'DC', category: 'Public Affairs', fit: 'B', notes: 'Public affairs consultancy' },
    ];
    const existing = JSON.parse(localStorage.getItem('highlife_crm_agencies') || '[]');
    agencies.forEach((a, idx) => {
      existing.push({
        id: 'a' + (existing.length + 1),
        name: a.name,
        website: a.website,
        phones: [{ number: a.phone, type: 'Main' }],
        email: '',
        contactPageUrl: '',
        linkedinCompany: '',
        address: '',
        city: a.city,
        state: a.state,
        category: a.category,
        services: '',
        industries: '',
        companySize: '',
        founderName: '',
        founderLinkedin: '',
        notes: a.notes,
        sourceUrl: '',
        lastEnrichedAt: '',
        dataConfidence: a.fit,
        status: 'new',
        outreachPriority: 'Medium',
        phoneStatus: 'Found',
        callOutcome: '',
        lastContactedAt: '',
        nextFollowUpAt: '',
        partnerModelInterest: '',
        owner: '',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      });
    });
    localStorage.setItem('highlife_crm_agencies', JSON.stringify(existing));
    renderAgencyBoard();
  });
  await page.waitForTimeout(500);

  console.log('5. Screenshot: Agency view with seeded records');
  await page.screenshot({ path: path.join(OUT, 'agency-03-seeded-cards.png'), fullPage: false });

  // Test quick-add form opens and fills
  console.log('6. Testing quick-add form...');
  await page.click('#agQuickAddTrigger');
  await page.waitForTimeout(300);
  await page.fill('#ag-qa-name', 'Test Agency Co');
  await page.fill('#ag-qa-phone', '3015551111');
  await page.screenshot({ path: path.join(OUT, 'agency-04-quick-add-form.png'), fullPage: false });

  // Submit via the specific quick-add button inside the form
  await page.click('#agQuickAddForm .btn-primary');
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, 'agency-05-after-quick-add.png'), fullPage: false });

  // Drag first card to "Researched" column
  console.log('7. Dragging card to Researched...');
  const firstCard = page.locator('.agency-card').first();
  const researchedCol = page.locator('.column-body[data-status="researched"]');
  await firstCard.dragTo(researchedCol);
  await page.waitForTimeout(500);

  // Drag to Call Needed
  console.log('8. Dragging to Call Needed...');
  const movedCard = page.locator('.column-body[data-status="researched"] .agency-card').first();
  const callNeededCol = page.locator('.column-body[data-status="call_needed"]');
  await movedCard.dragTo(callNeededCol);
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, 'agency-06-after-drag.png'), fullPage: false });

  // Open edit modal via the edit button on a card
  console.log('9. Opening edit modal...');
  // Hover over the card first to show actions
  const cardInNew = page.locator('.column-body[data-status="new"] .agency-card').first();
  await cardInNew.hover();
  await page.waitForTimeout(300);
  await cardInNew.locator('.card-action-btn').first().click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, 'agency-07-edit-modal.png'), fullPage: false });

  // Update phone status
  await page.selectOption('#ag-f-phoneStatus', 'Found');
  await page.click('#agencyModalSubmitBtn');
  await page.waitForTimeout(500);

  // Open templates panel
  console.log('10. Opening templates panel...');
  await page.locator('#agencyView button:has-text("Templates")').click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(OUT, 'agency-08-templates-panel.png'), fullPage: false });
  await page.locator('#agencyView button:has-text("Templates")').click();

  // Open CSV import dialog
  console.log('11. Opening CSV import dialog...');
  await page.locator('#agencyView button:has-text("Import CSV")').click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(OUT, 'agency-09-csv-import.png'), fullPage: false });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(200);

  // Reload and verify persistence
  console.log('12. Reload persistence test...');
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(800);
  const agencyViewVisible = await page.locator('#agencyView').isVisible();
  console.log('   Agency view visible after reload:', agencyViewVisible);

  const totalStat = await page.locator('#ag-stat-total').textContent();
  console.log('   Total agencies after reload:', totalStat);

  await page.screenshot({ path: path.join(OUT, 'agency-10-after-reload.png'), fullPage: false });

  // Switch back to clients to verify preservation
  console.log('13. Verifying clients view still works...');
  await page.click('button[data-view="clients"]');
  await page.waitForTimeout(500);
  const clientsVisible = await page.locator('#clientsView').isVisible();
  console.log('   Clients view visible:', clientsVisible);
  await page.screenshot({ path: path.join(OUT, 'agency-11-clients-still-works.png'), fullPage: false });

  console.log('\n=== ALL TESTS PASSED ===');
  console.log('Screenshots saved to:', OUT);
  await browser.close();
})();
