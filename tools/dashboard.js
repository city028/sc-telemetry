// Live dashboard bridge: node dashboard.js [port]  ->  open http://localhost:8088
// Reads the game's gRPC TelemetryStream (127.0.0.1:2942) and pushes each frame to the browser via Server-Sent Events.
const http = require('http'), http2 = require('http2'), fs = require('fs'), path = require('path');
const toObj = require('./schema.js')(path.join(__dirname, '..', 'proto'));
const PORT = Number(process.argv[2] || 8088), GAME = 'http://127.0.0.1:2942';
const STREAM = '/sc.game.telemetry.v1.GameTelemetryService/TelemetryStream';
const OUT = '.sc.game.telemetry.v1.TelemetryStreamResponse';

const clients = new Set();
let connected = false;
function send(event, data) { const s = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`; for (const c of clients) c.write(s); }
function setConnected(v) { if (v !== connected) { connected = v; send('status', { connected }); console.log(v ? 'game connected' : 'game disconnected, retrying...'); } }

function connect() {
  let done = false;
  const client = http2.connect(GAME);
  const retry = () => { if (done) return; done = true; setConnected(false); client.destroy(); setTimeout(connect, 2000); };
  client.on('error', retry); client.on('close', retry);
  const req = client.request({ ':method': 'POST', ':path': STREAM, 'content-type': 'application/grpc', te: 'trailers' });
  req.on('response', h => { if (h['grpc-status'] === undefined) setConnected(true); });
  let pending = Buffer.alloc(0);
  req.on('data', d => {
    pending = Buffer.concat([pending, d]);
    while (pending.length >= 5) {
      const l = pending.readUInt32BE(1); if (pending.length < 5 + l) break;
      const m = pending.subarray(5, 5 + l); pending = pending.subarray(5 + l);
      send('frame', toObj(m, OUT));
    }
  });
  req.on('error', retry); req.on('end', retry);
  req.end(Buffer.alloc(5)); // empty TelemetryStreamRequest
}

http.createServer((req, res) => {
  if (req.url === '/events') {
    res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache', connection: 'keep-alive' });
    res.write(`event: status\ndata: ${JSON.stringify({ connected })}\n\n`);
    clients.add(res); req.on('close', () => clients.delete(res));
  } else if (req.url === '/') {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
    fs.createReadStream(path.join(__dirname, 'dashboard.html')).pipe(res);
  } else { res.writeHead(404); res.end(); }
}).listen(PORT, '127.0.0.1', () => console.log(`dashboard on http://localhost:${PORT}`));

connect();
