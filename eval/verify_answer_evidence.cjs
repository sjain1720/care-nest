// One real-policy request; replay the capture for desktop/phone layout checks.
// No existing user workspace is modified. Synthetic test guest is deleted.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const base = process.env.CARENEST_BASE_URL || 'http://127.0.0.1:8088';
const out = path.join(__dirname, 'results', 'answer-evidence', 'local');
fs.mkdirSync(out, { recursive: true });
const question = 'For cataract surgery on 2025-09-12, has my specified disease waiting period ended? What else needs confirmation?';
const report = { base, question, checks: [], note: 'One real answer; UI replays are not additional live AI observations.' };
function check(name, passed) { report.checks.push({ name, passed: !!passed }); if (!passed) throw Error(name); }
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const c = await browser.newContext({ viewport: { width: 1280, height: 650 } });
  try {
    await c.request.get(base + '/api/session/profile');
    await c.request.put(base + '/api/session/profile', { data: { displayName: 'Evidence review' } });
    check('Prepared example attached without re-ingestion', (await c.request.post(base + '/api/demo/ensure?workspace=example')).status() === 200);
    const factsResponse = await c.request.get(base + '/api/policy?workspace=example');
    check('Example policy available', factsResponse.status() === 200);
    const facts = await factsResponse.json();
    check('Prepared original Kotak policy selected', facts.planName.includes('Kotak'));
    report.periods = facts.waitingPeriods.map(w => ({ id: w.id, duration: w.duration, page: w.citation.page }));
    let capture;
    if (process.env.CARENEST_CAPTURE_PATH) {
      capture = JSON.parse(fs.readFileSync(process.env.CARENEST_CAPTURE_PATH, 'utf8'));
      report.captureReused = true; report.note = 'UI-only replay of an earlier real answer; no fresh AI call/timing.';
    } else {
      const start = Date.now();
      const response = await c.request.post(base + '/api/copilot/ask?workspace=example', { data: { question }, timeout: 120000 });
      report.elapsedSeconds = (Date.now() - start) / 1000;
      check('Actual AI request returned 200', response.status() === 200);
      capture = await response.json();
    }
    fs.writeFileSync(out + '/actual-answer.json', JSON.stringify(capture, null, 2));
    const answer = capture.answer;
    report.verdict = answer.verdict; report.checksFromApi = answer.verification?.checks;
    check('Answer carries server-authored checks', !!answer.verification);
    check('Original policy citations retained', answer.citations.length > 0);
    check('Explanation reviewed or explicitly limited to checked timing', answer.verification.checks.find(c => c.kind === 'support')?.status === 'passed'
      || (answer.verification.scope === 'timing_only' && answer.verification.checks.find(c => c.kind === 'support')?.status === 'not_run'));
    check('Backend date calculation attached', answer.verification.dates.length === 1);
    check('Real Kotak specific period is 12 months', answer.verification.dates[0].duration === '12 months');
    check('Date result uses recorded start and planned date', answer.verification.dates[0].endDate === '2025-03-12' && answer.verification.dates[0].comparisonDate === '2025-09-12');
    check('Timing does not become a coverage verdict', answer.verdict !== 'covered');
    check('Treatment listing is linked to the actual waiting rule', answer.verification.treatment?.treatment === 'Cataract'
      && answer.verification.treatment.ruleCitation.page === 18 && answer.verification.treatment.listCitation.page === 19);
    check('Both policy pages retained', [18, 19].every(page => answer.citations.some(c => c.page === page)));
    const p = await c.newPage(), errors = []; p.on('pageerror', e => errors.push(e.message));
    let replay = answer; const sent = [];
    await p.route('**/api/copilot/ask/stream*', route => {
      sent.push(route.request().postDataJSON().question);
      return route.fulfill({ status: 200, contentType: 'text/event-stream', body: `data: ${JSON.stringify({ type: 'answer', answer: replay })}\n\n` });
    });
    await p.goto(base + '/ask?workspace=example&q=' + encodeURIComponent(question), { waitUntil: 'networkidle' });
    const panel = p.locator('app-answer-evidence'); await panel.waitFor();
    check('Evidence starts compact', await panel.locator('details').first().getAttribute('open') === null);
    check('Check explanations start collapsed', await panel.locator('details.check-method').getAttribute('open') === null);
    check('Treatment proof is visible without expanding', await panel.locator('.checks li').filter({ hasText: 'Treatment listed' }).isVisible());
    await panel.getByText('See policy evidence and inputs', { exact: true }).click();
    check('Quotation is readable before opening PDF', await panel.locator('blockquote').count() > 0);
    check('Fictional start-date origin disclosed', (await panel.innerText()).includes('Fictional example start date'));
    await panel.screenshot({ path: out + '/evidence-expanded.png' });
    for (const size of [{ width: 1280, height: 650 }, { width: 390, height: 844 }]) {
      await p.setViewportSize(size);
      check(`${size.width}px no horizontal overflow`, await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      const input = await p.locator('app-chat-bar input[name="q"]').last().boundingBox();
      check(`${size.width}px composer remains visible`, input && input.y >= 0 && input.y + input.height <= size.height);
      await p.screenshot({ path: out + `/chat-${size.width}.png`, fullPage: true });
    }
    // Controlled missing-date state: checks date input/continuation UX, not model quality.
    replay = structuredClone(answer); replay.verification.dates = [];
    replay.verification.checks.find(c => c.kind === 'dates').status = 'not_confirmed';
    replay.verification.checks.find(c => c.kind === 'dates').label = 'Dates still need checking';
    replay.verification.missingInputs = ['What is your planned treatment date?'];
    await p.goto(base + '/ask?workspace=example&q=Check%20my%20waiting%20period', { waitUntil: 'networkidle' });
    const picker = p.getByLabel('Planned treatment date', { exact: true }).first(); await picker.waitFor();
    check('Missing date has a native date picker', await picker.getAttribute('type') === 'date');
    await picker.fill('2027-03-12'); await p.getByRole('button', { name: 'Check this date', exact: true }).first().click();
    await p.waitForFunction(() => document.querySelectorAll('app-answer-evidence').length === 2);
    check('Date picker continues scoped chat', sent.some(q => q.includes('My planned treatment date is 2027-03-12')));
    check('No JavaScript errors', errors.length === 0);
    report.passed = true;
  } catch (error) { report.passed = false; report.error = error.message; }
  finally {
    try { report.cleanupStatus = (await c.request.delete(base + '/api/session?workspace=general', { timeout: 60000 })).status(); } catch { report.cleanupStatus = 'failed'; }
    await browser.close(); fs.writeFileSync(out + '/report.json', JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report)); if (!report.passed || report.cleanupStatus !== 204) process.exitCode = 1;
  }
})();
