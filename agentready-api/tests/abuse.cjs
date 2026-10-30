const {test}=require('node:test');
const assert=require('node:assert/strict');
const express=require('express');
const {scanRateLimit,unlockRateLimit,recipientRateLimit}=require('../dist/middleware/scanRateLimit');
const {normalizeUrl}=require('../dist/utils/url');
test('numeric subdomain is valid while private literals are blocked',()=>{
 assert.equal(normalizeUrl('https://10.example.com').domain,'10.example.com');
 assert.throws(()=>normalizeUrl('http://10.0.0.1'));
});
test('forged forwarding cannot reset scan or email allowances',async()=>{
 const app=express();app.set('trust proxy',false);app.use(express.json());
 app.post('/scan',scanRateLimit,(_req,res)=>res.json({ok:true}));
 app.post('/unlock',unlockRateLimit,recipientRateLimit,(_req,res)=>res.json({ok:true}));
 const server=app.listen(0,'127.0.0.1');
 await new Promise(resolve=>server.once('listening',resolve));
 try {
 const base='http://127.0.0.1:'+server.address().port;
 let blocked=0;
 for(let i=0;i<30;i++){
 const res=await fetch(base+'/scan',{method:'POST',headers:{'x-forwarded-for':'8.8.8.'+i}});
 if(res.status===429)blocked++;
 }
 assert.ok(blocked>0);
 const statuses=[];
 for(let i=0;i<7;i++) statuses.push((await fetch(base+'/unlock',{method:'POST',headers:{'content-type':'application/json','x-forwarded-for':'1.1.1.'+i},body:JSON.stringify({email:'recipient@example.invalid'})})).status);
 assert.deepEqual(statuses.slice(0,3),[200,200,200]); assert.ok(statuses.slice(3).every(s=>s===429));
 } finally {await new Promise(resolve=>server.close(resolve));}
});

test('CORS accepts configured origins and rejects unrelated Vercel tenants',async()=>{
 const {createApp}=require('../dist/app');
 const server=createApp().listen(0,'127.0.0.1');
 await new Promise(resolve=>server.once('listening',resolve));
 try {
 const base='http://127.0.0.1:'+server.address().port;
 const evil=await fetch(base+'/',{headers:{origin:'https://attacker.vercel.app'}});
 assert.equal(evil.headers.get('access-control-allow-origin'),null);
 const allowed=await fetch(base+'/',{headers:{origin:'http://localhost:5173'}});
 assert.equal(allowed.headers.get('access-control-allow-origin'),'http://localhost:5173');
 } finally {await new Promise(resolve=>server.close(resolve));}
});
