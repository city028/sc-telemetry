// Live client: node live.js <protoDir> list|stream [seconds] [host:port]
//              node live.js <protoDir> trigger <action_name> [hold_ms]
const http2 = require('http2');
const [dir, mode, secsArg, argTarget] = process.argv.slice(2);
const target = (mode !== 'trigger' && argTarget) || '127.0.0.1:2942';
const secs = Number(secsArg || 5);

const toObj = require('./schema.js')(dir);

const client = http2.connect('http://' + target);
client.on('error', e => { console.error('connection error:', e.message); process.exit(1); });
const svc = '/sc.game.telemetry.v1.GameTelemetryService/';
const [method, outType] = mode === 'list'
  ? ['ListTriggerableActions', '.sc.game.telemetry.v1.ListTriggerableActionsResponse']
  : mode === 'trigger'
  ? ['TriggerGameAction', '.sc.game.telemetry.v1.TriggerGameActionResponse']
  : ['TelemetryStream', '.sc.game.telemetry.v1.TelemetryStreamResponse'];
const req = client.request({ ':method': 'POST', ':path': svc + method, 'content-type': 'application/grpc', te: 'trailers' });
let pending = Buffer.alloc(0), count = 0;
const t0 = Date.now();
req.on('response', h => { if (h['grpc-status']) console.log('status', h['grpc-status'], h['grpc-message'] || ''); });
req.on('data', d => {
  pending = Buffer.concat([pending, d]);
  while (pending.length >= 5) {
    const l = pending.readUInt32BE(1); if (pending.length < 5 + l) break;
    const m = pending.subarray(5, 5 + l); pending = pending.subarray(5 + l); count++;
    const obj = toObj(m, outType);
    if (mode !== 'stream' || count <= 3 || count % 50 === 0) console.log(`[${((Date.now() - t0) / 1000).toFixed(2)}s #${count} ${l}B]`, JSON.stringify(obj, null, mode === 'list' ? 1 : 0));
  }
});
req.on('trailers', t => console.log('trailers: grpc-status', t['grpc-status'], t['grpc-message'] || ''));
req.on('end', () => { console.log(`end, ${count} messages`); client.close(); });
const varint = n => { const b = []; while (n > 127) { b.push((n & 127) | 128); n >>>= 7; } b.push(n); return Buffer.from(b); };
let body = Buffer.alloc(0); // empty request message for list/stream
if (mode === 'trigger') { // TriggerGameActionRequest: action_name = 1, optional hold_ms = 2
  const name = Buffer.from(secsArg);
  body = Buffer.concat([Buffer.from([0x0a]), varint(name.length), name]);
  if (process.argv[5] !== undefined) body = Buffer.concat([body, Buffer.from([0x10]), varint(Number(process.argv[5]))]);
}
const hdr = Buffer.alloc(5); hdr.writeUInt32BE(body.length, 1);
req.write(Buffer.concat([hdr, body]));
req.end();
if (mode === 'stream') setTimeout(() => { console.log(`stopping after ${secs}s, ${count} messages (${(count / secs).toFixed(1)}/s)`); req.close(http2.constants.NGHTTP2_CANCEL); client.close(); }, secs * 1000);
