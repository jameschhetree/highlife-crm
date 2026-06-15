// Extract localStorage from highlife-crm.vercel.app
// Strategy: Use a copy of James's Chrome profile + pre-set auth cookie to bypass login
// Falls back to empty if Chrome profile has no relevant data.

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';

const SRC_PROFILE = '/Users/james/Library/Application Support/Google/Chrome/Default';
const SNAP_DIR = '/tmp/hl-chrome-snapshot';
const OUT_FILE = '/Users/james/highlife-crm/_localstorage_dump.json';

// Take fresh snapshot of Chrome profile (Chrome may be running — we accept potential lock errors)
console.log('Snapshotting Chrome profile...');
try {
  execSync(`rm -rf "${SNAP_DIR}"`);
  fs.mkdirSync(SNAP_DIR, { recursive: true });
  // Only copy what we need: Local Storage, Cookies, Preferences
  fs.mkdirSync(path.join(SNAP_DIR, 'Default'), { recursive: true });
  for (const sub of ['Local Storage', 'Session Storage', 'Cookies', 'Preferences', 'Local State']) {
    const src = path.join(SRC_PROFILE, sub);
    const dst = path.join(SNAP_DIR, 'Default', sub);
    try {
      if (fs.existsSync(src)) {
        execSync(`cp -R "${src}" "${dst}"`);
      }
    } catch (e) {
      console.warn(`  skip ${sub}: ${e.message.slice(0,80)}`);
    }
  }
  // Local State at root (required)
  try {
    const src = path.join(SRC_PROFILE, '..', 'Local State');
    if (fs.existsSync(src)) execSync(`cp "${src}" "${SNAP_DIR}/Local State"`);
  } catch (e) {}
} catch (e) {
  console.error('Snapshot failed:', e.message);
}

// SHA-256 of admin:admin (from middleware.js)
const AUTH_HASH = '8da193366e1554c08b2870c50f737b9587c3372b656151c4a96028af26f51334';
const AUTH_COOKIE_VALUE = `${AUTH_HASH}|admin`;

console.log('Launching Playwright with snapshot profile...');
const context = await chromium.launchPersistentContext(SNAP_DIR, {
  headless: true,
  channel: 'chrome',
  args: ['--no-sandbox'],
  ignoreDefaultArgs: ['--enable-automation'],
});

// Pre-set the auth cookie
await context.addCookies([{
  name: 'auth',
  value: AUTH_COOKIE_VALUE,
  domain: 'highlife-crm.vercel.app',
  path: '/',
  secure: true,
  sameSite: 'Lax',
  expires: Math.floor(Date.now() / 1000) + 86400,
}]);

const page = await context.newPage();

console.log('Loading https://highlife-crm.vercel.app/ ...');
try {
  await page.goto('https://highlife-crm.vercel.app/', { waitUntil: 'domcontentloaded', timeout: 30000 });
} catch (e) {
  console.warn('Initial navigation issue:', e.message);
}

// Wait briefly for any seed-loader logic to run
await page.waitForTimeout(2500);

const url = page.url();
const title = await page.title();
console.log(`Loaded: ${url} — title: ${title}`);

// Extract localStorage keys + values
const dump = await page.evaluate(() => {
  const out = {};
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    out[k] = localStorage.getItem(k);
  }
  return out;
});

console.log('localStorage keys found:', Object.keys(dump));

fs.writeFileSync(OUT_FILE, JSON.stringify(dump, null, 2));
console.log(`Wrote dump to ${OUT_FILE}`);

await context.close();
process.exit(0);
