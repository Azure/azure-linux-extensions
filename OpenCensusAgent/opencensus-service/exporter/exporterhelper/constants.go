// Copyright 2019, OpenCensus Authors
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

package exporterhelper

import (
	"errors"
)

var (
	// errEmptyExporterFormat is returned when an empty name is given.
	errEmptyExporterFormat = errors.New("empty exporter format")
	// errNilPushTraceData is returned when a nil pushTraceData is given.
	errNilPushTraceData = errors.New("nil pushTraceData")
	// errNilPushMetricsData is returned when a nil pushMetricsData is given.
	errNilPushMetricsData = errors.New("nil pushMetricsData")
)

const (
	numDroppedMetricsAttribute  = "num_dropped_metrics"
	numReceivedMetricsAttribute = "num_received_metrics"
	numDroppedSpansAttribute    = "num_dropped_spans"
	numReceivedSpansAttribute   = "num_received_spans"
)
