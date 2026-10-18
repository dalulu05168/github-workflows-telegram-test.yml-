import test from 'node:test';
import assert from 'node:assert/strict';
import {prepareDeployment} from '../scripts/prepare-deployment.mjs';
import {REPOSITORY} from '../src/worker.js';
const env={CLOUDFLARE_ACCOUNT_ID:'a'.repeat(32),CLOUDFLARE_API_TOKEN:'secret-test'};
const ok=(result,extra={})=>new Response(JSON.stringify({success:true,result,...extra}));
const namespace={title:'dalulu05168-telegram-finance-news-wakeup-status',id:'b'.repeat(32)};
test('does not overwrite a worker owned by another project',async()=>{
  let calls=0;
  await assert.rejects(prepareDeployment(env,async()=>{calls++;return ok({bindings:[]});}),/ownership marker/);
  assert.equal(calls,1);
});
test('reuses only the named status namespace',async()=>{
  let calls=0;
  const result=await prepareDeployment(env,async()=>++calls===1?ok({bindings:[{name:'DEPLOYMENT_REPOSITORY',text:REPOSITORY}]}):ok([namespace]));
  assert.deepEqual(result,{namespaceId:namespace.id,created:false});assert.equal(calls,2);
});
test('creates namespace only after verifying worker name is unused',async()=>{
  const calls=[];
  const result=await prepareDeployment(env,async(url,opts)=>{
    calls.push([url,opts]);
    if(calls.length===1)return new Response(null,{status:404});
    if(calls.length===2)return ok([]);
    return ok(namespace);
  });
  assert.equal(result.created,true);assert.equal(calls[2][1].method,'POST');
  assert.equal(JSON.parse(calls[2][1].body).title,namespace.title);
});
test('invalid account and authorization failures fail closed',async()=>{
  await assert.rejects(prepareDeployment({},()=>assert.fail('network')),/credential/);
  await assert.rejects(prepareDeployment(env,async()=>new Response('secret-test',{status:403})),/HTTP 403/);
});

test('namespace pagination does not create a duplicate project namespace',async()=>{
  let calls=0;
  const result=await prepareDeployment(env,async()=>{
    calls++;
    if(calls===1)return new Response(null,{status:404});
    if(calls===2)return ok([],{result_info:{total_count:150,per_page:100,page:1}});
    return ok([namespace],{result_info:{total_count:150,per_page:100,page:2}});
  });
  assert.equal(calls,3);assert.deepEqual(result,{namespaceId:namespace.id,created:false});
});
