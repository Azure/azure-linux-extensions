package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path"
	"strconv"
	"strings"
	"sync"
	"time"
)

const LF_RUN = "run.log"
const LF_STRACE = "strace.log"
const LF_CPU = "cpu.log"
const LF_MEM = "mem.log"
const LF_DISK = "disk.log"
const LF_DIAG = "diagnosis.log"

type Run struct {
	wd       string
	opID     string
	log      *log.Logger
	strace   bool
	tracePID int64
	logToMem bool
	inMemDir string
}

func NewRun(workingDir, opID string, with_strace bool, trace_pid int64, logToMem bool) (*Run, *os.File, error) {
	r := &Run{
		wd:       workingDir,
		opID:     opID,
		strace:   with_strace,
		tracePID: trace_pid,
		inMemDir: "/dev/shm/Microsoft.Azure.Snapshots.Diagnostics",
		logToMem: logToMem,
	}
	if r.logToMem {
		if err := os.MkdirAll(path.Join(r.inMemDir, r.opID), 0755); err != nil {
			return nil, nil, wrapErr(err, "os.MkdirAll failed")
		}
	}
	f, err := os.OpenFile(path.Join(r.workDir(), LF_RUN), os.O_CREATE, 0644)
	if err != nil {
		return nil, nil, wrapErr(err, "os.OpenFile failed")
	}
	r.log = log.New(f, "", log.Ldate|log.Ltime|log.LUTC)
	return r, f, nil
}

func (r Run) workDir() string {
	p := path.Join(r.wd, r.opID)
	if r.logToMem {
		p = path.Join(r.inMemDir, r.opID)
	}
	return p
}

func (r Run) startStrace(ctx context.Context) error {
	if !r.strace {
		return nil
	}
	if r.tracePID == 0 {
		return fmt.Errorf("empty process ID")
	}
	command := exec.CommandContext(
		ctx, "strace", "-t", "-p", fmt.Sprintf("%d", r.tracePID),
		"-f", "-o", path.Join(r.workDir(), LF_STRACE),
	)
	_, err := command.CombinedOutput()
	if err != nil {
		r.log.Println(wrapErr(err, "CombinedOutput failed"))
	}
	return nil
}

func (r Run) diagnose() string {
	avreport := diagnoseAvs()
	dbreport := diagnoseDbs()
	logFile := path.Join(r.workDir(), LF_DIAG)
	f, err := os.OpenFile(logFile, os.O_CREATE, 0644)
	if err != nil {
		r.log.Println(wrapErr(err, "os.OpenFile failed"))
	}
	defer f.Close()

	l := ""
	if len(avreport) > 0 {
		l = l + "========== ANTIVIRUS ============\n\n"
		l = l + strings.Join(avreport, "\n\n")
	}
	f.WriteString(l)
	if len(l) > 0 {
		l = "\n\n\n"
	}
	if len(dbreport) > 0 {
		l = l + "========== DATABSES ============\n\n"
		l = l + strings.Join(dbreport, "\n\n")
	}

	f.WriteString(l)
	f.WriteString("\n")
	r.persistInMemDir()
	return path.Join(r.wd, r.opID, LF_DIAG)
}

type LoadAvg struct {
	TS         int64  `json:"timestamp_millis"`
	One        string `json:"one"`
	Five       string `json:"five"`
	Fifteen    string `json:"fifteen"`
	SchedRatio string `json:"scheduled_ratio"`
	LP         string `json:"last_pid"`
}

func (r Run) monitorCPU(ctx context.Context, cpuStream chan *LoadAvg) {
	// log.Println("[monitorCPU] -> Fired")
	ticker := time.NewTicker(time.Second)
	ctx1, cancel := context.WithCancel(ctx)
outer:
	for {
		select {
		case <-ctx.Done():
			cancel()
			ticker.Stop()
			cpuStream <- nil
			break outer
		case <-ticker.C:
			go func() {
				command := exec.CommandContext(ctx1, "cat", "/proc/loadavg")
				bs, err := command.CombinedOutput()
				if err != nil {
					r.log.Println(wrapErr(err, "CombinedOutput failed"))
				} else {
					fields := strings.Fields(strings.Trim(string(bs), " \n"))
					if len(fields) != 5 {
						r.log.Println(wrapErr(fmt.Errorf("/proc/loadavg returned invalid number of strings")))
					} else {
						la := LoadAvg{
							One:        fields[0],
							Five:       fields[1],
							Fifteen:    fields[2],
							SchedRatio: fields[3],
							LP:         fields[4],
							TS:         time.Now().UnixMilli(),
						}
						log.Println("[monitorCPU] -> sending new metric")
						cpuStream <- &la
					}
				}
			}()

		}
	}
}

