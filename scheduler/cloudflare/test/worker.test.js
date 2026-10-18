import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { publicationWindows, decideWakeup, executeWakeup, REPOSITORY } from '../src/worker.js';

const now = new Date('2026-10-18T05:30:00Z');
const env = { GITHUB_DISPATCH_TOKEN: 'fake-test-secret', DEPLOYMENT_REVISION: 'test', STATUS: {get:async()=>null,put:async()=>{}} };
const json = data => new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } });
const completed = created_at => ({ status: 'completed', created_at });

test('cash market post-open and US pre-open indicator windows wake the runner', () => {
  assert.deepEqual(publicationWindows(new Date('2026-10-19T07:20:00Z')), ['RO','FR']);
  assert.deepEqual(publicationWindows(new Date('2026-10-19T13:20:00Z')), ['US']);
  assert.deepEqual(publicationWindows(new Date('2026-10-26T13:20:00Z')), ['US']);
  assert.deepEqual(publicationWindows(new Date('2026-11-02T14:20:00Z')), ['US']);
  assert.deepEqual(publicationWindows(new Date('2026-10-18T07:20:00Z')), []);
});

test('Romanian and French summer opening windows preserve existing schedule', () => {
  assert.deepEqual(publicationWindows(new Date('2026-10-18T04:29:00Z')), []);
  assert.deepEqual(publicationWindows(new Date('2026-10-18T04:30:00Z')), ['RO']);
  assert.deepEqual(publicationWindows(new Date('2026-10-18T05:00:00Z')), []);
  assert.deepEqual(publicationWindows(now), ['RO', 'FR']);
});
test('winter and different local dates are handled by IANA time zones', () => {
  assert.deepEqual(publicationWindows(new Date('2026-11-02T05:30:00Z')), ['RO']);
  assert.deepEqual(publicationWindows(new Date('2026-10-18T21:30:00Z')), ['FR']);
  assert.deepEqual(publicationWindows(new Date('2026-10-18T22:30:00Z')), []);
});
test('pending run blocks another wakeup', () => {
  assert.equal(decideWakeup(now, [{ status:'in_progress',created_at:'2026-10-18T04:30:00Z' }]), 'RUN_ALREADY_PENDING');
});
test('completed recent checks skip; ten minute boundary can retry', () => {
  assert.equal(decideWakeup(now, [completed('2026-10-18T05:21:00Z')]), 'RECENT_CHECK_EXISTS');
  assert.equal(decideWakeup(now, [completed('2026-10-18T05:20:00Z')]), 'DISPATCH');
});
test('malformed dates and implausible future clock fail closed', () => {
  assert.equal(decideWakeup(now, [completed('invalid')]), 'GITHUB_RESPONSE_INVALID');
  assert.equal(decideWakeup(now, [completed('2026-10-18T06:30:00Z')]), 'CLOCK_SKEW');
});
test('outside windows never contacts GitHub', async () => {
  const result = await executeWakeup(env, { now: new Date('2026-10-18T01:00:00Z'), fetcher: () => assert.fail('network') });
  assert.equal(result.outcome,'OUTSIDE_WINDOW');
});
test('missing secret never contacts GitHub', async () => {
  const result = await executeWakeup({}, {now,fetcher:()=>assert.fail('network')});
  assert.equal(result.outcome,'MISSING_GITHUB_TOKEN');
});
test('reads latest runs then dispatches only the approved main workflow', async () => {
  const calls=[];
  const fetcher=async (url,options)=>{
    calls.push([url,options]);
    return calls.length===1 ? json({workflow_runs:[completed('2026-10-18T05:00:00Z')]}) : new Response(null,{status:204});
  };
  const result=await executeWakeup(env,{now,fetcher});
  assert.equal(result.outcome,'DISPATCH_ACCEPTED');
  assert.equal(result.telegram_delivery_proven,false);
  assert.equal(calls.length,2);
  assert.ok(calls[0][0].includes(`/repos/${REPOSITORY}/actions/workflows/finance-news-live.yml/runs?`));
  assert.ok(calls[0][0].includes('branch=main'));
  assert.equal(calls[1][1].method,'POST');
  assert.deepEqual(JSON.parse(calls[1][1].body),{ref:'main',inputs:{trigger_origin:'cloudflare'}});
  assert.equal(calls[1][1].headers.Authorization,'Bearer fake-test-secret');
  assert.ok(!JSON.stringify(result).includes('fake-test-secret'));
});
test('existing run skips without POST', async () => {
  let calls=0;
  const result=await executeWakeup(env,{now,fetcher:async()=>{calls++;return json({workflow_runs:[{status:'queued',created_at:now.toISOString()}]});}});
  assert.equal(result.outcome,'RUN_ALREADY_PENDING');assert.equal(calls,1);
});
test('authorization failure is explicit and never retried', async () => {
  let calls=0;
  const result=await executeWakeup(env,{now,fetcher:async()=>{calls++;return new Response('secret',{status:403});}});
  assert.equal(result.outcome,'GITHUB_READ_REJECTED');assert.equal(result.http_status,403);assert.equal(calls,1);
  assert.ok(!JSON.stringify(result).includes('secret'));
});
test('invalid API shape is rejected', async () => {
  const result=await executeWakeup(env,{now,fetcher:async()=>json({unexpected:[]})});
  assert.equal(result.outcome,'GITHUB_RESPONSE_INVALID');
});
test('read network failure is sanitized', async () => {
  const result=await executeWakeup(env,{now,fetcher:async()=>{throw new Error('fake-test-secret');}});
  assert.equal(result.outcome,'GITHUB_READ_FAILED');assert.ok(!JSON.stringify(result).includes('fake-test-secret'));
});
test('ambiguous dispatch is not automatically retried', async () => {
  let calls=0;
  const result=await executeWakeup(env,{now,fetcher:async()=>{calls++;if(calls===1)return json({workflow_runs:[]});throw new Error('fake-test-secret');}});
  assert.equal(result.outcome,'DISPATCH_UNCERTAIN');assert.equal(calls,2);
});
test('HTTP rejection is not reported as accepted dispatch', async () => {
  let calls=0;
  const result=await executeWakeup(env,{now,fetcher:async()=>++calls===1?json({workflow_runs:[]}):new Response(null,{status:422})});
  assert.equal(result.outcome,'GITHUB_DISPATCH_REJECTED');assert.equal(result.http_status,422);
});
test('public health is read-only and never exposes the secret', async () => {
  const response=await worker.fetch(new Request('https://example.workers.dev/health'),env);
  assert.equal(response.status,200);
  const text=await response.text();assert.ok(!text.includes('fake-test-secret'));
  assert.equal(JSON.parse(text).configured,true);
});
test('public requests cannot trigger a workflow', async () => {
  const response=await worker.fetch(new Request('https://example.workers.dev/run',{method:'POST'}),env);
  assert.equal(response.status,404);
});

