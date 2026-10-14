/* Fresh browser guest: desktop/phone investigation and editable letter. Never sends a letter. */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const base = (process.argv[2] || '').replace(/\/$/, '');
const folder = process.argv[3];
if (!base || !folder) throw new Error('Usage: node verify_ui_journey.cjs URL REPORT_FOLDER');
fs.mkdirSync(folder, { recursive: true });
const report = { checks: [], allPassed: false };
const check = (name, ok) => {
  report.checks.push({ check: name, passed: !!ok });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`);
  if (!ok) throw new Error(name);
};
(async () => {
  let browser, context;
  try {
    browser = await chromium.launch({ headless: true, executablePath: process.env.CARENEST_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
    context = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: 'light' });
    await context.addInitScript(() => localStorage.setItem('carenest.live', JSON.stringify(['policy','ask','upload','case','bill','settlement','letter','query'])));
    const page = await context.newPage();
    await page.goto(base, { waitUntil: 'domcontentloaded' });
    const seeded = await context.request.post(base + '/api/demo/load', { timeout: 180000 });
    check('fictional browser guest seeded', seeded.ok());
    const read = await context.request.get(base + '/api/case/bill');
    const bill = await read.json();
    const reviewed = await context.request.put(base + '/api/case/bill', { data: { items: bill.items, statedTotal: bill.total } });
    check('synthetic extracted bill reviewed for this guest', reviewed.ok());
    await page.goto(base + '/case/settlement', { waitUntil: 'domcontentloaded' });
    const button = page.getByRole('button', { name: 'Investigate my decision', exact: true });
    await button.waitFor({ state: 'visible', timeout: 60000 });
    await button.click();
    await page.getByRole('heading', { name: 'Claim investigation: evidence and next steps', exact: true }).waitFor({ state: 'visible', timeout: 240000 });
    check('normal UI displays completed investigation', true);
    check('personalized checklist visible', await page.getByText('Your clarification checklist', { exact: true }).isVisible());
    check('opening an answer leaves its actions unobstructed', !(await page.getByRole('listbox').isVisible()));
    await page.screenshot({ path: path.join(folder, 'investigation-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(200);
    check('phone investigation page has no horizontal overflow', await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.screenshot({ path: path.join(folder, 'investigation-phone.png'), fullPage: true });
    await page.getByRole('link', { name: 'Edit the evidence-based letter', exact: true }).click();
    const editor = page.getByLabel('Letter text', { exact: true });
    await editor.waitFor({ state: 'visible', timeout: 60000 });
    const body = await editor.inputValue();
    check('letter uses investigation amounts and questions', body.includes('₹38,000') && body.length > 200);
    await editor.fill(body + '\n\n[Demo reviewer note]');
    check('letter can be edited without submitting', (await editor.inputValue()).includes('[Demo reviewer note]'));
    check('phone letter page has no horizontal overflow', await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.screenshot({ path: path.join(folder, 'letter-phone.png'), fullPage: true });
    report.allPassed = true;
  } catch (error) {
    report.errorType = error.name;
    report.error = String(error.message).slice(0, 3000);
  } finally {
    if (context) {
      try { const deleted = await context.request.delete(base + '/api/session', { timeout: 60000 }); if (!deleted.ok()) throw new Error('Cleanup failed'); }
      catch { report.cleanupFailed = true; report.allPassed = false; }
      await context.close();
    }
    if (browser) await browser.close();
    fs.writeFileSync(path.join(folder, 'report.json'), JSON.stringify(report, null, 2));
    if (!report.allPassed) process.exitCode = 1;
  }
})();
