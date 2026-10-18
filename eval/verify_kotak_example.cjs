// Real prepared data/storage and synthetic upload; no AI-answer quality evaluation.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const base=process.env.CARENEST_CHECK_URL||'http://127.0.0.1:8088';
const out=path.join(__dirname,'results','kotak-example','local');fs.mkdirSync(out,{recursive:true});
const report={base,checks:[],mode:'real data/storage, synthetic bill upload; no answer-model evaluation'};
function check(name,passed){report.checks.push({name,passed:!!passed});if(!passed)throw Error(name);}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const get=async(route)=>{const r=await context.request.get(base+route,{timeout:60000});if(!r.ok())throw Error(route+': '+r.status());return r.json();};
 try {
  await page.goto(base+'/policy?workspace=example',{waitUntil:'networkidle'});
  if (await page.locator('#visitor-name').count()) { await page.locator('#visitor-name').fill('Demo reviewer'); await page.getByRole('button',{name:'Continue',exact:true}).click(); await page.locator('#visitor-name').waitFor({state:'hidden'}); }
  await page.getByText('Original policy wording · fictional family selections',{exact:true}).waitFor();
  const policy=await get('/api/policy?workspace=example');
  check('Original Kotak, 43 pages and fictional 10 lakh cover',policy.pageCount===43&&policy.sumInsured===1000000&&/kotak/i.test(policy.planName));
  check('Mother enrolment explicitly fictional',policy.members.some(m=>m.name==='Mother (example)'&&m.relation==='Mother')&&policy.demoAssumptions.some(n=>n.includes('assumed enrolled')));
  check('Five watch-outs cite original pages',policy.traps.length===5&&policy.traps.every(t=>[17,18,22].includes(t.citation.page)&&t.citation.quote));
  const source=await context.request.get(base+'/api/policy/document?workspace=example');
  check('Policy byte-identical to original',crypto.createHash('sha256').update(await source.body()).digest('hex')==='0bd43987c8812a866229f93c6f238b9b9f67de5810b4fb520e503c600b0313fc');
  await page.screenshot({path:out+'/policy.png',fullPage:true});
  const bill=await get('/api/case/bill?workspace=example');
  check('Current bill: 15 charges, 3 pages, net 185000',bill.total===185000&&bill.items.length===15&&bill.pagesRead===3);
  check('No arithmetic or missing-page errors',!bill.checks.some(c=>['missing_pages','total_mismatch','line_arithmetic'].includes(c.kind)));
  const decision=await get('/api/case/settlement?workspace=example');
  check('Decision reconciles: 185000 - 20000 = 165000',decision.claimedAmount===185000&&decision.approvedAmount===165000&&decision.deductions.reduce((s,d)=>s+d.amount,0)===20000);
  let claims=await get('/api/claims?workspace=example');
  check('Two claims, previous closed',claims.length===2&&claims.some(c=>!c.current&&c.closed&&c.claimedAmount===73420));
  const coverage=await get('/api/coverage?workspace=example');
  check('Coverage: used 238420, remaining 761580',coverage.used===238420&&coverage.remaining===761580&&coverage.counted.length===2);
  await page.goto(base+'/bills?workspace=example',{waitUntil:'networkidle'});await page.getByRole('heading',{name:'Other claims and bills'}).waitFor();
  check('Both bill amounts visible',(await page.locator('main').innerText()).includes('₹1,85,000')&&(await page.locator('main').innerText()).includes('₹73,420'));
  await page.screenshot({path:out+'/bills.png',fullPage:true});
  await page.getByRole('button',{name:'Open claim',exact:false}).click();
  await page.waitForFunction(()=>document.querySelector('.document-list header h2')?.textContent.includes('Current'));
  await page.waitForTimeout(1500);
  check('Previous claim opened',(await get('/api/case/bill?workspace=example')).total===73420);
  check('Switching does not double count',(await get('/api/coverage?workspace=example')).remaining===761580);
  claims=await get('/api/claims?workspace=example');
  check('Reopen current claim',(await context.request.post(base+'/api/claims/'+claims.find(c=>!c.current).id+'/open?workspace=example')).ok());
  await page.goto(base+'/case?workspace=example',{waitUntil:'networkidle'});await page.locator('#overview').waitFor();await page.screenshot({path:out+'/claim.png',fullPage:true});
  await page.goto(base+'/upload?workspace=personal&type=Hospital%20bill',{waitUntil:'networkidle'});
  const upload=await context.request.post(base+'/api/documents?workspace=personal',{multipart:{docType:'Hospital bill',file:{name:'hospital_bill.pdf',mimeType:'application/pdf',buffer:fs.readFileSync(path.join(__dirname,'../demo-data/hospital_bill.pdf'))}},timeout:180000});
  check('Real synthetic personal upload succeeds',upload.ok());
  const personal=await get('/api/case/bill?workspace=personal');check('Personal bill isolated',personal.total===185000);
  check('Example reset succeeds',(await context.request.post(base+'/api/demo/reset?workspace=example',{timeout:60000})).ok());
  check('Personal data survives reset',JSON.stringify(await get('/api/case/bill?workspace=personal'))===JSON.stringify(personal));
  check('Reset recreates example',(await context.request.post(base+'/api/demo/ensure?workspace=example',{timeout:60000})).ok());
  check('Reset retains two claims',(await get('/api/claims?workspace=example')).length===2);
  await page.setViewportSize({width:390,height:844});
  for(const route of ['policy','bills','case']) {await page.goto(base+'/'+route+'?workspace=example',{waitUntil:'networkidle'});check(route+' phone no overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:out+'/'+route+'-phone.png',fullPage:true});}
  check('No browser errors',errors.length===0);report.passed=true;
 }catch(e){report.passed=false;report.error=e.message;await page.screenshot({path:out+'/failure.png',fullPage:true});}
 finally {try{report.cleanupStatus=(await context.request.delete(base+'/api/session?workspace=general',{timeout:60000})).status();}catch{report.cleanupStatus='failed';}await browser.close();fs.writeFileSync(out+'/report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));if(!report.passed||report.cleanupStatus!==204)process.exitCode=1;}
})();
