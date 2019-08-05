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

// Package exporterwrapper provides support for wrapping OC go library trace.Exporter into a
// consumer.TraceConsumer.
// For now it currently only provides statically imported OpenCensus
// exporters like:
//  * Stackdriver Tracing and Monitoring
//  * DataDog
//  * Zipkin
package exporterwrapper

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"strconv"
	"time"

	"go.opencensus.io/trace"

	tracepb "github.com/census-instrumentation/opencensus-proto/gen-go/trace/v1"
	"github.com/census-instrumentation/opencensus-service/data"
	"github.com/census-instrumentation/opencensus-service/exporter"
	"github.com/census-instrumentation/opencensus-service/exporter/exporterhelper"
	"github.com/census-instrumentation/opencensus-service/internal"
	spandatatranslator "github.com/census-instrumentation/opencensus-service/translator/trace/spandata"
)

// NewExporterWrapper returns a consumer.TraceConsumer that converts OpenCensus Proto TraceData
// to OpenCensus-Go SpanData and calls into the given trace.Exporter.
//
// This is a bootstrapping mechanism for us to re-use as many of
// the OpenCensus-Go trace.SpanData exporters which were written
// by various vendors and contributors. Eventually the goal is to
// get those exporters converted to directly receive
// OpenCensus Proto TraceData.
func NewExporterWrapper(exporterName string, spanName string, ocExporter trace.Exporter) (exporter.TraceExporter, error) {
	return exporterhelper.NewTraceExporter(
		exporterName,
		func(ctx context.Context, td data.TraceData) (int, error) {
			return PushOcProtoSpansToOCTraceExporter(ocExporter, td)
		},
		exporterhelper.WithSpanName(spanName),
		exporterhelper.WithRecordMetrics(true),
	)
}

// TODO: Remove PushOcProtoSpansToOCTraceExporter after aws-xray is changed to ExporterWrapper.

// PushOcProtoSpansToOCTraceExporter pushes TraceData to the given trace.Exporter by converting the
// protos to trace.SpanData.
func PushOcProtoSpansToOCTraceExporter(ocExporter trace.Exporter, td data.TraceData) (int, error) {
	var errs []error
	var goodSpans []*tracepb.Span
	for _, span := range td.Spans {
		sd, err := spandatatranslator.ProtoSpanToOCSpanData(span)
		spanData := ConvertOCSpanDataToApplicationInsightsSchema(sd)
		SendSpanTo1Agent(spanData)
		if err == nil {
			//ocExporter.ExportSpan(sd) // We don't export here and instead let the 1Agent export the span
			goodSpans = append(goodSpans, span)
		} else {
			errs = append(errs, err)
		}
	}

	return len(td.Spans) - len(goodSpans), internal.CombineErrors(errs)
}

type mdsdJSON struct {
	Tag    string   `json:"TAG"` // Tag is used to see if acknowledged by 1Agent
	Source string   `json:"SOURCE"`
	Data   []string `json:"DATA"` // Data must be an array
}

// SendTraceTo1Agent makes a connection to 1Agent and passes in the OpenCensus proto trace in JSON format
func SendSpanTo1Agent(spanData string) {
	log.Println("Starting funnel of data.")

	conn, err := net.Dial("unix", "/var/run/mdsd/default_json.socket")
	if err != nil {
		log.Printf("Error connecting: %v", err)
		return
	}
	dataList := []string{
		spanData, //WholeTrace, this part is defined in schema found in mdsd.xml
	}
	id := time.Now().UTC()

	trace := new(mdsdJSON)
	trace.Tag = strconv.FormatInt(id.Unix(), 10) // Use time to create a unique Tag
	trace.Source = "funnel"                      // "funnel" defined in schema
	trace.Data = dataList

	byteData, err := json.Marshal(trace)
	if err != nil {
		log.Printf("Error marshaling mdsdJSON: %v", err)
		return
	}
	_, err = conn.Write(byteData)
	if err != nil {
		log.Printf("Error writing to 1Agent: %v", err)
		return
	}
	reader := bufio.NewReader(conn)
	line, err := reader.ReadString('\n')
	if err != nil {
		log.Printf("Error reading 1Agent connection:%v", err)
		return
	}
	fmt.Println(line) // Tag returned from 1Agent
}
