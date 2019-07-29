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

func runOCAgent() {
	fmt.Println("it's ya boy")
	viperCfg.SetConfigFile(configYAMLFile)
	err := viperCfg.ReadInConfig()
	if err != nil {
		log.Fatalf("Cannot read the YAML file %v error: %v", configYAMLFile, err)
	}

	var agentConfig config.Config
	err = viperCfg.Unmarshal(&agentConfig)
	if err != nil {
		log.Fatalf("Error unmarshalling yaml config file %v: %v", configYAMLFile, err)
	}

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

	traceExporters, metricsExporters, closeFns, err := config.ExportersFromViperConfig(logger, viperCfg)
	if err != nil {
		log.Fatalf("Config: failed to create exporters from YAML: %v", err)
	}

	commonSpanSink := multiconsumer.NewTraceProcessor(traceExporters)
	commonMetricsSink := multiconsumer.NewMetricsProcessor(metricsExporters)

	// Add other receivers here as they are implemented
	ocReceiverDoneFn, err := runOCReceiver(logger, &agentConfig, commonSpanSink, commonMetricsSink, asyncErrorChan)
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

func runOCReceiver(logger *zap.Logger, acfg *config.Config, tc consumer.TraceConsumer, mc consumer.MetricsConsumer, asyncErrorChan chan<- error) (doneFn func() error, err error) {
	tlsCredsOption, hasTLSCreds, err := acfg.OpenCensusReceiverTLSCredentialsServerOption()
	if err != nil {
		return nil, fmt.Errorf("OpenCensus receiver TLS Credentials: %v", err)
	}
	addr := acfg.OpenCensusReceiverAddress()
	corsOrigins := acfg.OpenCensusReceiverCorsAllowedOrigins()
	ocr, err := opencensusreceiver.New(addr,
		tc,
		mc,
		tlsCredsOption,
		opencensusreceiver.WithCorsOrigins(corsOrigins))

	if err != nil {
		return nil, fmt.Errorf("failed to create the OpenCensus receiver on address %q: error %v", addr, err)
	}
	if err := view.Register(observability.AllViews...); err != nil {
		return nil, fmt.Errorf("failed to register internal.AllViews: %v", err)
	}

	// Temporarily disabling the grpc metrics since they do not provide good data at this moment,
	// See https://github.com/census-instrumentation/opencensus-service/issues/287
	// if err := view.Register(ocgrpc.DefaultServerViews...); err != nil {
	// 	return nil, fmt.Errorf("Failed to register ocgrpc.DefaultServerViews: %v", err)
	// }

	ctx := context.Background()

	switch {
	case acfg.CanRunOpenCensusTraceReceiver() && acfg.CanRunOpenCensusMetricsReceiver():
		if err := ocr.Start(ctx); err != nil {
			return nil, fmt.Errorf("failed to start Trace and Metrics Receivers: %v", err)
		}
		log.Printf("Running OpenCensus Trace and Metrics receivers as a gRPC service at %q", addr)

	case acfg.CanRunOpenCensusTraceReceiver():
		if err := ocr.StartTraceReception(ctx, asyncErrorChan); err != nil {
			return nil, fmt.Errorf("failed to start TraceReceiver: %v", err)
		}
		log.Printf("Running OpenCensus Trace receiver as a gRPC service at %q", addr)

	case acfg.CanRunOpenCensusMetricsReceiver():
		if err := ocr.StartMetricsReception(ctx, asyncErrorChan); err != nil {
			return nil, fmt.Errorf("failed to start MetricsReceiver: %v", err)
		}
		log.Printf("Running OpenCensus Metrics receiver as a gRPC service at %q", addr)
	}

	if hasTLSCreds {
		tlsCreds := acfg.OpenCensusReceiverTLSServerCredentials()
		logger.Info("OpenCensus receiver with TLS Credentials",
			zap.String("cert_file", tlsCreds.CertFile),
			zap.String("key_file", tlsCreds.KeyFile))
	}

	doneFn = ocr.Stop
	return doneFn, nil
}
