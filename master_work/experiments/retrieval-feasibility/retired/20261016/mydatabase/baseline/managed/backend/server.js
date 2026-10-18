const http = require('http');
const fs = require('fs');
const path = require('path');

const data = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'db', 'data.json'), 'utf8'));
const port = Number(process.env.PORT || 3317);
function send(res, status, body) {
  res.writeHead(status, {'content-type': 'application/json; charset=utf-8'});
  res.end(JSON.stringify(body));
}
function route(req, res) {
  const parts = new URL(req.url, `http://${req.headers.host}`).pathname.split('/').filter(Boolean);
  if (parts[0] !== 'db') return send(res, 404, {error: 'route not found'});
  if (parts.length === 1) return send(res, 200, {databases: data.databases});
  const db = parts[1];
  if (!data.databases.includes(db)) return send(res, 404, {error: `Database "${db}" not found`});
  if (parts[2] === 'pages' && parts[3] === 'slug') {
    const page = data.pages.find(p => p.database === db && p.slug === parts[4]);
    if (!page) return send(res, 404, {error: `Page "${parts[4]}" not found`});
    return send(res, 200, page);
  }
  if (parts[2] === 'pages') return send(res, 200, {pages: data.pages.filter(p => p.database === db)});
  return send(res, 404, {error: 'route not found'});
}
http.createServer(route).listen(port, '127.0.0.1', () => console.log(`mydatabase fixture listening on ${port}`));
