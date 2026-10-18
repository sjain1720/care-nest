// Presentation check only: replay a captured real response; no new model calls.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
const base='http://127.0.0.1:8088',out=path.join(__dirname,'results/j0-review/ui');fs.mkdirSync(out,{recursive:true});
const dir=path.join(__dirname,'results/j0-review/local');
const captures=fs.readdirSync(dir).filter(x=>x.endsWith('.json')).sort((a,b)=>fs.statSync(path.join(dir,b)).mtimeMs-fs.statSync(path.join(dir,a)).mtimeMs).map(x=>JSON.parse(fs.readFileSync(path.join(dir,x))));
const capture=captures.find(x=>x.letter&&x.turns?.length===3&&x.letter.draft.evidenceIndex.some(e=>e.startsWith('Policy wording')));if(!capture)throw Error('No completed review capture');
const report={mode:'UI replay of captured answer and letter; not answer-quality evidence',checks:[]};
const check=(name,value)=>{report.checks.push({name,passed:!!value});if(!value)throw Error(name);};
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});const context=await browser.newContext({viewport:{width:1440,height:1000}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(base,{waitUntil:'networkidle'});await page.locator('#visitor-name').fill('UI reviewer');await page.getByRole('button',{name:'Continue',exact:true}).click();await page.locator('#visitor-name').waitFor({state:'hidden'});
 await context.request.post(base+'/api/demo/ensure?workspace=example',{data:{},timeout:60000});
 await page.route('**/api/case/letter?*',r=>r.fulfill({json:capture.letter.draft}));
 await page.goto(base+'/case/letter?workspace=example&kind=clarification',{waitUntil:'networkidle'});await page.locator('#letter-body').waitFor();
 check('Supporting document reminder precedes editor',await page.evaluate(()=>{const editor=document.querySelector('#letter-body'),summary=[...document.querySelectorAll('summary')].find(e=>e.textContent.includes('Supporting documents'));return !!(summary.compareDocumentPosition(editor)&Node.DOCUMENT_POSITION_FOLLOWING);}));
 check('Policy evidence separated',await page.getByText(/Policy evidence used/).count()===1);
 check('Old papers heading removed',await page.getByRole('heading',{name:'Papers to attach'}).count()===0);
 check('Letter stays editable',await page.locator('#letter-body').isEditable());
 await page.screenshot({path:out+'/letter-desktop.png',fullPage:true});await page.setViewportSize({width:390,height:844});
 check('Phone has no horizontal overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.getByText(/Before sending: fill/).scrollIntoViewIfNeeded();await page.screenshot({path:out+'/letter-phone.png',animations:'disabled'});check('No browser errors',errors.length===0);report.passed=true;
}catch(e){report.error=e.message;report.passed=false;}finally{report.cleanupStatus=(await context.request.delete(base+'/api/session?workspace=general',{timeout:60000})).status();await browser.close();fs.writeFileSync(out+'/report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));if(!report.passed||report.cleanupStatus!==204)process.exitCode=1;}
})();
