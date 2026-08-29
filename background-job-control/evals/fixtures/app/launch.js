const { spawn } = require('child_process');
const path = require('path');
console.log('launcher: starting server');
const c = spawn(process.execPath, [path.join(__dirname, 'server.js')], { stdio: 'inherit', env: process.env });
c.on('exit', (code) => process.exit(code));
