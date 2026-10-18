// UI-only replay. ALL /api requests are intercepted; no server workspace mutation or deletion.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
const base='http://127.0.0.1:8088',out=path.join(__dirname,'results/policy-facts'),answer=JSON.parse(fs.readFileSync(out+'/answer-fixture.json','utf8'));
const report={checks:[],note:'All API responses mocked; no session mutation/deletion, no live AI request.'};
function check(name,value){report.checks.push({name,passed:!!value});if(!value)throw Error(name);}
(async()=>{const b=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}),c=await b.newContext({viewport:{width:1280,height:700}}),p=await c.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
await c.route('**/api/**',r=>{
 const u=new URL(r.request().url()),key=u.pathname;
 if(key==='/api/copilot/ask/stream')return r.fulfill({status:200,contentType:'text/event-stream',body:`data: ${JSON.stringify({type:'answer',answer})}\n\n`});
 const file={'/api/policy':'policy','/api/case':'case','/api/case/bill':'bill','/api/case/settlement':'settlement','/api/claims':'claims'}[key];
 const json=file?JSON.parse(fs.readFileSync(path.join(__dirname,'../frontend/public/mocks',file+'.json'),'utf8')):key==='/api/session/profile'?{displayName:'UI fixture'}:{workspaceKey:'ui-fixture-only',ready:true,mode:'live_demo'};
 return r.fulfill({status:200,json});
});
try{
 await p.goto(base+'/ask?workspace=example&q='+encodeURIComponent('What is my room-rent limit?'),{waitUntil:'networkidle'});
 const card=p.locator('app-answer-card').last();await card.getByRole('heading',{name:'Room benefit: up to sum insured',exact:true}).waitFor();
 check('Direct factual answer visible',(await card.innerText()).includes('₹15,00,000'));
 check('No generic withholding headline',!(await card.innerText()).includes('Policy passages found; interpretation needs review'));
 await card.locator('app-answer-evidence .checks li').filter({hasText:'Interpretation not fully verified'}).waitFor();check('Failed interpretation disclosed',true);
 check('Small check note replaces large warning box',await card.locator('p[role="note"]').isVisible()&&await card.locator('.confirm').count()===0);
 check('Evidence collapsed initially',await card.locator('app-answer-evidence details').first().getAttribute('open')===null);
 await card.getByText('See policy evidence and inputs',{exact:true}).click();check('Three original-page quotations available',await card.locator('blockquote').count()===3);
 check('Failed check not green',await card.locator('app-answer-evidence .checks .unconfirmed').count()===1);
 for(const width of [1280,390]){await p.setViewportSize({width,height:width===390?844:700});await p.waitForTimeout(400);check(width+'px no overflow',await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await p.screenshot({path:out+'/source-facts-'+width+'.png',fullPage:true});}
 check('No JS errors',errors.length===0);report.passed=true;
}catch(e){report.passed=false;report.error=e.message;await p.screenshot({path:out+'/failure.png',fullPage:true}).catch(()=>{});}
finally{await b.close();fs.writeFileSync(out+'/ui-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));if(!report.passed)process.exitCode=1;}
})();
