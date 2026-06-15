import { chromium } from 'playwright';

const URL = 'https://highlife-crm.vercel.app';
const AUTH_COOKIE = '8da193366e1554c08b2870c50f737b9587c3372b656151c4a96028af26f51334|admin';

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });

  // Set auth cookie
  await context.addCookies([{
    name: 'auth',
    value: AUTH_COOKIE,
    domain: 'highlife-crm.vercel.app',
    path: '/'
  }]);

  const page = await context.newPage();
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });

  // Wait for page to load and board to render
  await page.waitForSelector('#board', { timeout: 15000 });
  await page.waitForTimeout(2000);

  // Inject sample prospects with recent dates and URLs for testing
  await page.evaluate(() => {
    const STORAGE_KEY = 'highlife_crm_prospects';
    const existing = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');

    const testProspects = [
      {
        id: 'test_clay_1',
        name: 'Sarah Mitchell',
        jobTitle: 'Podcast Host',
        company: 'The Daily Brief',
        source: 'LinkedIn',
        email: '',
        phone: '',
        linkedin: 'https://www.linkedin.com/in/sarahmitchell/',
        instagram: 'https://www.instagram.com/sarahmitchell/',
        package: 'Podcast Launch Kit',
        status: 'prospect',
        lastContact: '',
        notes: 'Test prospect for Clay panel',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        rating: null,
        feedback: '',
        ratedAt: null,
        graveyard_reason: null,
        twitter: 'https://x.com/sarahmitchell'
      },
      {
        id: 'test_clay_2',
        name: 'Marcus Chen',
        jobTitle: 'Political Analyst',
        company: 'DC Insight',
        source: 'LinkedIn',
        email: 'marcus@dcinsight.com',
        phone: '',
        linkedin: 'https://www.linkedin.com/in/marcuschen/',
        instagram: '',
        package: 'CEO Brand Suite',
        status: 'prospect',
        lastContact: '',
        notes: '',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        rating: null,
        feedback: '',
        ratedAt: null,
        graveyard_reason: null,
      },
      {
        id: 'test_clay_3',
        name: 'Denise Washington',
        jobTitle: 'Founder',
        company: 'Black Voices Media',
        source: 'Instagram',
        email: '',
        phone: '',
        linkedin: 'https://www.linkedin.com/in/denisewashington/',
        instagram: 'https://www.instagram.com/denisewash/',
        package: 'Content Sprint',
        status: 'prospect',
        lastContact: '',
        notes: '',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        rating: null,
        feedback: '',
        ratedAt: null,
        graveyard_reason: null,
      },
      {
        id: 'test_clay_4',
        name: 'James Rodriguez',
        jobTitle: 'Show Host',
        company: 'Capitol Conversations',
        source: 'Referral',
        email: '',
        phone: '',
        linkedin: '',
        instagram: 'https://www.instagram.com/jamesrod/',
        package: 'Monthly Creator',
        status: 'prospect',
        lastContact: '',
        notes: '',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        rating: null,
        feedback: '',
        ratedAt: null,
        graveyard_reason: null,
      }
    ];

    // Remove old test prospects
    const cleaned = existing.filter(p => !p.id.startsWith('test_clay_'));
    cleaned.push(...testProspects);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cleaned));
  });

  // Reload to pick up the test data
  await page.reload({ waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForSelector('#board', { timeout: 15000 });
  await page.waitForTimeout(2000);

  // Screenshot 1: Panel collapsed showing count
  const trigger = page.locator('#clayPanelTrigger');
  await trigger.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);

  await page.screenshot({
    path: '/Users/james/highlife-crm/test-results/clay-01-collapsed.png',
    clip: {
      x: 0,
      y: 0,
      width: 1440,
      height: 700
    }
  });
  console.log('Screenshot 1: clay-01-collapsed.png');

  // Click to expand
  await trigger.click();
  await page.waitForTimeout(800);

  // Screenshot 2: Panel expanded with textarea
  const section = page.locator('#clayPanelSection');
  await section.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);

  await page.screenshot({
    path: '/Users/james/highlife-crm/test-results/clay-02-expanded.png',
    clip: {
      x: 0,
      y: 0,
      width: 1440,
      height: 900
    }
  });
  console.log('Screenshot 2: clay-02-expanded.png');

  // Click "Mark All as Pushed"
  const markBtn = page.locator('button:has-text("Mark All as Pushed")');
  await markBtn.click();
  await page.waitForTimeout(1000);

  // Screenshot 3: After marking as pushed - empty state
  await page.screenshot({
    path: '/Users/james/highlife-crm/test-results/clay-03-pushed.png',
    clip: {
      x: 0,
      y: 0,
      width: 1440,
      height: 700
    }
  });
  console.log('Screenshot 3: clay-03-pushed.png');

  // Cleanup test data
  await page.evaluate(() => {
    const STORAGE_KEY = 'highlife_crm_prospects';
    const existing = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    const cleaned = existing.filter(p => !p.id.startsWith('test_clay_'));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cleaned));
  });

  await browser.close();
  console.log('All screenshots captured successfully.');
})();
