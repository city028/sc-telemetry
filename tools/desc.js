// Minimal gRPC server-reflection client (no deps). Usage: node reflect.js host:port outdir
const http2 = require('http2');
const fs = require('fs');
const path = require('path');
const target = process.argv[2] || '127.0.0.1:2942';
const outDir = process.argv[3] || '.';

// ---- protobuf helpers ----
function varint(n) { const b = []; while (n > 127) { b.push((n & 127) | 128); n >>>= 7; } b.push(n); return Buffer.from(b); }
function fieldStr(num, s) { const v = Buffer.from(s); return Buffer.concat([varint((num << 3) | 2), varint(v.length), v]); }
function decode(buf) { // -> array of {num, wt, val}
  const out = []; let i = 0;
  const rv = () => { let r = 0, s = 0, b; do { b = buf[i++]; r += (b & 127) * 2 ** s; s += 7; } while (b & 128); return r; };
  while (i < buf.length) {
    const key = rv(), num = Math.floor(key / 8), wt = key & 7; let val;
    if (wt === 0) val = rv(); else if (wt === 2) { const l = rv(); val = buf.subarray(i, i + l); i += l; }
    else if (wt === 1) { val = buf.subarray(i, i + 8); i += 8; } else if (wt === 5) { val = buf.subarray(i, i + 4); i += 4; }
    else throw new Error('bad wiretype ' + wt);
    out.push({ num, wt, val });
  }
  return out;
}
const get = (f, n) => f.filter(x => x.num === n);
const str = (f, n) => { const x = get(f, n)[0]; return x ? x.val.toString() : undefined; };
const int = (f, n) => { const x = get(f, n)[0]; return x ? x.val : undefined; };

// ---- gRPC call ----
function grpc(client, svcPath, msgs) {
  return new Promise((resolve, reject) => {
    const req = client.request({ ':method': 'POST', ':path': svcPath, 'content-type': 'application/grpc', te: 'trailers' });
    const chunks = []; let status = null, message = '';
    req.on('response', h => { if (h['grpc-status'] !== undefined) { status = h['grpc-status']; message = h['grpc-message'] || ''; } });
    req.on('trailers', t => { status = t['grpc-status']; message = t['grpc-message'] || ''; });
    req.on('data', d => chunks.push(d));
    req.on('error', reject);
    req.on('end', () => {
      const all = Buffer.concat(chunks), res = []; let i = 0;
      while (i + 5 <= all.length) { const l = all.readUInt32BE(i + 1); res.push(all.subarray(i + 5, i + 5 + l)); i += 5 + l; }
      resolve({ status, message, res });
    });
    for (const m of msgs) { const h = Buffer.alloc(5); h.writeUInt32BE(m.length, 1); req.write(Buffer.concat([h, m])); }
    req.end();
  });
}

// ---- descriptor -> .proto text ----
const TYPES = { 1: 'double', 2: 'float', 3: 'int64', 4: 'uint64', 5: 'int32', 6: 'fixed64', 7: 'fixed32', 8: 'bool', 9: 'string', 12: 'bytes', 13: 'uint32', 15: 'sfixed32', 16: 'sfixed64', 17: 'sint32', 18: 'sint64' };
function enumText(e, ind) {
  let s = `${ind}enum ${str(e, 1)} {\n`;
  for (const v of get(e, 2)) { const vf = decode(v.val); s += `${ind}  ${str(vf, 1)} = ${int(vf, 2) ?? 0};\n`; }
  return s + `${ind}}\n`;
}
function msgText(m, ind) {
  let s = `${ind}message ${str(m, 1)} {\n`;
  const oneofs = get(m, 8).map(o => str(decode(o.val), 1));
  for (const nt of get(m, 3)) s += msgText(decode(nt.val), ind + '  ');
  for (const et of get(m, 4)) s += enumText(decode(et.val), ind + '  ');
  for (const fl of get(m, 2)) {
    const f = decode(fl.val), label = int(f, 4), t = int(f, 5);
    const type = (t === 11 || t === 14) ? str(f, 6) : (TYPES[t] || 'type' + t);
    const oi = int(f, 9); const lab = label === 3 ? 'repeated ' : (get(f, 17).length ? 'optional ' : '');
    s += `${ind}  ${lab}${type} ${str(f, 1)} = ${int(f, 3)};${oi !== undefined && !get(f, 17).length ? `  // oneof ${oneofs[oi]}` : ''}\n`;
  }
  return s + `${ind}}\n`;
}
function fileText(fd) {
  let s = `// file: ${str(fd, 1)}\nsyntax = "${str(fd, 12) || 'proto2'}";\npackage ${str(fd, 2)};\n`;
  for (const d of get(fd, 3)) s += `import "${d.val}";\n`;
  s += '\n';
  for (const sv of get(fd, 6)) {
    const svf = decode(sv.val); s += `service ${str(svf, 1)} {\n`;
    for (const me of get(svf, 2)) {
      const mf = decode(me.val);
      s += `  rpc ${str(mf, 1)} (${int(mf, 5) ? 'stream ' : ''}${str(mf, 2)}) returns (${int(mf, 6) ? 'stream ' : ''}${str(mf, 3)});\n`;
    }
    s += '}\n\n';
  }
  for (const et of get(fd, 5)) s += enumText(decode(et.val), '') + '\n';
  for (const mt of get(fd, 4)) s += msgText(decode(mt.val), '') + '\n';
  return s;
}

