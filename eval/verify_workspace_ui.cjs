// Local acceptance: real stored fictional template, one synthetic personal bill upload, no answer-model evaluation.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const base = process.env.CARENEST_CHECK_URL || 'http://127.0.0.1:8088';
const out = path.join(__dirname, 'results', 'workspace-ui', 'local');
fs.mkdirSync(out, { recursive: true });
const report = { base, checks: [], mode: 'real cloud storage/owned workspaces; synthetic bill upload; greeting shortcut; controlled late-chat response' };
function check(name, passed) { report.checks.push({ name, passed: !!passed }); if (!passed) throw Error(name); }
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const p = await context.newPage();
  const errors = [], requests = [];
  p.on('pageerror', e => errors.push(e.message));
  p.on('request', r => { if (r.url().includes('/api/')) requests.push(r.url()); });
  async function json(url, opts) { const response = await context.request.get(base + url, opts); check('GET ' + url, response.ok()); return response.json(); }
  async function snap(name) { await p.screenshot({ path: path.join(out, name + '.png'), fullPage: true }); }
  async function switchTo(name) { await p.getByRole('button', { name: 'Switch workspace', exact: true }).click(); await p.getByRole('button', { name, exact: false }).click(); await p.locator('.workspace-dialog').waitFor({ state: 'hidden' }); }
  try {
    await p.goto(base, { waitUntil: 'networkidle' });
    check('Fresh Welcome does not read a case or policy', !requests.some(u => /\/api\/(policy|case)(\?|\/|$)/.test(u)));
    await snap('01-welcome');
    await p.locator('#ask-bar-hero').fill('Hi'); await p.locator('#ask-bar-hero').press('Enter');
    await p.getByRole('dialog', { name: 'How would you like to use CareNest?' }).waitFor();
    check('No chat request before workspace choice', !requests.some(u => u.includes('/copilot/ask')));
    await snap('02-workspace-choice');
    await p.getByRole('button', { name: 'Use my own documents', exact: false }).click();
    await p.getByText("Hi! I'm Nessi.", { exact: true }).waitFor({ timeout: 60000 });
    check('Pending first question continues after choice', await p.locator('.bubble-user').filter({ hasText: /^Hi$/ }).count() === 1);
    check('Personal starts without a demo policy', (await context.request.get(base + '/api/policy?workspace=personal')).status() === 404);
    await p.getByRole('button', { name: 'Hide the chat', exact: true }).click();
    await p.locator('.action-card[href^="/dashboard"]').click();
    await p.getByRole('heading', { name: 'Welcome, Shubham', exact: true }).waitFor();
    const example = await json('/api/case?workspace=example');
    const policy = await json('/api/policy?workspace=example');
    check('Fictional schedule renamed consistently', policy.members.some(m => m.name === 'Shubham Sharma') && !JSON.stringify(policy).includes('Ravi Sharma'));
    check('Dashboard keeps existing financial metrics', await p.getByText('₹38,000', { exact: true }).first().isVisible());
    await snap('03-example-dashboard');
    for (const [route, name, marker] of [
      ['/policy', '04-policy', 'app-document-preview iframe'], ['/bills', '05-bills', '.document-list-row'],
      ['/case', '06-claim', '#overview'], ['/case/bill', '07-bill-check', '#checks'],
      ['/case/settlement', '08-deductions', 'app-waterfall'],
    ]) {
      await p.goto(base + route + '?workspace=example', { waitUntil: 'networkidle' });
      await p.locator(marker).first().waitFor(); check(name + ' renders', true); await snap(name);
    }
    await p.goto(base + '/upload?workspace=example', { waitUntil: 'networkidle' });
    check('Upload always opens personal workspace', p.url().includes('workspace=personal'));
    check('Example bill not initially shown in personal workspace', (await context.request.get(base + '/api/case/bill?workspace=personal')).status() === 404);
    await snap('09-personal-upload');
    await p.locator('.upload-categories button').filter({ hasText: 'Hospital bill' }).click();
    const uploadResponse = p.waitForResponse(r => r.url().includes('/api/documents') && r.request().method() === 'POST', { timeout: 180000 });
    await p.locator('label.drop input[type=file]').setInputFiles(path.join(__dirname, '..', 'demo-data', 'hospital_bill.pdf'));
    const uploaded = await uploadResponse;
    check('Synthetic personal bill upload succeeds', uploaded.ok()); report.upload = await uploaded.json();
    check('Upload request is personal', uploaded.url().includes('workspace=personal'));
    await p.getByRole('link', { name: 'Check this bill', exact: true }).waitFor();
    const personalBill = await json('/api/case/bill?workspace=personal');
    check('Uploaded bill readable in personal workspace', personalBill.total === 246000);
    const personalCase = await json('/api/case?workspace=personal');
    check('Personal upload has no demo settlement', !personalCase.settlement && !personalCase.documents.some(d => d.type === 'Settlement letter'));
    const item = personalCase.checklist[0];
    const changed = item.status === 'requested' ? 'missing' : 'requested';
    check('Personal checklist editable', (await context.request.patch(base + '/api/case/checklist/' + item.id + '?workspace=personal', { data: { status: changed } })).ok());
    await p.goto(base + '/dashboard?workspace=personal', { waitUntil: 'networkidle' });
    await p.getByRole('heading', { name: 'Your health coverage, understood.', exact: true }).waitFor();
    await snap('10-personal-dashboard');
    await p.locator('header .brand').click();
    check('Welcome preserves selected personal workspace', (await p.locator('header .workspace-switch').innerText()).includes('My documents'));
    await switchTo('Try as Shubham');
    const restoredExample = await json('/api/case?workspace=example');
    check('Personal upload and edits do not alter fictional case', JSON.stringify(restoredExample) === JSON.stringify(example));
    await p.locator('header a[href^="/dashboard"]:visible').first().click();
    await p.getByRole('heading', { name: 'Welcome, Shubham', exact: true }).waitFor();
    await switchTo('Use my own documents');
    const restoredPersonal = await json('/api/case?workspace=personal');
    check('Switch restores personal checklist edits', restoredPersonal.checklist.find(x => x.id === item.id).status === changed);
    await p.reload({ waitUntil: 'networkidle' });
    check('Refresh preserves personal selection', p.url().includes('workspace=personal') && (await p.locator('header .workspace-switch').innerText()).includes('My documents'));
    // One delayed event verifies that in-flight personal replies never appear in the example chat.
    let release; const gate = new Promise(r => release = r); let seenPersonal = false;
    await p.route('**/api/copilot/ask/stream**', async route => { seenPersonal = route.request().url().includes('workspace=personal') && !route.request().postDataJSON().generalOnly; await gate; await route.fulfill({ status: 200, contentType: 'text/event-stream', body: 'data: ' + JSON.stringify({ type:'answer', answer:{ verdict:'info', headline:'Personal delayed response', summary:'Controlled scope check.', general:true, citations:[], toConfirm:[] } }) + '\n\n' }); });
    await p.locator('.chat-launcher').click(); await p.locator('#ask-bar').fill('Check my private document'); await p.locator('#ask-bar').press('Enter');
    await switchTo('Try as Shubham'); release(); await p.waitForTimeout(100);
    check('Request uses personal evidence scope', seenPersonal);
    check('Late personal answer absent from example', !(await p.locator('body').innerText()).includes('Personal delayed response'));
    await switchTo('Use my own documents'); await p.locator('.chat-launcher').click(); await p.getByText('Personal delayed response', { exact: true }).waitFor();
    check('Late answer retained in personal conversation', true); await p.unroute('**/api/copilot/ask/stream**');
    await p.setViewportSize({ width: 390, height: 844 });
    for (const [route, name] of [['/', '11-welcome-phone'], ['/dashboard?workspace=example', '12-dashboard-phone'], ['/policy?workspace=example', '13-policy-phone'], ['/bills?workspace=example', '14-bills-phone'], ['/case?workspace=example', '15-claim-phone'], ['/upload?workspace=personal', '16-upload-phone']]) {
      await p.goto(base + route, { waitUntil: 'networkidle' });
      check(name + ' has no horizontal overflow', await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)); await snap(name);
    }
    check('No JavaScript errors', errors.length === 0); report.browserErrors = errors;
    report.passed = true;
  } catch (e) { report.passed = false; report.error = e.message; await snap('failure'); }
  finally {
    try { report.cleanupStatus = (await context.request.delete(base + '/api/session?workspace=general', { timeout: 60000 })).status(); } catch { report.cleanupStatus = 'failed'; }
    await context.close(); await browser.close();
    fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report)); if (!report.passed || report.cleanupStatus !== 204) process.exitCode = 1;
  }
})();
