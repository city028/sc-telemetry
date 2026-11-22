// Stream a large binary, report printable-string context around each needle hit. Usage: node findstr.js file needle
const fs = require('fs');
const [file, needle] = process.argv.slice(2);
const nb = Buffer.from(needle);
const CTX = 400, seen = new Set();
let carry = Buffer.alloc(0), base = 0;
const stream = fs.createReadStream(file, { highWaterMark: 64 << 20 });
stream.on('data', chunk => {
  const buf = Buffer.concat([carry, chunk]);
  let i = 0;
  while ((i = buf.indexOf(nb, i)) !== -1) {
    const s = Math.max(0, i - CTX), e = Math.min(buf.length, i + nb.length + CTX);
    const off = base + i;
    if (![...seen].some(o => Math.abs(o - off) < CTX)) {
      seen.add(off);
      const txt = buf.subarray(s, e).toString('latin1').replace(/[^\x20-\x7e]+/g, ' | ');
      console.log(`@0x${off.toString(16)}: ${txt}\n`);
    }
    i += nb.length;
  }
  const keep = Math.min(buf.length, CTX + nb.length);
  carry = buf.subarray(buf.length - keep); base += buf.length - keep;
});
stream.on('end', () => console.log(`done, ${seen.size} hits`));
