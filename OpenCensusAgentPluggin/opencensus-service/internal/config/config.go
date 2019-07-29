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

package config

import (
	"fmt"
	"strings"

	"github.com/spf13/viper"
	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"

	"github.com/census-instrumentation/opencensus-service/consumer"

	"github.com/census-instrumentation/opencensus-service/exporter/azuremonitorexporter"
	"github.com/census-instrumentation/opencensus-service/exporter/opencensusexporter"
	"github.com/census-instrumentation/opencensus-service/receiver/opencensusreceiver"
)

// We expect the configuration.yaml file to look like this:
//
//  receivers:
//      opencensus:
//          port: <port>
//
//      zipkin:
//          reporter: <address>
//
//      prometheus:
//          config:
//             scrape_configs:
//               - job_name: 'foo_service"
//                 scrape_interval: 5s
//                 static_configs:
//                   - targets: ['localhost:8889']
//          buffer_count: 10
//          buffer_period: 5s
//
//  exporters:
//      stackdriver:
//          project: <project_id>
//          enable_tracing: true
//      zipkin:
//          endpoint: "http://localhost:9411/api/v2/spans"
//
//  zpages:
//      port: 55679

const (
	defaultOCReceiverAddress = ":55678"
)

var defaultOCReceiverCorsAllowedOrigins = []string{}

// Config denotes the configuration for the various elements of an agent, that is:
// * Receivers
// * ZPages
// * Exporters
type Config struct {
	Receivers *Receivers `mapstructure:"receivers"`
	Exporters *Exporters `mapstructure:"exporters"`
}

// Receivers denotes configurations for the various telemetry ingesters, such as:
// * OpenCensus (metrics and traces)
type Receivers struct {
	OpenCensus *ReceiverConfig `mapstructure:"opencensus"`
}

// ReceiverConfig is the per-receiver configuration that identifies attributes
// that a receiver's configuration can have such as:
// * Address
// * Various ports
type ReceiverConfig struct {
	// The address to which the OpenCensus receiver will be bound and run on.
	Address             string `mapstructure:"address"`
	CollectorHTTPPort   int    `mapstructure:"collector_http_port"`
	CollectorThriftPort int    `mapstructure:"collector_thrift_port"`

	// The allowed CORS origins for HTTP/JSON requests the grpc-gateway adapter
	// for the OpenCensus receiver. See github.com/rs/cors
	// An empty list means that CORS is not enabled at all. A wildcard (*) can be
	// used to match any origin or one or more characters of an origin.
	CorsAllowedOrigins []string `mapstructure:"cors_allowed_origins"`

	// DisableTracing disables trace receiving and is only applicable to trace receivers.
	DisableTracing bool `mapstructure:"disable_tracing"`
	// DisableMetrics disables metrics receiving and is only applicable to metrics receivers.
	DisableMetrics bool `mapstructure:"disable_metrics"`

	// TLSCredentials is a (cert_file, key_file) configuration.
	TLSCredentials *TLSCredentials `mapstructure:"tls_credentials"`
}

// ScribeReceiverConfig carries the settings for the Zipkin Scribe receiver.
type ScribeReceiverConfig struct {
	// Address is an IP address or a name that can be resolved to a local address.
	//
	// It can use a name, but this is not recommended, because it will create
	// a listener for at most one of the host's IP addresses.
	//
	// The default value bind to all available interfaces on the local computer.
	Address string `mapstructure:"address" mapstructure:"address"`
	Port    uint16 `mapstructure:"port" mapstructure:"port"`
	// Category is the string that will be used to identify the scribe log messages
	// that contain Zipkin spans.
	Category string `mapstructure:"category" mapstructure:"category"`
}

// Exporters denotes the configurations for the various backends
// that this service exports observability signals to.
type Exporters struct {
	//Zipkin *zipkinexporter.ZipkinConfig `mapstructure:"zipkin"`
}

// OpenCensusReceiverAddress is a helper to safely retrieve the address
// that the OpenCensus receiver will be bound to.
// If Config is nil or the OpenCensus receiver's configuration is nil, it
// will return the default of ":55678"
func (c *Config) OpenCensusReceiverAddress() string {
	if c == nil || c.Receivers == nil {
		return defaultOCReceiverAddress
	}
	inCfg := c.Receivers
	if inCfg.OpenCensus == nil || inCfg.OpenCensus.Address == "" {
		return defaultOCReceiverAddress
	}
	return inCfg.OpenCensus.Address
}

// OpenCensusReceiverCorsAllowedOrigins is a helper to safely retrieve the list
// of allowed CORS origins for HTTP/JSON requests to the grpc-gateway adapter.
func (c *Config) OpenCensusReceiverCorsAllowedOrigins() []string {
	if c == nil || c.Receivers == nil {
		return defaultOCReceiverCorsAllowedOrigins
	}
	inCfg := c.Receivers
	if inCfg.OpenCensus == nil {
		return defaultOCReceiverCorsAllowedOrigins
	}
	return inCfg.OpenCensus.CorsAllowedOrigins
}

// CanRunOpenCensusTraceReceiver returns true if the configuration
// permits running the OpenCensus Trace receiver.
func (c *Config) CanRunOpenCensusTraceReceiver() bool {
	return c.openCensusReceiverEnabled() && !c.Receivers.OpenCensus.DisableTracing
}

