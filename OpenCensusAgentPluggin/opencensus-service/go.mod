module github.com/census-instrumentation/opencensus-service

require (
	contrib.go.opencensus.io/exporter/aws v0.0.0-20181029163544-2befc13012d0
	contrib.go.opencensus.io/exporter/jaeger v0.1.1-0.20190430175949-e8b55949d948
	contrib.go.opencensus.io/exporter/ocagent v0.5.0
	contrib.go.opencensus.io/exporter/prometheus v0.1.0
	contrib.go.opencensus.io/exporter/stackdriver v0.12.3-0.20190626200219-09504ed717c7 // TODO: pin a released version
	contrib.go.opencensus.io/exporter/zipkin v0.1.1
	contrib.go.opencensus.io/resource v0.1.1
	github.com/ChrisCoe/opencensus-go-exporter-azuremonitor v0.0.0-20190729080708-927f6d285646
	github.com/DataDog/datadog-go v2.2.0+incompatible // indirect
	github.com/DataDog/opencensus-go-exporter-datadog v0.0.0-20181026070331-e7c4bd17b329
	github.com/VividCortex/gohistogram v1.0.0 // indirect
	github.com/apache/thrift v0.0.0-20161221203622-b2a4d4ae21c7
	github.com/bmizerany/perks v0.0.0-20141205001514-d9a9656a3a4b // indirect
	github.com/census-instrumentation/opencensus-proto v0.2.0
	github.com/go-kit/kit v0.8.0
	github.com/gogo/googleapis v1.2.0 // indirect
	github.com/golang/protobuf v1.3.1
	github.com/google/go-cmp v0.3.0
	github.com/gorilla/mux v1.6.2
	github.com/grpc-ecosystem/grpc-gateway v1.8.5
	github.com/honeycombio/opencensus-exporter v1.0.1
	github.com/inconshreveable/mousetrap v1.0.0 // indirect
	github.com/jaegertracing/jaeger v1.9.0
	github.com/omnition/scribe-go v0.0.0-20190131012523-9e3c68f31124
	github.com/opentracing/opentracing-go v1.1.0 // indirect
	github.com/openzipkin/zipkin-go v0.1.6
	github.com/orijtech/prometheus-go-metrics-exporter v0.0.3-0.20190313163149-b321c5297f60
	github.com/philhofer/fwd v1.0.0 // indirect
	github.com/pkg/errors v0.8.0
	github.com/prashantv/protectmem v0.0.0-20171002184600-e20412882b3a // indirect
	github.com/prometheus/client_golang v0.9.2
	github.com/prometheus/common v0.0.0-20181126121408-4724e9255275
	github.com/prometheus/procfs v0.0.0-20190117184657-bf6a532e95b1
	github.com/prometheus/prometheus v0.0.0-20190131111325-62e591f928dd
	github.com/rs/cors v1.6.0
	github.com/soheilhy/cmux v0.1.4
	github.com/spf13/cast v1.2.0
	github.com/spf13/cobra v0.0.3
	github.com/spf13/viper v1.2.1
	github.com/streadway/quantile v0.0.0-20150917103942-b0c588724d25 // indirect
	github.com/stretchr/testify v1.3.0
	github.com/tinylib/msgp v1.1.0 // indirect
	github.com/uber-go/atomic v1.3.2 // indirect
	github.com/uber/jaeger-client-go v2.16.0+incompatible // indirect
	github.com/uber/jaeger-lib v2.0.0+incompatible
	github.com/uber/tchannel-go v1.10.0
	github.com/wavefronthq/opencensus-exporter v0.0.0-20190506162721-983d7cdaceaf
	github.com/wavefronthq/wavefront-sdk-go v0.9.2
	github.com/yancl/opencensus-go-exporter-kafka v0.0.0-20181029030031-9c471c1bfbeb
	go.opencensus.io v0.22.0
	go.uber.org/atomic v1.3.2 // indirect
	go.uber.org/multierr v1.1.0 // indirect
	go.uber.org/zap v1.9.1
	golang.org/x/lint v0.0.0-20190313153728-d0100b6bd8b3
	google.golang.org/api v0.5.0
	google.golang.org/grpc v1.21.0
	gopkg.in/DataDog/dd-trace-go.v1 v1.12.1 // indirect
	gopkg.in/yaml.v2 v2.2.2
)