test('scheduled heartbeat persists without exposing credentials', async () => {
  const originalFetch=globalThis.fetch, originalLog=console.log, writes=[],logs=[];
  globalThis.fetch=async()=>json({workflow_runs:[{status:'queued',created_at:now.toISOString()}]});
  console.log=value=>logs.push(value);
  try {
    await worker.scheduled({scheduledTime:now.getTime()},{...env,STATUS:{put:async(...args)=>writes.push(args)}});
    assert.equal(writes.length,1);assert.equal(writes[0][0],'last_scheduled');
    const heartbeat=JSON.parse(writes[0][1]);assert.equal(heartbeat.origin,'cloudflare');
    assert.ok(!JSON.stringify({writes,logs}).includes('fake-test-secret'));
  } finally {globalThis.fetch=originalFetch;console.log=originalLog;}
});
test('health shows persistent last scheduled result and missing setup is not ready', async () => {
  const heartbeat={outcome:'RECENT_CHECK_EXISTS',checked_at:now.toISOString()};
  const response=await worker.fetch(new Request('https://example.workers.dev/health'),{...env,STATUS:{get:async()=>heartbeat}});
  assert.deepEqual((await response.json()).last_scheduled,heartbeat);
  const missing=await worker.fetch(new Request('https://example.workers.dev/health'),{});
  assert.equal(missing.status,503);assert.equal((await missing.json()).configured,false);
});
test('unavailable status storage fails health without leaking raw error', async () => {
  const response=await worker.fetch(new Request('https://example.workers.dev/health'),{...env,STATUS:{get:async()=>{throw new Error('fake-test-secret');}}});
  assert.equal(response.status,503);assert.ok(!(await response.text()).includes('fake-test-secret'));
});

test('whitespace credential is not treated as a configured scheduler',async()=>{
  const blank={...env,GITHUB_DISPATCH_TOKEN:'   '};
  assert.equal((await executeWakeup(blank,{now,fetcher:()=>assert.fail('network')})).outcome,'MISSING_GITHUB_TOKEN');
  const health=await worker.fetch(new Request('https://example.workers.dev/health'),blank);
  assert.equal(health.status,503);
});
