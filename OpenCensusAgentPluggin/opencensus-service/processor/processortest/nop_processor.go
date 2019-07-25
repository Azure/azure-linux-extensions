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

package processortest

import (
	"context"

	"github.com/census-instrumentation/opencensus-service/consumer"
	"github.com/census-instrumentation/opencensus-service/data"
	"github.com/census-instrumentation/opencensus-service/processor"
)

type nopProcessor struct {
	nextTraceProcessor   consumer.TraceConsumer
	nextMetricsProcessor consumer.MetricsConsumer
}

var _ processor.TraceProcessor = (*nopProcessor)(nil)
var _ processor.MetricsProcessor = (*nopProcessor)(nil)

func (np *nopProcessor) ConsumeTraceData(ctx context.Context, td data.TraceData) error {
	return np.nextTraceProcessor.ConsumeTraceData(ctx, td)
}

func (np *nopProcessor) ConsumeMetricsData(ctx context.Context, md data.MetricsData) error {
	return np.nextMetricsProcessor.ConsumeMetricsData(ctx, md)
}

// NewNopTraceProcessor creates an TraceProcessor that just pass the received data to the nextTraceProcessor.
func NewNopTraceProcessor(nextTraceProcessor consumer.TraceConsumer) consumer.TraceConsumer {
	return &nopProcessor{nextTraceProcessor: nextTraceProcessor}
}

// NewNopMetricsProcessor creates an MetricsProcessor that just pass the received data to the nextMetricsProcessor.
func NewNopMetricsProcessor(nextMetricsProcessor consumer.MetricsConsumer) consumer.MetricsConsumer {
	return &nopProcessor{nextMetricsProcessor: nextMetricsProcessor}
}