// CanRunOpenCensusMetricsReceiver returns true if the configuration
// permits running the OpenCensus Metrics receiver.
func (c *Config) CanRunOpenCensusMetricsReceiver() bool {
	return c.openCensusReceiverEnabled() && !c.Receivers.OpenCensus.DisableMetrics
}

// openCensusReceiverEnabled returns true if both:
//    Config.Receivers and Config.Receivers.OpenCensus
// are non-nil.
func (c *Config) openCensusReceiverEnabled() bool {
	return c != nil && c.Receivers != nil &&
		c.Receivers.OpenCensus != nil
}

// HasTLSCredentials returns true if TLSCredentials is non-nil
func (rCfg *ReceiverConfig) HasTLSCredentials() bool {
	return rCfg != nil && rCfg.TLSCredentials != nil && rCfg.TLSCredentials.nonEmpty()
}

// OpenCensusReceiverTLSServerCredentials retrieves the TLS credentials
// from this Config's OpenCensus receiver if any.
func (c *Config) OpenCensusReceiverTLSServerCredentials() *TLSCredentials {
	if !c.openCensusReceiverEnabled() {
		return nil
	}

	ocrConfig := c.Receivers.OpenCensus
	if !ocrConfig.HasTLSCredentials() {
		return nil
	}
	return ocrConfig.TLSCredentials
}

// ToOpenCensusReceiverServerOption checks if the TLS credentials
// in the form of a certificate file and a key file. If they aren't,
// it will return opencensusreceiver.WithNoopOption() and a nil error.
// Otherwise, it will try to retrieve gRPC transport credentials from the file combinations,
// and create a option, along with any errors encountered while retrieving the credentials.
func (tlsCreds *TLSCredentials) ToOpenCensusReceiverServerOption() (opt opencensusreceiver.Option, ok bool, err error) {
	if tlsCreds == nil {
		return opencensusreceiver.WithNoopOption(), false, nil
	}

	transportCreds, err := credentials.NewServerTLSFromFile(tlsCreds.CertFile, tlsCreds.KeyFile)
	if err != nil {
		return nil, false, err
	}
	gRPCCredsOpt := grpc.Creds(transportCreds)
	return opencensusreceiver.WithGRPCServerOptions(gRPCCredsOpt), true, nil
}

// OpenCensusReceiverTLSCredentialsServerOption checks if the OpenCensus receiver's Configuration
// has TLS credentials in the form of a certificate file and a key file. If it doesn't
// have any, it will return opencensusreceiver.WithNoopOption() and a nil error.
// Otherwise, it will try to retrieve gRPC transport credentials from the file combinations,
// and create a option, along with any errors encountered while retrieving the credentials.
func (c *Config) OpenCensusReceiverTLSCredentialsServerOption() (opt opencensusreceiver.Option, ok bool, err error) {
	tlsCreds := c.OpenCensusReceiverTLSServerCredentials()
	return tlsCreds.ToOpenCensusReceiverServerOption()
}

func eqHosts(host1, host2 string) bool {
	if host1 == host2 {
		return true
	}
	return eqLocalHost(host1) && eqLocalHost(host2)
}

func eqLocalHost(host string) bool {
	switch strings.ToLower(host) {
	case "", "localhost", "127.0.0.1":
		return true
	default:
		return false
	}
}

// ExportersFromViperConfig uses the viper configuration payload to returns the respective exporters
// from:
//  + datadog
//  + stackdriver
//  + zipkin
//  + jaeger
//  + kafka
//  + opencensus
//  + prometheus
//  + aws-xray
//  + honeycomb
func ExportersFromViperConfig(logger *zap.Logger, v *viper.Viper) ([]consumer.TraceConsumer, []consumer.MetricsConsumer, []func() error, error) {
	parseFns := []struct {
		name string
		fn   func(*viper.Viper) ([]consumer.TraceConsumer, []consumer.MetricsConsumer, []func() error, error)
	}{
		//{name: "kafka", fn: kafkaexporter.KafkaExportersFromViper},
		{name: "opencensus", fn: opencensusexporter.OpenCensusTraceExportersFromViper},
		{name: "azuremonitor", fn: azuremonitorexporter.AzureMonitorExportersFromViper},
	}

	var traceExporters []consumer.TraceConsumer
	var metricsExporters []consumer.MetricsConsumer
	var doneFns []func() error
	exportersViper := v.Sub("exporters")
	if exportersViper == nil {
		return nil, nil, nil, nil
	}
	for _, cfg := range parseFns {
		tes, mes, tesDoneFns, err := cfg.fn(exportersViper)
		if err != nil {
			err = fmt.Errorf("failed to create config for %q: %v", cfg.name, err)
			return nil, nil, nil, err
		}

		for _, te := range tes {
			if te != nil {
				traceExporters = append(traceExporters, te)
				logger.Info("Trace Exporter enabled", zap.String("exporter", cfg.name))
			}
		}

		for _, me := range mes {
			if me != nil {
				metricsExporters = append(metricsExporters, me)
				logger.Info("Metrics Exporter enabled", zap.String("exporter", cfg.name))
			}
		}

		for _, doneFn := range tesDoneFns {
			if doneFn != nil {
				doneFns = append(doneFns, doneFn)
			}
		}
	}
	return traceExporters, metricsExporters, doneFns, nil
}
