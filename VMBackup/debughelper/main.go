package main

import (
	"bytes"
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"os/signal"
	"runtime"
	"strings"
	"sync"

	"github.com/oklog/ulid/v2"
)

var (
	working_directory = flag.String(
		"wd",
		"./",
		"Location which this application will use for all it's processing and persisting data. Please make sure this location does not get frozen during a snapshot operation",
	)
	extension_command = flag.String("extcmd", "", "The command to execute extensions with")
	run_diagnosis     = flag.Bool("diagnose", false, "Daignose the system")
	with_strace       = flag.Bool("strace", false, "The tool will run with strace enabled")
	strace_pid        = flag.Int64("tracepid", 0, "The PID to apply strace on")
	log_to_mem        = flag.Bool("logtomem", true, "Will temporarily log to memory before moving all log files to working directory")
)

func wrapErr(err error, msgs ...string) error {
	pc := make([]uintptr, 15)
	n := runtime.Callers(2, pc)
	frames := runtime.CallersFrames(pc[:n])
	frame, _ := frames.Next()
	src := frame.Function
	s := strings.Join(append([]string{src}, msgs...), " -> ")
	return fmt.Errorf("%s -> %s", s, err.Error())
}

func checkBinExistence(c string) bool {
	if len(c) == 0 {
		return false
	}
	cmd := exec.Command("command", "-v", c)
	bs, err := cmd.CombinedOutput()
	if err != nil {
		log.Println(wrapErr(err, "CombinedOutput failed"))
		return false
	}
	if cmd.ProcessState.ExitCode() != 0 {
		return false
	}
	if len(bs) == 0 {
		return false
	}
	return true
}

func checkSvcExistence(s string) bool {
	if len(s) == 0 {
		return false
	}
	cmd := exec.Command("systemctl", "list-unit-files", "--type", "service")
	cmd2 := exec.Command("grep", "-e", s)
	r, w := io.Pipe()
	cmd.Stdout = w
	cmd2.Stdin = r

	var b2 bytes.Buffer
	cmd2.Stdout = &b2

	cmd.Start()
	cmd2.Start()
	cmd.Wait()
	w.Close()
	cmd2.Wait()

	bs := b2.Bytes()
	if len(bs) == 0 {
		return false
	}
	return true
}

func envVarExists(v string) bool {
	return len(os.Getenv(v)) > 0
}

func databaseText(d string) string {
	return fmt.Sprintf("Unsupported database detected: \"%s\". Please make sure the database is not in use during a snapshot operation. The heavy disk IO behavior of databases can conflict with disk freezing", d)
}

func avText(a string) string {
	return fmt.Sprintf("Anitivirus detected: \"%s\". Make sure no files, directories, or mountpoints are being scanned during a snapshot operation", a)
}

func diagnoseDbs() []string {
	dbreport := []string{}
	if checkSvcExistence("postgresql.service") {
		dbreport = append(dbreport, databaseText("PostgreSQL"))
	}
	if checkSvcExistence("mongod") {
		dbreport = append(dbreport, databaseText("MongoDB"))
	}
	if checkBinExistence("mysqld") || checkBinExistence("mysql") {
		dbreport = append(dbreport, databaseText("MySQL"))
	}
	return dbreport
}

func diagnoseAvs() []string {
	clamAVExists := checkBinExistence("clamscan")
	bitDefenderExists := checkSvcExistence("bdsec*")

	avreport := []string{}

	if clamAVExists {
		avreport = append(avreport, avText("ClamAV"))
	}
	if bitDefenderExists {
		avreport = append(avreport, avText("Bitdefender"))
	}

	return avreport
}

func main() {
	flag.Parse()
	opID := fmt.Sprintf("%s", ulid.Make())

	if *with_strace && *strace_pid == 0 {
		log.Printf("Cannot trace PID: 0")
		return
	}

	r, rf, err := NewRun(*working_directory, opID, *with_strace, *strace_pid, *log_to_mem)
	if err != nil {
		log.Println(wrapErr(err))
		return
	}
	defer rf.Close()

	if *run_diagnosis {
		lf := r.diagnose()
		log.Printf("Diagnosis has been written to:\n%s\n", lf)
		return
	}

	wg := sync.WaitGroup{}
	ctx, cancel := context.WithCancel(context.Background())
	wg.Add(1)
	go func() {
		defer wg.Done()
		r.monitor(ctx)
	}()

	inter := make(chan os.Signal, 1)
	signal.Notify(inter, os.Interrupt)
	<-inter
	cancel()
	wg.Wait()
}
