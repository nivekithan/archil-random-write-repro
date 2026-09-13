# Archil random-write stall reproduction

> For the reproduction with approximately 30-second stalls, see **[Long write stalls](LONG-WRITE-STALLS.md)**.

Small random overwrites on an Archil v0.8.35 FUSE mount can block for approximately one second.

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

sudo python3 reproduce.py "$MOUNT/random-write-repro.dat"
```

The script opens **one read/write (`O_RDWR`) descriptor**, reads the entire file with `os.read()`, and uses that same descriptor for **4,193 random six-byte `Heloo\n` overwrites** with `os.pwrite()`, stopping immediately after the write that stalled in the observed runs.

## Observed behavior

Example output from the run:

```text
4,193 random 6-byte writes (seed 16001): 1160.45 ms
Logical bytes written: 25158
Longest write: 1007.86 ms
Writes exceeding 100 ms: 1
  Write #4193, offset 48615538: 1007.86 ms
```


Reference environment: Linux, Archil v0.8.35, AWS `c7i.large` (2 vCPUs, 4 GiB RAM), disk and host in `us-east-1`, 954 MiB maximum / 715 MiB target client cache.
