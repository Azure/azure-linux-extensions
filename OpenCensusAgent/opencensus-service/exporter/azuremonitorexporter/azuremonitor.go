package azuremonitorexporter

import (
	"github.com/spf13/viper"

	// TODO: once this repository has been transferred to the
	// official census-ecosystem location, update this import path.
	"github.com/ChrisCoe/opencensus-go-exporter-azuremonitor/azuremonitor"
	"github.com/ChrisCoe/opencensus-go-exporter-azuremonitor/azuremonitor/common"

	"github.com/census-instrumentation/opencensus-service/consumer"
	"github.com/census-instrumentation/opencensus-service/exporter/exporterwrapper"
)

type azuermonitorconfig struct {
	InstrumentationKey string `mapstructure:"instrumentationKey"`
}

// AzureMonitorExportersFromViper unmarshals the viper and returns exporter.TraceExporters targeting
// Azure Monitor according to the configuration settings.
func AzureMonitorExportersFromViper(v *viper.Viper) (traceExporters []consumer.TraceConsumer, metricExporters []consumer.MetricsConsumer, doneFns []func() error, err error) {
	var cfg struct { // cfg stands for config. I am following the naming convention 
					 // used for all the exporters in this package
		AzureMonitor *azuermonitorconfig `mapstructure:"azuremonitor"`
	}
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, nil, nil, err
	}
	azureMonitorConfig := cfg.AzureMonitor
	if azureMonitorConfig == nil {
		return nil, nil, nil, nil
	}
	azureExporter, err := azuremonitor.NewAzureTraceExporter(common.Options{
		InstrumentationKey: azureMonitorConfig.InstrumentationKey, // add InstrumentationKey
	})

	if err != nil {
		return nil, nil, nil, err
	}

	doneFns = append(doneFns, func() error {
		return nil
	})

	azureMonitorTraceExporter, err := exporterwrapper.NewExporterWrapper("azuremonitor", "ocservice.exporter.AzureMonitor.ConsumeTraceData", azureExporter)
	if err != nil {
		return nil, nil, nil, err
	}

	traceExporters = append(traceExporters, azureMonitorTraceExporter)
	return
}
