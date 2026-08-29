const http = require('http');
const PORT = process.env.PORT || 5123;
const srv = http.createServer((req, res) => {
  if (req.url === '/health') { res.writeHead(200, {'Content-Type': 'text/plain'}); res.end('app-ok\n'); return; }
  if (req.url === '/events') {
    res.writeHead(200, {'Content-Type': 'text/event-stream'});
    const t = setInterval(() => res.write('data: tick\n\n'), 1000);
    req.on('close', () => clearInterval(t));
    return;
  }
  res.writeHead(200); res.end('hello from app\n');
});
srv.listen(PORT, () => console.log('listening on ' + PORT));
setInterval(() => console.log('heartbeat ' + new Date().toISOString()), 2000);
