// Loads the extracted descriptors and returns toObj(buf, '.full.TypeName') -> plain JS object.
const fs = require('fs'), path = require('path');
const { decode, get, str } = require('./desc.js');

module.exports = function load(dir) {
  const msgs = {}, enums = {};
  function reg(prefix, m) {
    const name = prefix + '.' + str(m, 1);
    const fields = {};
    for (const fl of get(m, 2)) { const f = decode(fl.val); fields[f.find(x => x.num === 3).val] = { name: str(f, 1), label: (get(f, 4)[0] || {}).val, type: (get(f, 5)[0] || {}).val, typeName: str(f, 6) }; }
    msgs[name] = fields;
    for (const nt of get(m, 3)) reg(name, decode(nt.val));
    for (const et of get(m, 4)) regEnum(name, decode(et.val));
  }
  function regEnum(prefix, e) { const vals = {}; for (const v of get(e, 2)) { const vf = decode(v.val); vals[(get(vf, 2)[0] || { val: 0 }).val] = str(vf, 1); } enums[prefix + '.' + str(e, 1)] = vals; }
  for (const f of ['types.proto.desc', 'api.proto.desc']) {
    const fd = decode(fs.readFileSync(path.join(dir, f))), pkg = '.' + str(fd, 2);
    for (const m of get(fd, 4)) reg(pkg, decode(m.val));
    for (const e of get(fd, 5)) regEnum(pkg, decode(e.val));
  }
  return function toObj(buf, typeName) {
    const def = msgs[typeName], o = {};
    for (const { num, wt, val } of decode(buf)) {
      const fd = def[num]; if (!fd) { o['#' + num] = wt === 2 ? val.toString('hex') : val; continue; }
      let vals;
      if (fd.type === 2 && wt === 2) { vals = []; for (let i = 0; i < val.length; i += 4) vals.push(val.readFloatLE(i)); } // packed floats
      else if (fd.type === 2) vals = [val.readFloatLE(0)];
      else if (fd.type === 1) vals = [val.readDoubleLE(0)];
      else if (fd.type === 9) vals = [val.toString()];
      else if (fd.type === 11) vals = [toObj(val, fd.typeName)];
      else if (fd.type === 14) vals = [enums[fd.typeName]?.[val] ?? val];
      else if (fd.type === 8) vals = [!!val];
      else if ((fd.type === 3 || fd.type === 5) && val > 2 ** 63) vals = [val - 2 ** 64]; // negative int64/int32
      else vals = [val];
      if (fd.label === 3) o[fd.name] = (o[fd.name] || []).concat(vals); else o[fd.name] = vals[0];
    }
    return o;
  };
};
