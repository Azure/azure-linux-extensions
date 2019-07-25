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

package internal

import (
	"context"
	"errors"
	"github.com/census-instrumentation/opencensus-service/consumer"
	"github.com/prometheus/prometheus/pkg/labels"
	"github.com/prometheus/prometheus/scrape"
	"github.com/prometheus/prometheus/storage"
	"go.uber.org/zap"
	"io"
	"sync"
	"sync/atomic"
)

const (
	runningStateInit = iota
	runningStateReady
	runningStateStop
)

var idSeq int64
var errAlreadyStop = errors.New("ocaStore already stopped")

// OcaStore is an interface combines io.Closer and prometheus' scrape.Appendable
type OcaStore interface {
	scrape.Appendable
	io.Closer
	SetScrapeManager(*scrape.Manager)
}

// OpenCensus Store for prometheus
type ocaStore struct {
	running int32
	logger  *zap.SugaredLogger
	sink    consumer.MetricsConsumer
	mc      *mService
	once    *sync.Once
	ctx     context.Context
}

// NewOcaStore returns an ocaStore instance, which can be acted as prometheus' scrape.Appendable
func NewOcaStore(ctx context.Context, sink consumer.MetricsConsumer, logger *zap.SugaredLogger) OcaStore {
	return &ocaStore{
		running: runningStateInit,
		ctx:     ctx,
		sink:    sink,
		logger:  logger,
		once:    &sync.Once{},
	}
}

// SetScrapeManager is used to config the underlying scrape.Manager as it's needed for OcaStore, otherwise OcaStore
// cannot accept any Appender() request
func (o *ocaStore) SetScrapeManager(scrapeManager *scrape.Manager) {
	if scrapeManager != nil && atomic.CompareAndSwapInt32(&o.running, runningStateInit, runningStateReady) {
		o.mc = &mService{scrapeManager}
	}
}

func (o *ocaStore) Appender() (storage.Appender, error) {
	state := atomic.LoadInt32(&o.running)
	if state == runningStateReady {
		return newTransaction(o.ctx, o.mc, o.sink, o.logger), nil
	} else if state == runningStateInit {
		return nil, errors.New("ScrapeManager is not set")
	}
	// instead of returning an error, return a dummy appender instead, otherwise it can trigger panic
	return noopAppender(true), nil
}

func (o *ocaStore) Close() error {
	atomic.CompareAndSwapInt32(&o.running, runningStateReady, runningStateStop)
	return nil
}

// noopAppender, always return error on any operations
type noopAppender bool

func (noopAppender) Add(l labels.Labels, t int64, v float64) (uint64, error) {
	return 0, errAlreadyStop
}

func (noopAppender) AddFast(l labels.Labels, ref uint64, t int64, v float64) error {
	return errAlreadyStop
}

func (noopAppender) Commit() error {
	return errAlreadyStop
}

func (noopAppender) Rollback() error {
	return errAlreadyStop
}

var _ storage.Appender = noopAppender(true)
