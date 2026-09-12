import { closeSync, constants, fstatSync, openSync, readFileSync, readSync, writeSync } from 'node:fs';
import { performance } from 'node:perf_hooks';

const [path, count = '10000'] = process.argv.slice(2);
const writes = Number(count);
if (!path || process.argv.length > 4 || !Number.isSafeInteger(writes) || writes < 1) {
  console.error('Usage: node reproduce.mjs FILE [WRITES=10000]');
  process.exit(1);
}

// Fixed input offsets make the workload identical across runtimes and runs.
const offsets = JSON.parse(readFileSync(new URL('./offsets.json', import.meta.url), 'utf8'));
if (writes > offsets.length) throw new Error(`Maximum write count: ${offsets.length}`);

const payload = Buffer.from('Heloo\n');
let fd = openSync(path, 'r');
try {
  const { size } = fstatSync(fd);
  if (size !== 100 * 1048576) throw new Error('Expected the included 100 MiB test file');
  const buffer = Buffer.alloc(1024 * 1024);
  const readStart = performance.now();
  while (readSync(fd, buffer, 0, buffer.length, null) > 0) {}
  console.log(`File: ${size / 1048576} MiB; full pre-read: ${(performance.now() - readStart).toFixed(2)} ms`);
  closeSync(fd);
  fd = undefined;
  fd = openSync(path, constants.O_WRONLY);

  const slow = [];
  let longest = 0;
  const start = performance.now();
  for (let n = 1; n <= writes; n++) {
    const offset = offsets[n - 1];
    const before = performance.now();
    const written = writeSync(fd, payload, 0, payload.length, offset);
    const elapsed = performance.now() - before;
    if (written !== payload.length) throw new Error(`Short write: ${written}`);
    longest = Math.max(longest, elapsed);
    if (elapsed > 100) slow.push({ write: n, offset, milliseconds: elapsed });
  }
  const total = performance.now() - start;
  console.log(`${writes.toLocaleString('en-US')} random 6-byte writes: ${total.toFixed(2)} ms`);
  console.log(`Logical bytes written: ${writes * payload.length}`);
  console.log(`Longest write: ${longest.toFixed(2)} ms`);
  console.log(`Writes exceeding 100 ms: ${slow.length}`);
  for (const { write, offset, milliseconds } of slow) {
    console.log(`  Write #${write}, offset ${offset}: ${milliseconds.toFixed(2)} ms`);
  }
} finally {
  if (fd !== undefined) closeSync(fd);
}
console.log('No explicit fsync; close and subsequent unmount flushing are outside write timing.');
