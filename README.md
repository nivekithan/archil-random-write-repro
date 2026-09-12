# Archil random-write stall reproduction

Small random overwrites on an Archil v0.8.35 FUSE mount can block for approximately one second, even when each write changes only six bytes and the entire file has been read beforehand.

## Requirements

- Linux, Python 3, and GNU coreutils
- Archil CLI v0.8.35 and an Archil disk
- Mount credentials or IAM-role authentication
- Permissions to mount and write to the test file

The standalone Python script has no external dependencies and uses `os.pwrite()` on one open write descriptor.

## Reproduce

Set your connection details (omit the token when using IAM-role authentication):

```bash
export ARCHIL_MOUNT_TOKEN='<disk-token>'
export DISK='<account>/<disk>'
export MOUNT=/mnt/archil
```

The repository includes `test-file.dat`, an exactly **100 MiB**, zero-filled file. Mount a dedicated test disk and copy it onto the mount:

```bash
sudo --preserve-env=ARCHIL_MOUNT_TOKEN archil mount "$DISK" "$MOUNT" \
  --region aws-us-east-1 --statistics --max-cache-mb 954 --target-cache-mb 715

sudo cp --sparse=never test-file.dat "$MOUNT/random-write-repro.dat"
sudo archil unmount "$MOUNT"
```

Fully remount before each run to reset the local client cache:

```bash
sudo --preserve-env=ARCHIL_MOUNT_TOKEN archil mount "$DISK" "$MOUNT" \
  --region aws-us-east-1 --statistics --max-cache-mb 954 --target-cache-mb 715

sudo python3 reproduce.py "$MOUNT/random-write-repro.dat"

# Flush pending data separately from the measured writes.
time sudo archil unmount "$MOUNT"
```

The script reads the entire file, closes the read descriptor, and opens a **write-only (`O_WRONLY`) descriptor** for **10,000 random six-byte `Heloo\n` overwrites**. Python's `random.Random(16001)` generates the offsets during the loop, giving each run the same random offset sequence without a saved offset file. Offsets can repeat. It keeps the write descriptor open, preserves file size, and measures each write with a monotonic clock. There is no explicit workload `fsync()` or payload verification. Archil can still flush automatically, and clean unmount flushes pending data.

To run a smaller batch, remount and pass a write count:

```bash
sudo python3 reproduce.py "$MOUNT/random-write-repro.dat" 1000
```

## Observed behavior

The Python script reproduced the approximately one-second stall in **three consecutive runs**, fully unmounting/remounting and pre-reading the same 100 MiB file before each run:

| Run | Total write time | Longest write | Stalled write |
|---|---:|---:|---:|
| 1 | 1,327.20 ms | 1,007.94 ms | #4,193 |
| 2 | 1,322.30 ms | 1,007.46 ms | #4,193 |
| 3 | 1,338.38 ms | 1,007.58 ms | #4,193 |

Example output:

```text
File: 100 MiB; full pre-read: 370.85 ms
10,000 random 6-byte writes (seed 16001): 1327.20 ms
Logical bytes written: 60000
Longest write: 1007.94 ms
Writes exceeding 100 ms: 1
  Write #4193, offset 48615538: 1007.94 ms
```

The earlier fixed-offset JavaScript version also reproduced the stall at write #4,193. A JavaScript version generating fresh offsets with `crypto.randomInt()` did not reproduce the pause in five checked runs. A single read/write descriptor did not reproduce it in the checked runs either. These observations do not isolate the effects of the offset sequence, access mode, reopening, or timing; write-only mode alone is not sufficient to trigger the stall.

On a fully pre-read 100 MiB file with Archil v0.8.35:

| Workload | Total write time | Longest write | Timeout-retry log entries |
|---|---:|---:|---:|
| 1,000 six-byte random writes | 19.97 ms | 0.241 ms | 0 |
| 10,000 six-byte random writes | 1,335 ms | 1,008 ms | 0 |

These earlier measurements used the same seeded offset sequence. Timing and the exact stall location may vary with the environment and file state; a fixed seed makes the offsets repeatable, not the runtime scheduling.

Additional observed results with the same six-byte payload and full-file pre-read:

- Sustained random writes on a **10 MiB file** for 60 seconds completed with no writes exceeding 100 ms and no timeout-retry logs.
- Sustained random writes on **100 MiB and 192 MiB files** encountered multi-second write stalls and `commit_unconditional` retries with `reason=server_timeout`.
- Six-byte sequential appends for 60 seconds had no writes exceeding 100 ms and no timeout-retry logs.

The one-second pause in the 10,000-write case occurs **without timeout-retry logs**. It should be distinguished from the longer stalls in sustained random-write runs. These observations do not establish a universal file-size or write-count threshold.

Reference environment: Linux, Archil v0.8.35, AWS `c7i.large` (2 vCPUs, 4 GiB RAM), disk and host in `us-east-1`, 954 MiB maximum / 715 MiB target client cache, no FUSE writeback-cache flag. The table reports earlier measurements; the script prints the results for your run.
