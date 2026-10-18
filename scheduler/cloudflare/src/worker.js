// Cloud wakeup only: news, Telegram credentials and delivery receipts stay in GitHub.
export const REPOSITORY = 'dalulu05168/github-workflows-telegram-test.yml-';
export const WORKFLOW = 'finance-news-live.yml';
export const WORKER_NAME = 'telegram-finance-news-wakeup';
const CRON = '*/10 * * * *';
const formatters = Object.entries({ RO:'Europe/Bucharest', FR:'Europe/Paris', US:'America/New_York' }).map(([region,timeZone]) => [region,new Intl.DateTimeFormat('en-GB',{timeZone,weekday:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'})]);
const pending = new Set(['queued','in_progress','waiting','pending','requested']);

export function publicationWindows(now) {
  return formatters.filter(([region,formatter]) => {
    const parts = formatter.formatToParts(now);
    const hour = Number(parts.find(x => x.type==='hour').value);
    const minute = Number(parts.find(x => x.type==='minute').value);
    const weekday = parts.find(x => x.type==='weekday').value;
    const clock = hour*60+minute;
    const targets = {RO:[585,615],FR:[525,555],US:[555,585]}[region];
    const indicator = !['Sat','Sun'].includes(weekday) && targets.some(t => clock>=t && clock<t+15);
    // Holiday decisions stay in the Python exchange calendar, not this wakeup.
    return (region!=='US' && hour>=7 && minute>=30) || indicator;
  }).map(([region]) => region);
}

export function decideWakeup(now,runs) {
  if (!Array.isArray(runs)) return 'GITHUB_RESPONSE_INVALID';
  for (const run of runs) {
    if (!run || typeof run.status!=='string') return 'GITHUB_RESPONSE_INVALID';
    if (pending.has(run.status)) return 'RUN_ALREADY_PENDING';
    const created = Date.parse(run.created_at);
    if (!Number.isFinite(created)) return 'GITHUB_RESPONSE_INVALID';
    const age = (now.getTime()-created)/60000;
    if (age < -2) return 'CLOCK_SKEW';
    if (age < 10) return 'RECENT_CHECK_EXISTS';
  }
  return 'DISPATCH';
}

export async function executeWakeup(env,{now=new Date(),fetcher=fetch}={}) {
  const result = {checked_at:now.toISOString(),active_markets:publicationWindows(now),origin:'cloudflare',revision:env.DEPLOYMENT_REVISION||'not-specified',telegram_delivery_proven:false};
  if (!result.active_markets.length) return {...result,outcome:'OUTSIDE_WINDOW'};
  const token=typeof env.GITHUB_DISPATCH_TOKEN==='string' ? env.GITHUB_DISPATCH_TOKEN.trim() : '';
  if (!token) return {...result,outcome:'MISSING_GITHUB_TOKEN'};
  const base = `https://api.github.com/repos/${REPOSITORY}/actions/workflows/${WORKFLOW}`;
  const headers = {Authorization:`Bearer ${token}`,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'TelegramFinanceCloudWakeup/1.0'};
  let response;
  try {
    response = await fetcher(`${base}/runs?branch=main&per_page=5`,{method:'GET',headers,signal:AbortSignal.timeout(8000)});
  } catch {
    return {...result,outcome:'GITHUB_READ_FAILED'};
  }
  if (!response.ok) return {...result,outcome:'GITHUB_READ_REJECTED',http_status:response.status};
  let data;
  try { data=await response.json(); } catch { return {...result,outcome:'GITHUB_RESPONSE_INVALID'}; }
  const decision = decideWakeup(now,data?.workflow_runs);
  if (decision!=='DISPATCH') return {...result,outcome:decision};
  try {
    response=await fetcher(`${base}/dispatches`,{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({ref:'main',inputs:{trigger_origin:'cloudflare'}}),signal:AbortSignal.timeout(8000)});
  } catch {
    // A timeout may occur after GitHub accepts the request. Do not retry the POST.
    return {...result,outcome:'DISPATCH_UNCERTAIN'};
  }
  if (response.status!==204) return {...result,outcome:'GITHUB_DISPATCH_REJECTED',http_status:response.status};
  return {...result,outcome:'DISPATCH_ACCEPTED'};
}

export default {
  async scheduled(controller,env) {
    const result=await executeWakeup(env);
    const heartbeat={...result,scheduled_at:new Date(controller.scheduledTime).toISOString()};
    if(env.STATUS){
      try {await env.STATUS.put('last_scheduled',JSON.stringify(heartbeat),{expirationTtl:604800});}
      catch {heartbeat.status_storage='WRITE_FAILED';}
    }
    console.log(JSON.stringify(heartbeat));
  },
  async fetch(request,env) {
    if (request.method!=='GET' || !['/','/health'].includes(new URL(request.url).pathname)) return new Response('Not found',{status:404});
    let lastScheduled=null;
    try {lastScheduled=env.STATUS ? await env.STATUS.get('last_scheduled',{type:'json'}) : null;}
    catch {return Response.json({service:WORKER_NAME,error:'STATUS_STORAGE_UNAVAILABLE'},{status:503,headers:{'Cache-Control':'no-store'}});}
    const configured=Boolean(env.GITHUB_DISPATCH_TOKEN?.trim() && env.STATUS);
    return Response.json({service:WORKER_NAME,configured,cron:CRON,timezones:['Europe/Bucharest','Europe/Paris','America/New_York'],revision:env.DEPLOYMENT_REVISION||'not-specified',last_scheduled:lastScheduled,note:'Accepted dispatch is not a Telegram delivery receipt.'},{status:configured?200:503,headers:{'Cache-Control':'no-store'}});
  },
};