func (r Run) logCPU(ctx context.Context, cpuStream chan *LoadAvg) error {
	f, err := os.Create(path.Join(r.workDir(), LF_CPU))
	if err != nil {
		return wrapErr(err, "os.Create failed")
	}
	// logger := log.New(f, "", log.Ldate|log.Ltime|log.LUTC)
	defer f.Close()
outer:
	for {
		select {
		case <-ctx.Done():
			break outer
		case lav := <-cpuStream:
			// log.Println("[logCPU] -> new metric received")
			bs, err := json.Marshal(lav)
			if err != nil {
				r.log.Println(wrapErr(err, "json.Marshal failed"))
			} else {
				// log.Println("[logCPU] -> writing to log file")
				f.WriteString(fmt.Sprintf("%s\n", string(bs)))
			}
		}
	}
	return nil
}

type Mem struct {
	TS           int64 `json:"timestamp_millis"`
	TotalKb      int64 `json:"total_kb"`
	AvailKb      int64 `json:"avail_kb"`
	FreeKb       int64 `json:"free_kb"`
	CachedKb     int64 `json:"cached_kb"`
	SwapCachedKb int64 `json:"swap_cached_kb"`
	SwapTotalKb  int64 `json:"swap_total_kb"`
	SwapFreeKb   int64 `json:"swap_free_kb"`
}

func (r Run) monitorMem(ctx context.Context, memStream chan *Mem) {
	ticker := time.NewTicker(time.Second)
	ctx1, cancel := context.WithCancel(context.TODO())
outer:
	for {
		select {
		case <-ctx.Done():
			cancel()
			ticker.Stop()
			memStream <- nil
			break outer
		case <-ticker.C:
			command := exec.CommandContext(ctx1, "cat", "/proc/meminfo")
			bs, err := command.CombinedOutput()
			if err != nil {
				log.Println(wrapErr(err, "CombinedOutput failed"))
			} else {
				m := Mem{
					TS: time.Now().UnixMilli(),
				}
				flag := false
				for _, line := range strings.Split(string(bs), "\n") {
					if len(line) == 0 {
						continue
					}
					fields := strings.Fields(line)
					if len(fields) != 3 {
						continue
					}
					switch fields[0] {
					case "MemTotal:":
						v, err := strconv.Atoi(fields[1])
						if err != nil {
							log.Println("MemTotal conversion to int failed: ", err)
						} else {
							m.TotalKb = int64(v)
							flag = true
						}
					case "MemAvailable:":
						v, err := strconv.Atoi(fields[1])
						if err != nil {
							log.Println("MemAvailable conversion to int failed: ", err)
						} else {
							m.AvailKb = int64(v)
							flag = true
						}
					case "MemFree:":
						v, err := strconv.Atoi(fields[1])
						if err != nil {
							log.Println("MemFree conversion to int failed: ", err)
						} else {
							m.FreeKb = int64(v)
							flag = true
						}
					case "Cached:":
						v, err := strconv.Atoi(fields[1])
						if err != nil {
							log.Println("Cached Mem conversion to int failed: ", err)
						} else {
							m.CachedKb = int64(v)
							flag = true
						}
					case "SwapCached:":
						v, err := strconv.Atoi(fields[1])
						if err != nil {
							log.Println("SwapCached conversion to int failed: ", err)
						} else {
							m.SwapCachedKb = int64(v)
							flag = true
						}
					case "SwapTotal:":
						v, err := strconv.Atoi(fields[1])
						if err != nil {
							log.Println("SwapTotal conversion to int failed: ", err)
						} else {
							m.SwapTotalKb = int64(v)
							flag = true
						}
					case "SwapFree:":
						v, err := strconv.Atoi(fields[1])
						if err != nil {
							log.Println("SwapFree conversion to int failed: ", err)
						} else {
							m.SwapFreeKb = int64(v)
							flag = true
						}
					}
				}
				if flag {
					// log.Println("[monitorMem] -> sending new metric")
					memStream <- &m
				}
			}
		}
	}
}

