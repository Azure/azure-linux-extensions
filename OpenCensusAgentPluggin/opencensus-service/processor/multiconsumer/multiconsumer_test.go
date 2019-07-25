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
package multiconsumer

import (
	"context"
	"fmt"
	"testing"

	metricspb "github.com/census-instrumentation/opencensus-proto/gen-go/metrics/v1"
	tracepb "github.com/census-instrumentation/opencensus-proto/gen-go/trace/v1"
	"github.com/census-instrumentation/opencensus-service/consumer"
	"github.com/census-instrumentation/opencensus-service/data"
)

func TestTraceProcessorMultiplexing(t *testing.T) {
	processors := make([]consumer.TraceConsumer, 3)
	for i := range processors {
		processors[i] = &mockTraceConsumer{}
	}

	tdp := NewTraceProcessor(processors)
	td := data.TraceData{
		Spans: make([]*tracepb.Span, 7),
	}

	var wantSpansCount = 0
	for i := 0; i < 2; i++ {
		wantSpansCount += len(td.Spans)
		err := tdp.ConsumeTraceData(context.Background(), td)
		if err != nil {
			t.Errorf("Wanted nil got error")
			return
		}
	}

	for _, p := range processors {
		m := p.(*mockTraceConsumer)
		if m.TotalSpans != wantSpansCount {
			t.Errorf("Wanted %d spans for every processor but got %d", wantSpansCount, m.TotalSpans)
			return
		}
	}
}

func TestTraceProcessorWhenOneErrors(t *testing.T) {
	processors := make([]consumer.TraceConsumer, 3)
	for i := range processors {
		processors[i] = &mockTraceConsumer{}
	}

	// Make one processor return error
	processors[1].(*mockTraceConsumer).MustFail = true

	tdp := NewTraceProcessor(processors)
	td := data.TraceData{
		Spans: make([]*tracepb.Span, 5),
	}

	var wantSpansCount = 0
	for i := 0; i < 2; i++ {
		wantSpansCount += len(td.Spans)
		err := tdp.ConsumeTraceData(context.Background(), td)
		if err == nil {
			t.Errorf("Wanted error got nil")
			return
		}
	}

	for _, p := range processors {
		m := p.(*mockTraceConsumer)
		if m.TotalSpans != wantSpansCount {
			t.Errorf("Wanted %d spans for every processor but got %d", wantSpansCount, m.TotalSpans)
			return
		}
	}
}

func TestMetricsProcessorMultiplexing(t *testing.T) {
	processors := make([]consumer.MetricsConsumer, 3)
	for i := range processors {
		processors[i] = &mockMetricsConsumer{}
	}

	mdp := NewMetricsProcessor(processors)
	md := data.MetricsData{
		Metrics: make([]*metricspb.Metric, 7),
	}

	var wantMetricsCount = 0
	for i := 0; i < 2; i++ {
		wantMetricsCount += len(md.Metrics)
		err := mdp.ConsumeMetricsData(context.Background(), md)
		if err != nil {
			t.Errorf("Wanted nil got error")
			return
		}
	}

	for _, p := range processors {
		m := p.(*mockMetricsConsumer)
		if m.TotalMetrics != wantMetricsCount {
			t.Errorf("Wanted %d metrics for every processor but got %d", wantMetricsCount, m.TotalMetrics)
			return
		}
	}
}

func TestMetricsProcessorWhenOneErrors(t *testing.T) {
	processors := make([]consumer.MetricsConsumer, 3)
	for i := range processors {
		processors[i] = &mockMetricsConsumer{}
	}

	// Make one processor return error
	processors[1].(*mockMetricsConsumer).MustFail = true

	mdp := NewMetricsProcessor(processors)
	md := data.MetricsData{
		Metrics: make([]*metricspb.Metric, 5),
	}

	var wantMetricsCount = 0
	for i := 0; i < 2; i++ {
		wantMetricsCount += len(md.Metrics)
		err := mdp.ConsumeMetricsData(context.Background(), md)
		if err == nil {
			t.Errorf("Wanted error got nil")
			return
		}
	}

	for _, p := range processors {
		m := p.(*mockMetricsConsumer)
		if m.TotalMetrics != wantMetricsCount {
			t.Errorf("Wanted %d metrics for every processor but got %d", wantMetricsCount, m.TotalMetrics)
			return
		}
	}
}

type mockTraceConsumer struct {
	TotalSpans int
	MustFail   bool
}

var _ consumer.TraceConsumer = &mockTraceConsumer{}

func (p *mockTraceConsumer) ConsumeTraceData(ctx context.Context, td data.TraceData) error {
	p.TotalSpans += len(td.Spans)
	if p.MustFail {
		return fmt.Errorf("this processor must fail")
	}

	return nil
}

type mockMetricsConsumer struct {
	TotalMetrics int
	MustFail     bool
}

var _ consumer.MetricsConsumer = &mockMetricsConsumer{}

func (p *mockMetricsConsumer) ConsumeMetricsData(ctx context.Context, td data.MetricsData) error {
	p.TotalMetrics += len(td.Metrics)
	if p.MustFail {
		return fmt.Errorf("this processor must fail")
	}

	return nil
}
