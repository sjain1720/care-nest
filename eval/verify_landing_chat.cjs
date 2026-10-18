/* Controlled browser acceptance: no Google calls; synthetic API responses only. */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const base = (process.argv[2] || 'http://127.0.0.1:8084').replace(/\/$/, '');
const folder = process.argv[3] || 'eval/results/landing-chat-local';
const report = { mode: 'controlled synthetic API fixtures; not live AI evidence', checks: [], allPassed: false };
fs.mkdirSync(folder, { recursive: true });
const fixture = name => JSON.parse(fs.readFileSync(path.join(__dirname, '../frontend/public/mocks', name + '.json'), 'utf8'));
function check(name, ok) { report.checks.push({ check: name, passed: !!ok }); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`); if (!ok) throw new Error(name); }
(async () => {
  let browser, activePage;
  const states = [];
  const contexts = [];
  try {
    browser = await chromium.launch({ headless: true, executablePath: process.env.CARENEST_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
    async function guest({ phone = false, personal = false, mock = false, motion = 'reduce' } = {}) {
      const context = await browser.newContext({ viewport: phone ? { width: 390, height: 844 } : { width: 1440, height: 1000 }, reducedMotion: motion }); contexts.push(context);
      if (mock) await context.addInitScript(() => localStorage.setItem('carenest.live', '[]'));
      const state = { loaded: personal, demo: false, posts: [], mockReads: 0, demoPosts: 0, failDemo: false, errors: [] };
      await context.route('**/mocks/**', async route => { state.mockReads++; await route.continue(); });
      await context.route('**/api/**', async route => {
        const req = route.request(), url = new URL(req.url()), endpoint = url.pathname;
        const json = (data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
        if (endpoint === '/api/health') return json({ status: 'ok', service: 'carenest' });
        if (endpoint === '/api/session') return json({ expiresAt: '2026-10-22T12:00:00Z', mode: state.demo ? 'live_demo' : 'guest' });
        if (endpoint === '/api/demo/load') {
          state.demoPosts++;
          if (state.failDemo) { state.failDemo = false; return json({ detail: 'Synthetic transient demo failure; retry.' }, 502); }
          state.loaded = true; state.demo = true; return json({ loaded: [] });
        }
        if (endpoint === '/api/copilot/ask/stream') {
          let release; const gate = new Promise(resolve => { release = resolve; });
          state.posts.push({ body: req.postDataJSON(), release }); await gate;
          return route.fulfill({ contentType: 'text/event-stream', body: 'data: ' + JSON.stringify({ type: 'answer', answer: { verdict: 'info', headline: 'A waiting period needs a policy start date', summary: 'General guidance: check your policy wording and schedule before relying on a date.', citations: [], toConfirm: ['Add your policy for a personal answer.'], nextAction: { label: 'Add your policy', route: '/upload' }, general: true } }) + '\n\n' });
        }
        if (endpoint === '/api/claims') return json(state.loaded ? fixture('claims') : []);
        const files = { '/api/policy': 'policy', '/api/case': 'case', '/api/case/bill': 'bill', '/api/case/settlement': 'settlement' };
        if (files[endpoint]) return state.loaded ? json(fixture(files[endpoint])) : json({ detail: 'Not uploaded yet' }, 404);
        return json({ detail: 'No synthetic fixture' }, 404);
      });
      const page = await context.newPage(); activePage = page; states.push(state); page.setDefaultTimeout(15000); page.on('pageerror', error => state.errors.push(error.message));
      await page.goto(base, { waitUntil: 'networkidle' });
      await page.getByRole('heading', { name: 'Health insurance, made simple.' }).waitFor();
      return { page, state };
    }
    const { page, state } = await guest();
    check('fresh visitor uses live APIs without reading mock documents', state.mockReads === 0);
    check('landing contains no fictional patient, money or claim progress', !(await page.locator('main').innerText()).match(/Ravi Sharma|Kamala|₹|steps done/) && await page.locator('.m-progress').count() === 0);
    check('only one landing composer is visible', await page.locator('input:visible').count() === 1);
    await page.screenshot({ path: path.join(folder, 'landing-desktop.png'), fullPage: true });
    const entry = page.getByRole('combobox', { name: 'Ask CareNest a question, or find something', exact: true });
    await entry.fill('What is a waiting period?'); await entry.press('Enter');
    await page.getByRole('button', { name: 'Hide the chat', exact: true }).waitFor();
    await page.waitForFunction(() => !!document.querySelector('.bar.busy'));
    check('landing submit starts exactly one guest request', state.posts.length === 1 && !!state.posts[0].body.conversationId);
    await page.getByRole('link', { name: 'My policy', exact: true }).click();
    await page.waitForURL('**/policy');
    check('panel stays open through navigation during generation', await page.getByRole('dialog').isVisible());
    await page.getByRole('button', { name: 'Open the chat as a full page' }).click();
    await page.waitForURL('**/ask');
    check('maximize keeps pending question and one composer', state.posts.length === 1 && await page.locator('input:visible').count() === 1 && (await page.locator('.messages').innerText()).includes('What is a waiting period?'));
    await page.getByRole('button', { name: 'Return to side panel' }).click();
    await page.waitForURL('**/policy');
    check('return restores source page and active panel', await page.getByRole('dialog').isVisible() && state.posts.length === 1);
    await page.getByRole('button', { name: 'Hide the chat', exact: true }).click();
    await page.getByRole('button', { name: 'Open chat, CareNest is thinking' }).waitFor();
    await page.getByRole('link', { name: 'CareNest home', exact: true }).click();
    await page.getByRole('heading', { name: 'Health insurance, made simple.' }).waitFor();
    state.posts[0].release();
    await page.getByRole('button', { name: 'Open chat, new answer' }).waitFor();
    await page.getByRole('button', { name: 'Open chat, new answer' }).click();
    await page.getByRole('heading', { name: 'A waiting period needs a policy start date', exact: true }).waitFor();
    check('answer arrives after hiding and navigation without resending', state.posts.length === 1);
    await page.getByRole('button', { name: 'Open the chat as a full page' }).click();
    await page.waitForURL('**/ask');
    await page.screenshot({ path: path.join(folder, 'chat-desktop.png'), fullPage: true });
    await page.getByRole('link', { name: 'My policy', exact: true }).click();
    await page.waitForURL('**/policy');
    check('leaving full chat reopens existing conversation on desktop', await page.getByRole('dialog').isVisible());
    await page.getByRole('button', { name: 'Hide the chat', exact: true }).click();
    await page.getByRole('link', { name: 'CareNest home', exact: true }).click();
    await page.getByRole('heading', { name: 'Health insurance, made simple.' }).waitFor();
    check('demo never auto-loads', state.demoPosts === 0);
    state.failDemo = true;
    const demo = page.locator('button.action-card').filter({ has: page.getByRole('heading', { name: 'Explore demo', exact: true }) });
    await demo.click(); await page.getByRole('alert').waitFor();
    check('failed demo stays on landing with retry', new URL(page.url()).pathname === '/' && await demo.isEnabled());
    await demo.click(); await page.waitForURL('**/case');
    check('explicit successful demo loads then opens claim overview', state.demoPosts === 2 && state.demo);
    await page.getByRole('link', { name: 'CareNest home', exact: true }).click();
    await page.getByRole('heading', { name: 'Health insurance, made simple.' }).waitFor();
    check('loaded demo remains a landing page without sample figures', !(await page.locator('main').innerText()).match(/₹|Ravi Sharma|Kamala/));
    check('no horizontal desktop overflow', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));

    const own = await guest({ personal: true });
    await own.page.locator('button.action-card').filter({ has: own.page.getByRole('heading', { name: 'Explore demo', exact: true }) }).click();
    await own.page.getByRole('alert').waitFor();
    check('existing documents prevent one-click demo mixing', own.state.demoPosts === 0 && (await own.page.getByRole('alert').innerText()).includes('already has documents'));
    const preview = await guest({ mock: true });
    check('explicit saved mock preference remains visible and honored', preview.state.mockReads > 0 && (await preview.page.locator('.mode').innerText()).includes('Mock preview'));

    const mobile = await guest({ phone: true });
    await mobile.page.screenshot({ path: path.join(folder, 'landing-phone.png'), fullPage: true });
    check('phone landing has one composer and no horizontal overflow', await mobile.page.locator('input:visible').count() === 1 && await mobile.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await mobile.page.getByRole('button', { name: /Ask CareNest.*Talk to CareNest AI/ }).click();
    await mobile.page.getByRole('button', { name: 'Open the chat as a full page' }).click();
    await mobile.page.waitForURL('**/ask');
    check('phone chat has one composer and no horizontal overflow', await mobile.page.locator('input:visible').count() === 1 && await mobile.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await mobile.page.screenshot({ path: path.join(folder, 'chat-phone.png'), fullPage: true });
    await mobile.page.getByRole('button', { name: 'Return to side panel' }).click();
    await mobile.page.waitForURL(base + '/');
    await mobile.page.getByRole('button', { name: 'Hide the chat', exact: true }).click();
    await mobile.page.getByRole('dialog').waitFor({ state: 'hidden' });
    check('hidden phone panel leaves no mounted composer', await mobile.page.locator('#ask-bar').count() === 0);
    check('phone return and hide reveal the original landing page', await mobile.page.getByRole('heading', { name: 'Health insurance, made simple.' }).isVisible());
    const phoneEntry = mobile.page.locator('#ask-bar-hero');
    await phoneEntry.fill('What is a waiting period?');
    await mobile.page.getByRole('option').filter({ hasText: 'Ask: \"What is a waiting period?\"' }).waitFor();
    await phoneEntry.press('Enter');
    await mobile.page.getByRole('button', { name: 'Hide the chat', exact: true }).waitFor();
    await mobile.page.getByRole('button', { name: 'Hide the chat', exact: true }).click();
    await mobile.page.getByRole('link', { name: 'My policy', exact: true }).click();
    await mobile.page.waitForURL('**/policy');
    await mobile.page.getByRole('button', { name: 'Open chat, CareNest is thinking' }).waitFor();
    check('phone can navigate with a hidden pending response', mobile.state.posts.length === 1);
    mobile.state.posts[0].release();
    await mobile.page.locator('.chat-launcher').filter({ hasText: 'New answer' }).click();
    await mobile.page.getByRole('heading', { name: 'A waiting period needs a policy start date', exact: true }).waitFor();
    check('phone receives the same response after navigation', mobile.state.posts.length === 1);
    await mobile.page.screenshot({ path: path.join(folder, 'conversation-phone.png'), fullPage: false });
    const reduced = await guest();
    const reducedPrompt = await reduced.page.locator('.ph-topic').innerText();
    const animated = await guest({ motion: 'no-preference' });
    const firstPrompt = await animated.page.locator('.ph-topic').innerText();
    await animated.page.waitForFunction(first => document.querySelector('.ph-topic')?.textContent.trim() !== first, firstPrompt, { timeout: 7000 });
    check('search suggestions rotate when idle', true);
    await animated.page.getByRole('combobox').focus();
    const focusedPrompt = await animated.page.locator('.ph-topic').innerText();
    await animated.page.waitForTimeout(3500);
    check('search suggestions pause while input is focused', await animated.page.locator('.ph-topic').innerText() === focusedPrompt);
    await animated.page.getByRole('combobox').fill('room rent');
    check('suggestions never replace typed search text', await animated.page.getByRole('combobox').inputValue() === 'room rent');
    check('reduced motion keeps a stable suggestion', await reduced.page.locator('.ph-topic').innerText() === reducedPrompt);
    await animated.page.getByRole('link', { name: 'Chat', exact: true }).click();
    await animated.page.waitForURL('**/ask');
    await animated.page.getByRole('combobox').focus();
    const desktopSuggestions = animated.page.getByRole('listbox');
    await desktopSuggestions.waitFor();
    const desktopBounds = await desktopSuggestions.boundingBox();
    check('full-chat desktop suggestions fit inside visible screen', desktopBounds && desktopBounds.y >= 0 && desktopBounds.y + desktopBounds.height <= animated.page.viewportSize().height);
    await mobile.page.getByRole('button', { name: 'Open the chat as a full page' }).click();
    await mobile.page.waitForURL('**/ask');
    await mobile.page.getByRole('combobox').focus();
    const phoneSuggestions = mobile.page.getByRole('listbox');
    await phoneSuggestions.waitFor();
    const phoneBounds = await phoneSuggestions.boundingBox();
    check('full-chat phone suggestions fit inside visible screen', phoneBounds && phoneBounds.y >= 0 && phoneBounds.y + phoneBounds.height <= mobile.page.viewportSize().height);
    await mobile.page.screenshot({ path: path.join(folder, 'chat-suggestions-phone.png') });
    await mobile.page.getByRole('combobox').press('Escape');
    await mobile.page.getByRole('link', { name: 'Add your policy', exact: true }).click();
    await mobile.page.waitForURL('**/upload');
    await mobile.page.getByRole('button', { name: 'Ask CareNest', exact: true }).click();
    await mobile.page.getByRole('link', { name: 'Add your policy', exact: true }).click();
    await mobile.page.getByRole('dialog').waitFor({ state: 'hidden' });
    check('phone chat action reveals upload even when already on that route', new URL(mobile.page.url()).pathname === '/upload' && mobile.state.posts.length === 1);
    check('no browser runtime errors across fresh, demo, personal, mock and phone states', states.every(s => s.errors.length === 0));
    report.allPassed = true;
  } catch (error) { report.error = String(error.message).slice(0, 2200); report.debug = states.map(s => ({ errors: s.errors, requests: s.posts.length })); if (activePage) report.inputs = await activePage.locator('input').evaluateAll(inputs => inputs.map(i => ({id:i.id,value:i.value,visible:!!i.offsetParent,form:!!i.form,expanded:i.getAttribute('aria-expanded')}))); if (activePage) await activePage.screenshot({ path: path.join(folder, 'failure.png') }); console.log('ERROR', report.error, JSON.stringify(report.debug)); }
  finally {
    for (const context of contexts) await context.close();
    if (browser) await browser.close();
    fs.writeFileSync(path.join(folder, 'report.json'), JSON.stringify(report, null, 2));
    if (!report.allPassed) process.exitCode = 1;
  }
})();
