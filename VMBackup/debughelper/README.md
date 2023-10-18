# Diagnostic app for Snapshot Extensions

## What?

This is a very experimental stage program to capture system level logs
and metrics while a snapshot operation is in progress. This kind of data is often
private to each customer and hence we have no plans right now of including this
as part of the normal workflow. This tool will hopefully help us gather critical
data to debug issues that are not solved with the normal logs we collect.

## Build
Please install [Go](https://go.dev/doc/install) and then

```sh
cd <extension_installation_dir>
go build
```

## Run as part of a snapshot operation

- Create or edit "/etc/azure/vmbackup.conf"
- Add a new section `[Monitor]` to the file and 
- under that add the following options
- `Run=yes`
- `Strace=no`
- Of course if you want strace to also run while taking a snapshot enable the option
- That's it. Now every time after a snapshot is taken a new folder will be created at
`<extension installation path>/debughelper/<new folder>`.
- The name of this new folder will be a `ULID` which can be sorted by time
- Inside this directory you'll see several files called `cpu.log`, `mem.log`, `strace.log`
- It is pretty self explanatory what metrics/logs each file contains.

I'll add a more detailed section about how to read the data in each file soon.
For the curious, it's pretty much the data in the `/proc/*` files.

## Running manually
When run manually, right now, it will keep running till it receives an OS Interrupt (Ctrl+c) after
the binary has been executed.

The default behavior (do `./debughelper --help` for all options) will log everything
to a shared memory location (`/dev/shm/Microsoft.Azure.Snapshots.Diagnostics/`)
and after it has been interrupted will move the log subdirectory (see section below)
to the working directory - which by default is the current directory.

```sh
./debughelper
```

You should see a lot of logs like:
```
2023/08/11 16:44:37 [monitor] -> Fired
2023/08/11 16:44:37 [logMem] -> Fired
2023/08/11 16:44:37 [logCPU] -> Fired
2023/08/11 16:44:37 [monitorCPU] -> Fired
2023/08/11 16:44:37 [monitorMem] -> Fired
2023/08/11 16:44:38 [monitorMem] -> sending new metric
2023/08/11 16:44:38 [logMem] -> received new metric
2023/08/11 16:44:38 [monitorCPU] -> sending new metric
2023/08/11 16:44:38 [logCPU] -> new metric received
2023/08/11 16:44:38 [logMem] -> writing to log file
2023/08/11 16:44:38 [logCPU] -> writing to log file
2023/08/11 16:44:39 [monitorCPU] -> sending new metric
2023/08/11 16:44:39 [monitorMem] -> sending new metric
2023/08/11 16:44:39 [logCPU] -> new metric received
2023/08/11 16:44:39 [logMem] -> received new metric
2023/08/11 16:44:39 [logCPU] -> writing to log file
2023/08/11 16:44:39 [logMem] -> writing to log file
2023/08/11 16:44:40 [monitorCPU] -> sending new metric
2023/08/11 16:44:40 [logCPU] -> new metric received
2023/08/11 16:44:40 [logCPU] -> writing to log file
2023/08/11 16:44:40 [monitorMem] -> sending new metric
2023/08/11 16:44:40 [logMem] -> received new metric
2023/08/11 16:44:40 [logMem] -> writing to log file
2023/08/11 16:44:41 [monitorCPU] -> sending new metric
2023/08/11 16:44:41 [monitorMem] -> sending new metric
2023/08/11 16:44:41 [logMem] -> received new metric
2023/08/11 16:44:41 [logMem] -> writing to log file
2023/08/11 16:44:41 [logCPU] -> new metric received
2023/08/11 16:44:41 [logCPU] -> writing to log file
2023/08/11 16:44:42 [monitorMem] -> sending new metric
2023/08/11 16:44:42 [logMem] -> received new metric
2023/08/11 16:44:42 [logMem] -> writing to log file
2023/08/11 16:44:42 [monitorCPU] -> sending new metric
2023/08/11 16:44:42 [logCPU] -> new metric received
2023/08/11 16:44:42 [logCPU] -> writing to log file
2023/08/11 16:44:43 [monitorCPU] -> sending new metric
2023/08/11 16:44:43 [logCPU] -> new metric received
2023/08/11 16:44:43 [logCPU] -> writing to log file
2023/08/11 16:44:43 [monitorMem] -> sending new metric
2023/08/11 16:44:43 [logMem] -> received new metric
2023/08/11 16:44:43 [logMem] -> writing to log file
2023/08/11 16:44:44 [monitorCPU] -> sending new metric
2023/08/11 16:44:44 [logCPU] -> new metric received
2023/08/11 16:44:44 [logCPU] -> writing to log file
2023/08/11 16:44:44 [monitorMem] -> sending new metric
2023/08/11 16:44:44 [logMem] -> received new metric
2023/08/11 16:44:44 [logMem] -> writing to log file
2023/08/11 16:44:45 [monitorCPU] -> sending new metric
2023/08/11 16:44:45 [logCPU] -> new metric received
... and so on
```

Ignore this and in another terminal window:
```sh
# go to the shared memory location. this directory is in memory so fsfreeze will 
# not affect it
cd /dev/shm/Microsoft.Azure.Snapshots.Diagnostics
ls -l
```

You should see a subdirectory here that looks something like `01H7J4WD653PA49Y2X3J1RVYHS`.
This is a ULID (see the ULID section below). `cd` into it and list files.
```sh
cd 01H7J4WD653PA49Y2X3J1RVYHS
ls
```

Now you should see some `.log` files here. `tail` them to see data as its written:
```sh
# tail the cpu file
tail -f cpu.log

# or tail all logs files
tail -f *.log
```


## ULID
Each run will generate a fresh [ULID](https://github.com/ulid/spec).
This ID is unique to this run and all associated logs will be stored in a
subdirectory inside the working directory with the ID as it's name. ULID
has the nice property of encoding the Unix timestamp in the generated ID -
so it will be easy later to make corelations based on time.

```sh
go install github.com/oklog/ulid/v2/cmd/ulid@latest
# Let's assume we have a ULID: 01H7J38F44J44RZ5CYYJHKMVHB
ulid 01H7J38F44J44RZ5CYYJHKMVHB
```

The output should be
```sh
Fri Aug 11 10:46:15.94 UTC 2023
```

### NB:
Running this with strace enabled hasn't been completely tested yet - give it a whirl if you want. Ofcourse please make sure strace is installed.
You will need the PID of a running process.

In one terminal run:
```sh
watch ls -la /tmp
```

In another terminal run
```sh
ps -ef | grep watch | grep -v grep | awk '{print $2}'
```

Let's say the process ID is: `35151`

```sh
./debughelper --strace --tracepid 35151
```

## Plan
There are quite a few more resources to log and monitor like disks and processes
but the broader structure of the code should not need too many changes. Please test
it out and open issues for bugs and feature requests that you think would help
in debugging snapshots.

### Thank You
