import argparse
import os
import random
import time

parser = argparse.ArgumentParser(description="Reproduce multi-second random-write stalls on Archil")
parser.add_argument("file", help="Path to the included 100 MiB file copied onto Archil")
parser.add_argument("--seconds", type=int, default=60, help="Write-loop duration target (default: 60)")
args = parser.parse_args()
if args.seconds < 1:
    parser.error("seconds must be positive")

size = os.stat(args.file).st_size
if size != 100 * 1048576:
    parser.error("expected the included 100 MiB test file")

rng = random.Random(16001)
payload = b"Heloo\n"
slow = []
longest = 0
n = 0
fd = os.open(args.file, os.O_RDWR)
try:
    start = time.monotonic()
    while os.read(fd, 1048576):
        pass
    print(f"File: 100 MiB; full pre-read: {(time.monotonic() - start) * 1000:.2f} ms")
    print(f"Starting {args.seconds}s of random 6-byte writes (seed 16001).", flush=True)

    start = time.monotonic()
    deadline = start + args.seconds
    while time.monotonic() < deadline:
        offset = rng.randrange(size - len(payload) + 1)
        before = time.monotonic()
        written = os.pwrite(fd, payload, offset)
        elapsed = time.monotonic() - before
        if written != len(payload):
            raise RuntimeError(f"Short write: {written}")
        n += 1
        longest = max(longest, elapsed)
        if elapsed > 0.1:
            slow.append((n, offset, elapsed))
    total = time.monotonic() - start
finally:
    os.close(fd)

print(f"{n:,} random 6-byte writes (seed 16001): {total:.2f} s")
print(f"Logical bytes written: {n * len(payload)}")
print(f"Longest write: {longest * 1000:.2f} ms")
print(f"Writes exceeding 100 ms: {len(slow)}")
for n, offset, elapsed in slow:
    print(f"  Write #{n}, offset {offset}: {elapsed * 1000:.2f} ms")
print("No explicit fsync; close and subsequent unmount flushing are outside write timing.")
