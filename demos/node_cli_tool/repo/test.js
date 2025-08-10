const { spawnSync } = require('child_process');
const fs = require('fs');

fs.writeFileSync('sample.txt', 'hello world this is a test');
const res = spawnSync('node', ['index.js', 'sample.txt'], { encoding: 'utf-8' });
if (res.status !== 0) {
  console.error('CLI exited with non-zero status');
  process.exit(1);
}
const out = (res.stdout || '').trim();
if (out !== '6') {
  console.error('Expected 6 words, got', out);
  process.exit(1);
}
console.log('ok');
