// Copyright 2018, OpenCensus Authors
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Program ocagent collects OpenCensus stats and traces
// to export to a configured backend.
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
	"go.opencensus.io/stats/view"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"

	"github.com/census-instrumentation/opencensus-service/consumer"
	"github.com/census-instrumentation/opencensus-service/exporter/exporterwrapper"
	"github.com/census-instrumentation/opencensus-service/internal/config"
	"github.com/census-instrumentation/opencensus-service/internal/config/viperutils"
	"github.com/census-instrumentation/opencensus-service/internal/pprofserver"
	"github.com/census-instrumentation/opencensus-service/internal/version"
	"github.com/census-instrumentation/opencensus-service/observability"
	"github.com/census-instrumentation/opencensus-service/processor/multiconsumer"
	"github.com/census-instrumentation/opencensus-service/receiver/opencensusreceiver"
)

var rootCmd = &cobra.Command{
	Use:   "ocagent",
	Short: "ocagent runs the OpenCensus service",
	Run: func(cmd *cobra.Command, args []string) {
		runOCAgent()
	},
}

var viperCfg = viper.New()

var configYAMLFile string

func init() {
	var versionCmd = &cobra.Command{
		Use:   "version",
		Short: "Print the version information for ocagent",
		Run: func(cmd *cobra.Command, args []string) {
			fmt.Print(version.Info())
		},
	}
	rootCmd.AddCommand(versionCmd)
	rootCmd.PersistentFlags().StringVarP(&configYAMLFile, "config", "c", "config.yaml", "The YAML file with the configurations for the agent and various exporters")

	viperutils.AddFlags(viperCfg, rootCmd, pprofserver.AddFlags)
}

func main() {
	if err := rootCmd.Execute(); err != nil {
		log.Fatal(err)
	}
}

// Modified version of OpenCensus Agent, but relies heavily on original version minus exporters (https://github.com/census-instrumentation/opencensus-service)
// For this prototype of sending spans to 1Agent, we want to use the Opencensus Receiver in the Agent to collect Opencensus Proto data.
func runOCAgent() {
	var agentConfig config.Config

	// TODO: don't hardcode info level logging
	conf := zap.NewProductionConfig()
	conf.Level.SetLevel(zapcore.InfoLevel)
	logger, err := conf.Build()
	if err != nil {
		log.Fatalf("Could not instantiate logger: %v", err)
	}

	var asyncErrorChan = make(chan error)
	err = pprofserver.SetupFromViper(asyncErrorChan, viperCfg, logger)
	if err != nil {
		log.Fatalf("Failed to start net/http/pprof: %v", err)
	}

	traceExporters, _, closeFns, err := config.ExportersFromViperConfig(logger, viperCfg)

	if err != nil {
		log.Fatalf("Config: failed to create exporters from YAML: %v", err)
	}

	// Create exporter wrapper to trigger process to push out OC proto data to be intercepted and sent to 1Agent
	emptyTraceExporter, err := exporterwrapper.NewExporterWrapper("emptyExporter", "ocservice.exporter.Empty.ConsumeTraceData", nil)
	if err != nil {
		log.Fatalf("Could not create exporter wrapper to push OC proto data: %v", err)
	}
	traceExporters = append(traceExporters, emptyTraceExporter)
	commonSpanSink := multiconsumer.NewTraceProcessor(traceExporters)

	// Add other receivers here as they are implemented
	ocReceiverDoneFn, err := runOCReceiver(logger, &agentConfig, commonSpanSink, asyncErrorChan)
	if err != nil {
		log.Fatal(err)
	}
	closeFns = append(closeFns, ocReceiverDoneFn)

	// Always cleanup finally
	defer func() {
		for _, closeFn := range closeFns {
			if closeFn != nil {
				closeFn()
			}
		}
	}()

	signalsChan := make(chan os.Signal, 1)
	signal.Notify(signalsChan, os.Interrupt, syscall.SIGTERM)

	select {
	case err = <-asyncErrorChan:
		log.Fatalf("Asynchronous error %q, terminating process", err)
	case s := <-signalsChan:
		log.Printf("Received %q signal from OS, terminating process", s)
	}
}

func runOCReceiver(logger *zap.Logger, acfg *config.Config, tc consumer.TraceConsumer, asyncErrorChan chan<- error) (doneFn func() error, err error) {
	tlsCredsOption, _, err := acfg.OpenCensusReceiverTLSCredentialsServerOption()
	if err != nil {
		return nil, fmt.Errorf("OpenCensus receiver TLS Credentials: %v", err)
	}
	addr := acfg.OpenCensusReceiverAddress()
	corsOrigins := acfg.OpenCensusReceiverCorsAllowedOrigins()
	ocr, err := opencensusreceiver.New(addr,
		tc,
		tlsCredsOption,
		opencensusreceiver.WithCorsOrigins(corsOrigins))

	if err != nil {
		return nil, fmt.Errorf("failed to create the OpenCensus receiver on address %q: error %v", addr, err)
	}
	if err := view.Register(observability.AllViews...); err != nil {
		return nil, fmt.Errorf("failed to register internal.AllViews: %v", err)
	}

	ctx := context.Background()

	if err := ocr.StartTraceReception(ctx, asyncErrorChan); err != nil {
		return nil, fmt.Errorf("failed to start TraceReceiver: %v", err)
	}
	log.Printf("Running OpenCensus Trace receiver as a gRPC service at %q", addr)

	doneFn = ocr.Stop
	return doneFn, nil
}