func (r Run) logMem(ctx context.Context, memStream chan *Mem) error {
	// log.Println("[logMem] -> Fired")
	f, err := os.Create(path.Join(r.workDir(), LF_MEM))
	if err != nil {
		return wrapErr(err, "OpenFile failed")
	}
	defer f.Close()
outer:
	for {
		select {
		case <-ctx.Done():
			break outer
		case lav := <-memStream:
			if lav == nil {
				break outer
			}
			log.Println("[logMem] -> received new metric")
			bs, err := json.Marshal(lav)
			if err != nil {
				r.log.Println(wrapErr(err, "json.Marshal failed"))
			} else {
				log.Println("[logMem] -> writing to log file")
				f.WriteString(fmt.Sprintf("%s\n", string(bs)))
			}
		}
	}
	return nil
}

type DiskLog struct {
	TS                          int64  `json:"timestamp_millis"`
	MajorNum                    string `json:"major_num"`
	MinorNum                    string `json:"minor_num"`
	DeviceName                  string `json:"device_name"`
	ReadsCompleted              string `json:"reads_completed_successfully"`
	ReadsMerged                 string `json:"reads_merged"`
	SectorsRead                 string `json:"sectors_read"`
	TimeSpentReadingMs          string `json:"time_spent_reading_ms"`
	WritesCompleted             string `json:"writes_completed"`
	WriteMerged                 string `json:"writes_merged"`
	SectorsWritten              string `json:"sectors_written"`
	TimeSpentWritingMs          string `json:"time_spent_writing"`
	IosInProgress               string `json:"ios_currently_in_progress"`
	TimeSpentIosMs              string `json:"time_spent_doing_ios_ms"`
	WeightedTimeSpentDoingIosMs string `json:"weighted_time_spent_doing_ios_ms"`
	DiscardsCompleted           string `json:"discards_completed_successfully"`
	DiscardsMerged              string `json:"discards_merged"`
	SectorsDiscarded            string `json:"sectors_discarded"`
	TimeSpentDiscardingMs       string `json:"time_sspent_discarding"`
	FlushRequestsCompleted      string `json:"flush_requests_completed_successfully"`
	TimeSpentFlushingMs         string `json:"time_spent_flushing"`
}

func (r Run) monitorDisk(ctx context.Context, diskChan chan *DiskLog) {
	ticker := time.NewTicker(time.Second)
	ctx1, cancel := context.WithCancel(context.TODO())
outer:
	for {
		select {
		case <-ctx.Done():
			cancel()
			ticker.Stop()
			diskChan <- nil
			break outer
		case <-ticker.C:
			command := exec.CommandContext(ctx1, "cat", "/proc/diskstats")
			bs, err := command.CombinedOutput()
			if err != nil {
				log.Println(wrapErr(err, "CombinedOutput failed"))
				continue outer
			}
			for _, line := range strings.Split(string(bs), "\n") {
				fields := strings.Fields(line)
				// Get only sata or nvme disks
				if len(fields) == 0 {
					continue
				}
				if !strings.Contains(fields[2], "sd") && !strings.Contains(fields[2], "nvme") {
					continue
				}

				dl := DiskLog{
					TS:                          time.Now().UnixMilli(),
					MajorNum:                    fields[0],
					MinorNum:                    fields[1],
					DeviceName:                  fields[2],
					ReadsCompleted:              fields[3],
					ReadsMerged:                 fields[4],
					SectorsRead:                 fields[5],
					TimeSpentReadingMs:          fields[6],
					WritesCompleted:             fields[7],
					WriteMerged:                 fields[8],
					SectorsWritten:              fields[9],
					TimeSpentWritingMs:          fields[10],
					IosInProgress:               fields[11],
					TimeSpentIosMs:              fields[12],
					WeightedTimeSpentDoingIosMs: fields[13],
				}

				lf := len(fields)
				// Kernel 4.18+ will have the following fields
				if lf >= 18 {
					dl.DiscardsCompleted = fields[14]
					dl.DiscardsMerged = fields[15]
					dl.SectorsDiscarded = fields[16]
					dl.TimeSpentDiscardingMs = fields[17]
				}

				// Kernel 5.5+ further have the following fields
				if lf >= 20 {
					dl.FlushRequestsCompleted = fields[18]
					dl.TimeSpentFlushingMs = fields[19]
				}

				diskChan <- &dl
			}
		}
	}
}

