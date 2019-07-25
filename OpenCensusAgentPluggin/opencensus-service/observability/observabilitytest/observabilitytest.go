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

package observabilitytest

import (
	"fmt"
	"reflect"
	"sort"

	"go.opencensus.io/stats/view"
	"go.opencensus.io/tag"

	"github.com/census-instrumentation/opencensus-service/observability"
)

// SetupRecordedMetricsTest does setup the testing environment to check the metrics recorded by receivers, producers or exporters.
// The returned function should be deferred.
func SetupRecordedMetricsTest() (doneFn func()) {
	// Register views
	view.Register(observability.AllViews...)

	return func() {
		view.Unregister(observability.AllViews...)
	}
}

// CheckValueViewExporterReceivedSpans checks that for the current exported value in the ViewExporterReceivedSpans
// for {TagKeyReceiver: receiverName, TagKeyExporter: exporterTagName} is equal to "value".
// When this function is called it is required to also call SetupRecordedMetricsTest as first thing.
func CheckValueViewExporterReceivedSpans(receiverName string, exporterTagName string, value int) error {
	return checkValueForView(observability.ViewExporterReceivedSpans.Name,
		wantsTagsForExporterView(receiverName, exporterTagName), int64(value))
}

// CheckValueViewExporterDroppedSpans checks that for the current exported value in the ViewExporterDroppedSpans
// for {TagKeyReceiver: receiverName} is equal to "value".
// In tests that this function is called it is required to also call SetupRecordedMetricsTest as first thing.
func CheckValueViewExporterDroppedSpans(receiverName string, exporterTagName string, value int) error {
	return checkValueForView(observability.ViewExporterDroppedSpans.Name,
		wantsTagsForExporterView(receiverName, exporterTagName), int64(value))
}

// CheckValueViewReceiverReceivedSpans checks that for the current exported value in the ViewReceiverReceivedSpans
// for {TagKeyReceiver: receiverName, TagKeyExporter: exporterTagName} is equal to "value".
// In tests that this function is called it is required to also call SetupRecordedMetricsTest as first thing.
func CheckValueViewReceiverReceivedSpans(receiverName string, value int) error {
	return checkValueForView(observability.ViewReceiverReceivedSpans.Name,
		wantsTagsForReceiverView(receiverName), int64(value))
}

// CheckValueViewReceiverDroppedSpans checks that for the current exported value in the ViewReceiverDroppedSpans
// for {TagKeyReceiver: receiverName} is equal to "value".
// In tests that this function is called it is required to also call SetupRecordedMetricsTest as first thing.
func CheckValueViewReceiverDroppedSpans(receiverName string, value int) error {
	return checkValueForView(observability.ViewReceiverDroppedSpans.Name,
		wantsTagsForReceiverView(receiverName), int64(value))
}

func checkValueForView(vName string, wantTags []tag.Tag, value int64) error {
	// Make sure the tags slice is sorted by tag keys.
	sortTags(wantTags)

	rows, err := view.RetrieveData(vName)
	if err != nil {
		return fmt.Errorf("Error retrieving view data for view Name %s", vName)
	}

	for _, row := range rows {
		// Make sure the tags slice is sorted by tag keys.
		sortTags(row.Tags)
		if reflect.DeepEqual(wantTags, row.Tags) {
			sum := row.Data.(*view.SumData)
			if float64(value) != sum.Value {
				return fmt.Errorf("Different recorded value: want %v got %v", float64(value), sum.Value)
			}
			// We found the result
			return nil
		}
	}
	return fmt.Errorf("Could not find wantTags: %s in rows %v", wantTags, rows)
}

func wantsTagsForExporterView(receiverName string, exporterTagName string) []tag.Tag {
	return []tag.Tag{
		{Key: observability.TagKeyReceiver, Value: receiverName},
		{Key: observability.TagKeyExporter, Value: exporterTagName},
	}
}

func wantsTagsForReceiverView(receiverName string) []tag.Tag {
	return []tag.Tag{
		{Key: observability.TagKeyReceiver, Value: receiverName},
	}
}

func sortTags(tags []tag.Tag) {
	sort.SliceStable(tags, func(i, j int) bool {
		return tags[i].Key.Name() < tags[j].Key.Name()
	})
}
