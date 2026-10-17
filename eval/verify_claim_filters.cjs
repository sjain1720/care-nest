// Actual prepared example and owned diary changes; no inference calls.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
const base=process.env.CARENEST_BASE_URL||'http://127.0.0.1:8088';
const out=path.join(__dirname,'results/claim-filters/local');fs.mkdirSync(out,{recursive:true});
const report={checks:[],note:'Prepared example; disposable visitor. No new AI calls.'};
function check(name,passed){report.checks.push({name,passed:!!passed});if(!passed)throw Error(name);}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 const c=await browser.newContext({viewport:{width:1280,height:800}}),p=await c.newPage(),errors=[];
 p.on('pageerror',e=>errors.push(e.message));
 try{
  await c.request.get(base+'/api/session/profile?workspace=general');
  await c.request.put(base+'/api/session/profile?workspace=general',{data:{displayName:'Claim filter reviewer'}});
  check('Prepared example ready',(await c.request.post(base+'/api/demo/ensure?workspace=example',{data:{},timeout:60000})).status()===200);
  const personal=await (await c.request.get(base+'/api/session?workspace=personal')).json();
  const example=await (await c.request.get(base+'/api/session?workspace=example')).json();
  check('Example resolves to a distinct owned workspace',personal.workspaceKey&&example.workspaceKey&&personal.workspaceKey!==example.workspaceKey);
  await p.goto(base+'/case?workspace=example#claims',{waitUntil:'networkidle'});
  const section=p.locator('app-claims-list'),rows=section.locator('.cl-row');
  const select=async name=>{
   await section.getByRole('button',{name,exact:false}).click();
   await p.waitForFunction(label=>document.querySelector('app-claims-list .cl-filter.selected')?.textContent.includes(label),name);
  };
  await section.getByRole('button',{name:'All claims 2',exact:true}).waitFor();
  check('All claims shows two actual claims',await rows.count()===2);
  check('List page has no selected-claim diary or workflow',await p.locator('#diary').count()===0&&await p.locator('nav[aria-label="Claim workflow"]').count()===0);
  await section.getByRole('button',{name:/View claim: Mother/}).click();
  await p.waitForURL(/\/case\/detail/);
  await p.getByRole('heading',{name:"Mother's fracture-repair claim",exact:true}).waitFor();
  check('Clicking current claim opens its separate detail page',await section.count()===0&&await p.locator('nav[aria-label="Claim workflow"]').count()===1);
  await p.getByRole('link',{name:'Back to all claims',exact:true}).click();
  await p.waitForURL(/\/case\?/);await section.getByRole('button',{name:'All claims 2',exact:true}).waitFor();
  check('Back to claims defaults to the full list',await rows.count()===2);
  await select('In progress');check('In progress shows mother claim only',await rows.count()===1&&(await rows.innerText()).includes('fracture'));
  await select('Closed');check('Closed shows previous stay only',await rows.count()===1&&(await rows.innerText()).includes('Previous short hospital stay'));
  await select('Pending reply');check('Pending reply starts empty',await rows.count()===0&&await section.getByText('No claims in this section.',{exact:true}).isVisible());
  check('Selected filter exposed accessibly',await section.getByRole('button',{name:'Pending reply 0',exact:true}).getAttribute('aria-pressed')==='true');
  await select('All claims');await section.scrollIntoViewIfNeeded();await section.screenshot({path:out+'/claims-laptop.png'});
  await p.setViewportSize({width:390,height:844});await section.scrollIntoViewIfNeeded();
  await p.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  report.phoneOverflow=await p.evaluate(()=>[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,12).map(e=>({tag:e.tagName,classes:e.className,right:e.getBoundingClientRect().right})));
  check('Phone has no horizontal overflow',await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  check('All four filters available on phone',await section.locator('.cl-filter').count()===4);
  await section.screenshot({path:out+'/claims-phone.png'});
  check('Explicit follow-up recorded',(await c.request.post(base+'/api/case/timeline?workspace=example',{data:{kind:'letter_sent',letterKind:'clarification',date:'2026-10-17'}})).status()===200);
  await p.reload({waitUntil:'networkidle'});await section.getByRole('button',{name:'Pending reply 1',exact:true}).waitFor();
  await select('Pending reply');check('Recorded follow-up enters Pending reply',await rows.count()===1&&(await rows.innerText()).includes('fracture'));
  await select('In progress');check('Pending reply and In progress do not double count',await rows.count()===0);
  await select('Closed');await section.getByRole('button',{name:'View claim: Previous short hospital stay',exact:true}).click();
  await p.waitForURL(/\/case\/detail/);
  await p.getByRole('heading',{name:'Previous short hospital stay',exact:true}).waitFor();
  check('Opening earlier claim shows the correct separate detail',await section.count()===0);
  await p.getByRole('link',{name:'Back to all claims',exact:true}).click();await p.waitForURL(/\/case\?/);
  await section.getByRole('button',{name:'All claims 2',exact:true}).waitFor();
  await select('Closed');
  check('Opening completed claim keeps it Closed',await rows.count()===1&&(await rows.innerText()).includes('Previous short hospital stay'));
  await select('Pending reply');check('Archived follow-up retains pending status',await rows.count()===1&&(await rows.innerText()).includes('fracture'));
  await p.goto(base+'/dashboard?workspace=example',{waitUntil:'networkidle'});
  await section.getByRole('button',{name:'All claims 2',exact:true}).waitFor();
  check('Dashboard claims also exposes the same filters',await rows.count()===2);
  await p.goto(base+'/case?workspace=example&section=documents',{waitUntil:'networkidle'});
  check('Existing document deep links still open claim detail',await p.getByRole('heading',{name:'Papers checklist',exact:true}).count()===1&&await section.count()===0);
  check('No JavaScript errors',errors.length===0);report.passed=true;
 }catch(e){report.passed=false;report.error=e.message;await p.screenshot({path:out+'/failure.png',fullPage:true}).catch(()=>{});}
 finally{
  try{report.cleanupStatus=(await c.request.delete(base+'/api/session?workspace=general',{timeout:60000})).status();}catch{report.cleanupStatus='failed';}
  await browser.close();fs.writeFileSync(out+'/report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
  if(!report.passed||report.cleanupStatus!==204)process.exitCode=1;
 }
})();