async function _unused() {
  const client = http2.connect('http://' + target);
  client.on('error', e => { console.error('connection error:', e.message); process.exit(1); });
  let rpath = null, services = [];
  for (const v of ['grpc.reflection.v1.ServerReflection', 'grpc.reflection.v1alpha.ServerReflection']) {
    const p = `/${v}/ServerReflectionInfo`;
    const r = await grpc(client, p, [fieldStr(7, '')]);
    console.log(`${p} -> grpc-status ${r.status} ${r.message}`);
    if (r.res.length) {
      const resp = decode(r.res[0]); const lsr = get(resp, 6)[0];
      if (lsr) { services = get(decode(lsr.val), 1).map(s => str(decode(s.val), 1)); rpath = p; break; }
      const err = get(resp, 7)[0]; if (err) console.log('  error response:', decode(err.val).map(x => x.val.toString()).join(' '));
    }
  }
  if (!rpath) { console.log('Reflection not available.'); client.close(); return; }
  console.log('Services:\n  ' + services.join('\n  '));

  const files = new Map(); const queue = [];
  const addFiles = r => { for (const m of r.res) { const fdr = get(decode(m), 4)[0]; if (!fdr) continue;
    for (const b of get(decode(fdr.val), 1)) { const fd = decode(b.val), n = str(fd, 1);
      if (!files.has(n)) { files.set(n, b.val); for (const d of get(fd, 3)) queue.push(d.val.toString()); } } } };
  for (const s of services) addFiles(await grpc(client, rpath, [fieldStr(4, s)]));
  while (queue.length) { const n = queue.shift(); if (!files.has(n)) addFiles(await grpc(client, rpath, [fieldStr(3, n)])); }
  client.close();

  fs.mkdirSync(outDir, { recursive: true });
  for (const [n, raw] of files) {
    if (n.startsWith('google/protobuf/')) continue;
    const txt = fileText(decode(raw)); const out = path.join(outDir, n.replace(/[\/\\]/g, '__'));
    fs.writeFileSync(out, txt); console.log(`\n===== ${n} -> ${out}\n` + txt);
  }
}
module.exports = { decode, fileText, get, str };
if (require.main === module) {
  const exe = process.argv[2], outDir = process.argv[3];
  const names = process.argv.slice(4);
  const bin = fs.readFileSync(exe);
  fs.mkdirSync(outDir, { recursive: true });
  for (const n of names) {
    const needle = Buffer.concat([Buffer.from([0x0a, n.length]), Buffer.from(n)]);
    const start = bin.indexOf(needle);
    if (start < 0) { console.log('not found', n); continue; }
    // walk top-level fields until syntax (12) is read
    let i = start; const rv = () => { let r = 0, s = 0, b; do { b = bin[i++]; r += (b & 127) * 2 ** s; s += 7; } while (b & 128); return r; };
    for (;;) { const key = rv(), num = Math.floor(key / 8), wt = key & 7; if (wt !== 2) throw new Error('unexpected wt at ' + i); const l = rv(); i += l; if (num === 12) break; }
    const raw = bin.subarray(start, i);
    const base = n.split('/').pop();
    fs.writeFileSync(path.join(outDir, base + '.desc'), raw);
    const txt = fileText(decode(raw));
    fs.writeFileSync(path.join(outDir, base), txt);
    console.log(`===== ${n} (${raw.length} bytes @0x${start.toString(16)})\n${txt}`);
  }
}
