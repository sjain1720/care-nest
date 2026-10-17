const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const base='http://127.0.0.1:8088', out=path.join(__dirname,'results','context-bill-reliability','local');
fs.mkdirSync(out,{recursive:true}); const report={checks:[],note:'One real bill comparison; general context checks use deterministic personal-policy request, not mock policy answers.'};
function check(name,value){report.checks.push({name,passed:!!value});if(!value)throw Error(name);}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}),contexts=[];
 try {
  const c=await browser.newContext({viewport:{width:1280,height:720}});contexts.push(c);
  await c.request.get(base+'/api/session/profile');await c.request.put(base+'/api/session/profile',{data:{displayName:'Context review'}});
  await c.addInitScript(()=>{sessionStorage.setItem('carenest.workspace.choice','example');localStorage.setItem('carenest.live','[]');});
  const p=await c.newPage(), requests=[];p.on('request',r=>requests.push(r.url()));
  await p.goto(base,{waitUntil:'networkidle'});
  check('Welcome does not attach saved example',!requests.some(u=>u.includes('/api/demo/ensure')));
  await p.goto(base+'/ask?workspace=general',{waitUntil:'networkidle'});
  const responsePromise=p.waitForResponse(r=>r.url().includes('/api/copilot/ask/stream'));
  await p.locator('input[name="q"]').last().fill('What is my room-rent limit?');await p.locator('input[name="q"]').last().press('Enter');
  const response=await responsePromise, request=response.request().postDataJSON();
  check('General mode uses live API even with old mock setting',response.status()===200&&request.generalOnly===true);
  check('Request is explicitly general workspace',new URL(response.url()).searchParams.get('workspace')==='general');
  await p.getByRole('heading',{name:'I need your policy to answer that',exact:true}).waitFor();
  check('Own-cover question asks for upload',await p.getByRole('link',{name:'Upload your policy',exact:true}).isVisible());
  check('No synthetic QA was loaded',!requests.some(u=>u.includes('/mocks/qa.json')));
  await p.goto(base+'/ask',{waitUntil:'networkidle'});
  check('Unscoped chat is general, despite remembered example',!(await p.locator('main').innerText()).includes('Your fictional example workspace'));
  await p.goto(base+'/ask?workspace=personal',{waitUntil:'networkidle'});
  const own=await c.request.post(base+'/api/copilot/ask?workspace=personal',{data:{question:'What is my room-rent limit?'}});
  check('Empty personal workspace asks for own policy',(await own.json()).answer.nextAction.route==='/upload');
  const c2=await browser.newContext({viewport:{width:1280,height:720}});contexts.push(c2);
  await c2.request.get(base+'/api/session/profile');await c2.request.put(base+'/api/session/profile',{data:{displayName:'Bill review'}});
  check('Prepared example attached',(await c2.request.post(base+'/api/demo/ensure?workspace=example')).status()===200);
  const bill=await(await c2.request.get(base+'/api/case/bill?workspace=example')).json();
  check('Authored example bill reviewed for this test visitor',(await c2.request.put(base+'/api/case/bill?workspace=example',{data:{statedTotal:bill.total,items:bill.items.map(r=>({description:r.description,category:r.category,amount:r.amount,page:r.page,rate:r.rate,qty:r.qty}))}})).status()===200);
  const start=Date.now(),compared=await c2.request.post(base+'/api/case/bill/evidence?workspace=example',{timeout:120000});report.billElapsedSeconds=(Date.now()-start)/1000;
  check('Real comparison completes',compared.status()===200);const analysis=await compared.json();fs.writeFileSync(out+'/bill-evidence.json',JSON.stringify(analysis,null,2));
  const room=analysis.rows.find(r=>r.id===bill.items.find(i=>i.category==='room').id);
  check('Room has a real source passage',room?.assessment==='related_clause'&&room.citations.length>0);
  check('Room source remains contextual, not coverage approval',!/(fully covered|guaranteed|will be paid)/i.test(room.explanation));
  report.matched=analysis.rows.filter(r=>r.assessment==='related_clause').length;report.pending=analysis.rows.length-report.matched;
  const p2=await c2.newPage();await p2.goto(base+'/case/bill?workspace=example',{waitUntil:'networkidle'});
  await p2.getByRole('heading',{name:'Policy references for your bill',exact:true}).waitFor();
  const pending=p2.locator('#policy-evidence details');
  check('Unresolved charges are grouped honestly',report.pending===0||await pending.count()>0);
  if(report.pending)check('Clarification group starts collapsed',await pending.getAttribute('open')===null);
  check('Old repeated failure copy removed',!(await p2.locator('#policy-evidence').innerText()).includes('No verified applicable wording'));
  await p2.locator('#policy-evidence').screenshot({path:out+'/bill-policy-references.png'});report.passed=true;
 }catch(error){report.passed=false;report.error=error.message;}
 finally {report.cleanup=[];for(const c of contexts){try{report.cleanup.push((await c.request.delete(base+'/api/session?workspace=general',{timeout:60000})).status());}catch{report.cleanup.push('failed');}}await browser.close();fs.writeFileSync(out+'/report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));if(!report.passed||report.cleanup.some(c=>c!==204))process.exitCode=1;}
})();
