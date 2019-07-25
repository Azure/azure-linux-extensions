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

package jaegerexporter

import (
	"github.com/spf13/viper"

	"contrib.go.opencensus.io/exporter/jaeger"

	"github.com/census-instrumentation/opencensus-service/consumer"
	"github.com/census-instrumentation/opencensus-service/exporter/exporterwrapper"
)

// Slight modified version of go/src/contrib.go.opencensus.io/exporter/jaeger/jaeger.go
type jaegerConfig struct {
	CollectorEndpoint string `mapstructure:"collector_endpoint,omitempty"`
	Username          string `mapstructure:"username,omitempty"`
	Password          string `mapstructure:"password,omitempty"`
	ServiceName       string `mapstructure:"service_name,omitempty"`
}

// JaegerExportersFromViper unmarshals the viper and returns exporter.TraceExporters targeting
// Jaeger according to the configuration settings.
func JaegerExportersFromViper(v *viper.Viper) (tps []consumer.TraceConsumer, mps []consumer.MetricsConsumer, doneFns []func() error, err error) {
	var cfg struct {
		Jaeger *jaegerConfig `mapstructure:"jaeger"`
	}
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, nil, nil, err
	}
	jc := cfg.Jaeger
	if jc == nil {
		return nil, nil, nil, nil
	}

	// jaeger.NewExporter performs configurqtion validation
	je, err := jaeger.NewExporter(jaeger.Options{
		CollectorEndpoint: jc.CollectorEndpoint,
		Username:          jc.Username,
		Password:          jc.Password,
		Process: jaeger.Process{
			ServiceName: jc.ServiceName,
		},
	})
	if err != nil {
		return nil, nil, nil, err
	}

	doneFns = append(doneFns, func() error {
		je.Flush()
		return nil
	})

	jte, err := exporterwrapper.NewExporterWrapper("jaeger", "ocservice.exporter.Jaeger.ConsumeTraceData", je)
	if err != nil {
		return nil, nil, nil, err
	}
	// TODO: Examine "contrib.go.opencensus.io/exporter/jaeger" to see
	// if trace.ExportSpan was constraining and if perhaps the Jaeger
	// upload can use the context and information from the Node.
	tps = append(tps, jte)
	return
}
