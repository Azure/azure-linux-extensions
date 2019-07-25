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

package opencensusexporter

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
	factory := factories.GetExporterFactory(typeStr)

	config, err := configv2.LoadConfigFile(t, path.Join(".", "testdata", "config.yaml"))

	require.NoError(t, err)
	require.NotNil(t, config)

	e0 := config.Exporters["opencensus"]
	assert.Equal(t, e0, factory.CreateDefaultConfig())

	e1 := config.Exporters["opencensus/2"]
	assert.Equal(t, e1,
		&ConfigV2{
			ExporterSettings: configmodels.ExporterSettings{
				NameVal: "opencensus/2",
				TypeVal: "opencensus",
				Enabled: true,
			},
			Headers: map[string]string{
				"can you have a . here?": "F0000000-0000-0000-0000-000000000000",
				"header1":                "234",
				"another":                "somevalue",
			},
			Endpoint:          "1.2.3.4:1234",
			Compression:       "on",
			NumWorkers:        123,
			CertPemFile:       "/var/lib/mycert.pem",
			UseSecure:         true,
			ReconnectionDelay: 15,
			KeepaliveParameters: &keepaliveConfig{
				Time:                20,
				PermitWithoutStream: true,
				Timeout:             30,
			},
		})
}
