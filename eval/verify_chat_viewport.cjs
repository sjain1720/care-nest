// Replays a captured answer to check layout only; no AI requests.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
const base='http://127.0.0.1:8088',out=path.join(__dirname,'results/chat-viewport');fs.mkdirSync(out,{recursive:true});
const captured=JSON.parse(fs.readFileSync(path.join(__dirname,'results/j0-review/local/capture.json'))).turns[0].response.answer;
const report={mode:'captured-answer presentation check; no model calls',checks:[]};const check=(name,v)=>{report.checks.push({name,passed:!!v});if(!v)throw Error(name);};
(async()=>{const b=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}),c=await b.newContext({viewport:{width:1280,height:650},reducedMotion:'reduce'}),p=await c.newPage();try{
await p.goto(base,{waitUntil:'networkidle'});await p.locator('#visitor-name').fill('Viewport review');await p.getByRole('button',{name:'Continue',exact:true}).click();await p.locator('#visitor-name').waitFor({state:'hidden'});
await c.request.post(base+'/api/demo/ensure?workspace=example',{data:{},timeout:60000});await p.route('**/api/copilot/ask/stream?*',r=>r.fulfill({contentType:'text/event-stream',body:'data: '+JSON.stringify({type:'answer',answer:captured})+'\n\n'}));
await p.goto(base+'/ask?workspace=example',{waitUntil:'networkidle'});await p.getByRole('button',{name:'Why was money deducted from my claim?',exact:true}).click();await p.getByRole('heading',{name:'Claim investigation: evidence and next steps',exact:true}).waitFor();
for(const [width,height] of [[1280,650],[1440,720],[390,750]]){
 await p.setViewportSize({width,height});await p.locator('.messages').evaluate(e=>{e.scrollTop=e.scrollHeight;});
 check(width+' composer fully visible',await p.locator('.composer').evaluate(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight+1;}));
 check(width+' no outer vertical or horizontal scrolling',await p.evaluate(()=>document.documentElement.scrollHeight<=innerHeight+1&&document.documentElement.scrollWidth<=innerWidth+1));
 check(width+' conversation has its own scroll',await p.locator('.messages').evaluate(e=>e.scrollHeight>e.clientHeight));
 await p.screenshot({path:out+'/chat-'+width+'.png',animations:'disabled'});
}
await p.setViewportSize({width:1280,height:650});await p.goto(base+'/case?workspace=example',{waitUntil:'networkidle'});check('Claim and follow-up labels distinct',(await p.locator('main').innerText()).includes('Claim submitted')&&(await p.locator('main').innerText()).includes('Follow-up sent'));report.passed=true;
}catch(e){report.error=e.message;report.passed=false;}finally{report.cleanupStatus=(await c.request.delete(base+'/api/session?workspace=general',{timeout:60000})).status();await b.close();fs.writeFileSync(out+'/report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));if(!report.passed||report.cleanupStatus!==204)process.exitCode=1;}})();
