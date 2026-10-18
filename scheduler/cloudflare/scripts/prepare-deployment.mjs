import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { REPOSITORY, WORKER_NAME } from '../src/worker.js';
const namespaceTitle = 'dalulu05168-telegram-finance-news-wakeup-status';

export async function prepareDeployment(env,fetcher=fetch) {
  const account=env.CLOUDFLARE_ACCOUNT_ID?.trim();
  if (!account || !/^[a-f0-9]{32}$/i.test(account) || !env.CLOUDFLARE_API_TOKEN?.trim()) throw new Error('Cloudflare account ID or API credential missing/invalid');
  const base=`https://api.cloudflare.com/client/v4/accounts/${account}`;
  const headers={Authorization:`Bearer ${env.CLOUDFLARE_API_TOKEN.trim()}`,'Content-Type':'application/json'};
  const call=async(path,options={})=>{
    let response;
    try {response=await fetcher(base+path,{...options,headers,signal:AbortSignal.timeout(15000)});}
    catch {throw new Error('Cloudflare API network failure; no credential details logged');}
    return response;
  };
  const decoded=async response=>{
    if(!response.ok)throw new Error(`Cloudflare API rejected configuration (HTTP ${response.status})`);
    let body;try{body=await response.json();}catch{throw new Error('Invalid Cloudflare API response');}
    if(body.success!==true)throw new Error('Cloudflare API did not confirm configuration');
    return body;
  };
  const worker=await call(`/workers/scripts/${WORKER_NAME}/settings`);
  if(worker.status!==404){
    const body=await decoded(worker);
    const marker=body.result?.bindings?.find(x=>x.name==='DEPLOYMENT_REPOSITORY');
    if(marker?.text!==REPOSITORY)throw new Error('Worker name already exists without this repository ownership marker. No deployment performed.');
  }
  let namespaceId;
  for(let page=1;page<=20;page++){
    const body=await decoded(await call(`/storage/kv/namespaces?per_page=100&page=${page}`));
    if(!Array.isArray(body.result))throw new Error('Invalid Cloudflare namespace response');
    namespaceId=body.result.find(x=>x.title===namespaceTitle)?.id;
    const pages=body.result_info?.total_pages || Math.ceil((body.result_info?.total_count||body.result.length)/(body.result_info?.per_page||100)) || 1;
    if(namespaceId || page>=pages)break;
    if(page===20)throw new Error('Too many namespaces to safely inspect automatically');
  }
  let created=false;
  if(!namespaceId){
    const body=await decoded(await call('/storage/kv/namespaces',{method:'POST',body:JSON.stringify({title:namespaceTitle})}));
    namespaceId=body.result?.id;created=true;
  }
  if(!/^[a-f0-9]{32}$/i.test(namespaceId||''))throw new Error('Cloudflare did not return a valid status namespace');
  return {namespaceId,created};
}

if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href){
  const {namespaceId}=await prepareDeployment(process.env);
  let config=await readFile(new URL('../wrangler.toml',import.meta.url),'utf8');
  const revision=process.env.GITHUB_SHA || 'local';
  if(!/^[a-zA-Z0-9-]{1,64}$/.test(revision))throw new Error('Invalid deployment revision');
  config=config.replace(`DEPLOYMENT_REPOSITORY = "${REPOSITORY}"`, `DEPLOYMENT_REPOSITORY = "${REPOSITORY}"\nDEPLOYMENT_REVISION = "${revision}"`);
  await writeFile(new URL('../wrangler.deploy.toml',import.meta.url),config+`\n[[kv_namespaces]]\nbinding = "STATUS"\nid = "${namespaceId}"\n`);
  console.log('Cloudflare ownership checked and persistent scheduler status configured.');
}
