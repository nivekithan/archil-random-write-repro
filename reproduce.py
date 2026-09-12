import argparse
import os
import random
import time

parser = argparse.ArgumentParser(description="Reproduce small random-write stalls on Archil")
parser.add_argument("file", help="Path to the included 100 MiB file copied onto Archil")
parser.add_argument("writes", type=int, nargs="?", default=4193)
args = parser.parse_args()
if args.writes < 1:
    parser.error("writes must be positive")

size = os.stat(args.file).st_size
if size != 100 * 1048576:
    parser.error("expected the included 100 MiB test file")

start = time.monotonic()
with open(args.file, "rb", buffering=0) as f:
    while f.read(1048576):
        pass
print(f"File: 100 MiB; full pre-read: {(time.monotonic() - start) * 1000:.2f} ms")

rng = random.Random(16001)
payload = b"Heloo\n"
slow = []
longest = 0
fd = os.open(args.file, os.O_WRONLY)
try:
    start = time.monotonic()
    for n in range(1, args.writes + 1):
        offset = rng.randrange(size - len(payload) + 1)
        before = time.monotonic()
        written = os.pwrite(fd, payload, offset)
        elapsed = time.monotonic() - before
        if written != len(payload):
            raise RuntimeError(f"Short write: {written}")
        longest = max(longest, elapsed)
        if elapsed > 0.1:
            slow.append((n, offset, elapsed))
    total = time.monotonic() - start
finally:
    os.close(fd)

print(f"{args.writes:,} random 6-byte writes (seed 16001): {total * 1000:.2f} ms")
print(f"Logical bytes written: {args.writes * len(payload)}")
print(f"Longest write: {longest * 1000:.2f} ms")
print(f"Writes exceeding 100 ms: {len(slow)}")
for n, offset, elapsed in slow:
    print(f"  Write #{n}, offset {offset}: {elapsed * 1000:.2f} ms")
print("No explicit fsync; close and subsequent unmount flushing are outside write timing.")