func (r Run) logDisk(ctx context.Context, diskChan chan *DiskLog) error {
	f, err := os.Create(path.Join(r.workDir(), LF_DISK))
	if err != nil {
		return wrapErr(err, "os.Create failed")
	}
	defer f.Close()
outer:
	for {
		select {
		case <-ctx.Done():
			break outer
		case lav := <-diskChan:
			if lav == nil {
				break outer
			}
			log.Println("[logDisk] -> received new metric")
			bs, err := json.Marshal(lav)
			if err != nil {
				r.log.Println(wrapErr(err, "json.Marshal failed"))
			} else {
				log.Println("[logDisk] -> writing to log file")
				f.WriteString(fmt.Sprintf("%s\n", string(bs)))
			}
		}
	}
	return nil
}

func (r Run) persistInMemDir() {
	// log.Println("[persistInMemDir] -> Fired")
	if !r.logToMem {
		return
	}
	log.Printf("moving: \"%s\" to \"%s\"\n", r.workDir(), r.wd)
	cmd := exec.Command("mv", r.workDir(), fmt.Sprintf("%s/", r.wd))
	if _, err := cmd.CombinedOutput(); err != nil {
		r.log.Println(wrapErr(err, fmt.Sprintf("moving from shared memory to path: \"%s\" failed", r.wd)))
	}
}

func (r Run) monitor(ctx context.Context) {
	// log.Println("[monitor] -> Fired")
	wg := sync.WaitGroup{}

	// save pid file
	pf, err := os.Create(path.Join(r.workDir(), "monitor.pid"))
	if err != nil {
		r.log.Println("error creating pid file")
		return
	}

	pf.WriteString(fmt.Sprintf("%d", os.Getpid()))

	// strace
	tctx, tcancel := context.WithCancel(ctx)
	wg.Add(1)
	go func() {
		defer wg.Done()
		r.startStrace(tctx)
	}()

	// CPU ==============================
	cpuStream := make(chan *LoadAvg, 1)
	cpuCtx, cpuCancel := context.WithCancel(ctx)
	logCpuCtx, logCpuCancel := context.WithCancel(ctx)
	wg.Add(1)
	go func() {
		defer wg.Done()
		r.monitorCPU(cpuCtx, cpuStream)
	}()
	wg.Add(1)
	go func() {
		defer wg.Done()
		if err := r.logCPU(logCpuCtx, cpuStream); err != nil {
			r.log.Println(wrapErr(err))
		}
	}()

	// RAM
	memStream := make(chan *Mem, 1)
	memCtx, memCancel := context.WithCancel(ctx)
	logMemCtx, logMemCancel := context.WithCancel(ctx)
	wg.Add(1)
	go func() {
		defer wg.Done()
		r.monitorMem(memCtx, memStream)

	}()
	wg.Add(1)
	go func() {
		defer wg.Done()
		if err := r.logMem(logMemCtx, memStream); err != nil {
			r.log.Println(wrapErr(err))
		}
	}()

	// Disk
	diskChan := make(chan *DiskLog, 20)
	diskCtx, diskCancel := context.WithCancel(ctx)
	logDiskCtx, logDiskCancel := context.WithCancel(ctx)
	wg.Add(1)
	go func() {
		defer wg.Done()
		r.monitorDisk(diskCtx, diskChan)

	}()
	wg.Add(1)
	go func() {
		defer wg.Done()
		if err := r.logDisk(logDiskCtx, diskChan); err != nil {
			r.log.Println(wrapErr(err))
		}
	}()

	<-ctx.Done()
	tcancel()
	cpuCancel()
	logCpuCancel()
	memCancel()
	logMemCancel()
	diskCancel()
	logDiskCancel()

	wg.Wait()

	r.persistInMemDir()
}
