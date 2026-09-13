# Archil long random-write stall reproduction

Sustained six-byte random overwrites on an Archil v0.8.35 FUSE mount can block individual writes for **approximately 30 seconds**, even after the entire 100 MiB file has been read.

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

```bash
sudo --preserve-env=ARCHIL_MOUNT_TOKEN archil mount "$DISK" "$MOUNT" \
  --region aws-us-east-1 --statistics --max-cache-mb 954 --target-cache-mb 715

sudo python3 reproduce-long-stalls.py "$MOUNT/random-write-repro.dat"

# Flush pending data separately from the measured write loop.
sudo archil unmount "$MOUNT"
```

The script opens **one read/write (`O_RDWR`) descriptor**, reads the entire file with `os.read()`, and uses that same descriptor for **60 seconds of random six-byte `Heloo\n` overwrites** with `os.pwrite()`. It generates offsets using `random.Random(16001)` and keeps the file size unchanged. It does not explicitly call `fsync()` or verify payloads; Archil can still flush automatically.

The duration is a target: a write started before the deadline can block past it. Per-write timings cover `os.pwrite()` only; pre-read, close, and unmount are outside write-loop timing. Fully unmount and remount before each run. To change the duration, pass `--seconds 120`.

## Observed behavior

The script completed 176,147 writes in **69.75 seconds** despite its 60-second target, using a newly created zero-filled 100 MiB file:

```text
File: 100 MiB; full pre-read: 355.07 ms
Starting 60s of random 6-byte writes (seed 16001).
176,147 random 6-byte writes (seed 16001): 69.75 s
Logical bytes written: 1056882
Longest write: 30146.08 ms
Writes exceeding 100 ms: 3
  Write #72646, offset 39434368: 10131.75 ms
  Write #107866, offset 13163171: 25139.58 ms
  Write #176147, offset 88156081: 30146.08 ms
```

The 10-, 25-, and 30-second stalls coincided with `commit_unconditional` retries reporting `reason=server_timeout`. The associated `cache_full` syncs pushed approximately 3 MiB each. The seed repeats the offset sequence, but exact stall positions and durations may vary.

Reference environment: Linux 6.18.44, Archil v0.8.35 (build `e8be7043`), AWS `c7i.large` (2 vCPUs, 4 GiB RAM), disk and host in `us-east-1`, 954 MiB maximum / 715 MiB target client cache, no FUSE writeback-cache flag.
