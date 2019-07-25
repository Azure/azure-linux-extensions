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

package addattributesprocessor

import (
	"path"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/census-instrumentation/opencensus-service/internal/configmodels"
	"github.com/census-instrumentation/opencensus-service/internal/configv2"
	"github.com/census-instrumentation/opencensus-service/internal/factories"
)

var _ = configv2.RegisterTestFactories()

func TestLoadConfig(t *testing.T) {

	factory := factories.GetProcessorFactory(typeStr)

	config, err := configv2.LoadConfigFile(t, path.Join(".", "testdata", "config.yaml"))

	require.Nil(t, err)
	require.NotNil(t, config)

	p0 := config.Processors["attributes"]
	assert.Equal(t, p0, factory.CreateDefaultConfig())

	p1 := config.Processors["attributes/2"]
	assert.Equal(t, p1,
		&ConfigV2{
			ProcessorSettings: configmodels.ProcessorSettings{
				TypeVal: "attributes",
			},
			Values: map[string]interface{}{
				"attribute1":         123,
				"string attribute":   "string value",
				"attribute.with.dot": "another value",
			},
		})
}
