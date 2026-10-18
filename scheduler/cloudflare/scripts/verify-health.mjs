import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {WORKER_NAME} from '../src/worker.js';

const log=await readFile(process.env.DEPLOY_LOG,'utf8');
const found=log.match(/https:\/\/telegram-finance-news-wakeup\.[a-z0-9-]+\.workers\.dev/);
if(!found)throw new Error('Deployment did not provide a workers.dev URL. Enable your Workers subdomain in Cloudflare first.');
const url=found[0];
let health;
for(let attempt=0;attempt<6;attempt++){
  try{
    const response=await fetch(url+'/health',{signal:AbortSignal.timeout(8000)});
    const data=await response.json();
    if(response.ok && data.service===WORKER_NAME && data.configured===true && data.revision===process.env.GITHUB_SHA){health=data;break;}
  }catch{/* DNS and secret activation can take a short time to propagate. */}
  if(attempt<5)await new Promise(resolve=>setTimeout(resolve,5000));
}
if(!health)throw new Error('Worker deployed but health/configuration verification did not complete. Do not disable the PC fallback.');
const status={state:'DEPLOYED_AWAITING_CRON_VERIFICATION',worker_url:url,revision:health.revision,health_configured:true,last_scheduled:health.last_scheduled||null,telegram_delivery_proven:false};
await mkdir('../../reports',{recursive:true});
await writeFile('../../reports/cloudflare-deployment-status.json',JSON.stringify(status,null,2)+'\n');
if(process.env.GITHUB_STEP_SUMMARY){
 const {appendFile}=await import('node:fs/promises');
 await appendFile(process.env.GITHUB_STEP_SUMMARY,`## Cloudflare wakeup deployed\n\nWorker health: ${url}/health\n\nConfiguration and revision verified. Cron activation can take up to 15 minutes. Keep the PC fallback until a natural cron heartbeat and a cloudflare-origin GitHub run have been verified. This deployment does not prove Telegram delivery.\n`);
}
console.log(JSON.stringify(status));
