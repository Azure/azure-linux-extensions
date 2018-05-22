// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "OmiTask.hh"
#include "OMIQuery.hh"
#include "Batch.hh"
#include "Logger.hh"
#include "Trace.hh"
#include "SchemaCache.hh"
#include <cpprest/pplx/threadpool.h>

class MdsdConfig;

std::map<std::string, SchemaCache::IdType> OmiTask::_qryToSchemaId;

OmiTask::OmiTask(MdsdConfig *config, const MdsEntityName &target, Priority prio,
		 const std::string& nmspc, const std::string& qry, time_t sampleRate)
	: _config(config), _target(target), _priority(prio), _namespace(nmspc), _query(qry),
	  _sampleRate(sampleRate?sampleRate:prio.Duration()), _retryCount(0), _timer(crossplat::threadpool::shared_instance().service()),
	  _cancelled(false), _omiConn(nullptr), _head(nullptr), _tail(nullptr)
{
	Trace trace(Trace::OMIIngest, "OmiTask Constructor");

	if (nmspc.empty() || qry.empty()) {
		throw std::invalid_argument("Missing at least one required attribute (omiNamespace, cqlQuery)");
	}

	// Allocated a schemaId for this namespace+query, if necessary
	std::string mapkey = _namespace + _query;
	if (0 == _qryToSchemaId.count(mapkey)) {	// Not found - insert
		_qryToSchemaId[mapkey] = SchemaCache::Get().GetId();
	}
}

OmiTask::~OmiTask()
{
	// Cleanup the query object
	if (_omiConn != nullptr) {
		delete _omiConn;
	}

	// Cleanup the processing pipeline for query results. Cleanup is recursive; each stage
	// deletes its successor before completing its own cleanup.
	if (_head) {
		delete _head;
		_head = nullptr;
	}
}

SchemaCache::IdType
OmiTask::SchemaId(const std::string & ns, const std::string & qry)
{
	const auto & iter = _qryToSchemaId.find(ns+qry);
	if (iter == _qryToSchemaId.end()) {
		return 0;	// Not found
	} else {
		return iter->second;
	}
}

void
OmiTask::AddStage(PipeStage *stage)
{
	Trace trace(Trace::QueryPipe, "OmiTask::AddStage");

	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << "OmiTask " << this << " adding stage " << stage->Name();
		trace.NOTE(msg.str());
	}
	if (! _tail) {
		// This is the first stage in the pipeline; set the head to point here
		_head = stage;
	} else {
		// There's already a pipeline; make the old tail point to the newly-added stage
		_tail->AddSuccessor(stage);
	}
	// Either way, we have a new tail in the pipeline
	_tail = stage;
}

void
OmiTask::Start()
{
	using namespace boost::posix_time;

	Trace trace(Trace::OMIIngest, "OmiTask::Start");

	trace.NOTE(_query);
	if (!_head) {
		Logger::LogError("No processing pipeline for event; should never happen");
		return;
	}

	// The OMIQuery object does all the retrieval work
	try {
		_omiConn = new OMIQuery(_head, _namespace, _query, true);
	} catch (const std::exception& ex) {
		std::ostringstream msg;
		msg << "Query task (" << _query << ") not started because OMIQuery creation failed: " << ex.what();
		Logger::LogError(msg.str());
		return;
	}

	_firstTimeTaskStartTried.Touch();
	TryToStartAndRetryIfFailed(boost::system::error_code());
}

void
OmiTask::TryToStartAndRetryIfFailed(const boost::system::error_code& error)
{
	using namespace boost::posix_time;

	Trace trace(Trace::OMIIngest, "OmiTask::TryToStartAndRetryIfFailed");

	if (error == boost::asio::error::operation_aborted) {
		// Same comments as in OmiTask::DoWork() applies here as well.
		trace.NOTE("Timer cancelled");
		return;
	}

	if (_omiConn->NoOp()) {
		// Add some randomness to when we start regular queries
		MdsTime target { MdsTime::Now() + MdsTime(2 + random()%5, random()%1000000) };
		_qibase = target.Round(_sampleRate);
		_nextTime = target.to_ptime();
		_timer.expires_at(_nextTime);
		_timer.async_wait(boost::bind(&OmiTask::DoWork, this, boost::asio::placeholders::error));
		if (_retryCount > 0) {
			Logger::LogInfo("Query task(" + _query + ") started after " + std::to_string(_retryCount) + " retries");
		}
		return;
	}

	// OMI noop query failed
	const time_t maxRetryTimeSec = 30 * 60; // Retry up to 30 minutes
	if (MdsTime::Now() > _firstTimeTaskStartTried + maxRetryTimeSec) {
	    Logger::LogError(std::string("Can't connect to OMI server for more than ")
	                    .append(std::to_string(maxRetryTimeSec / 60)).append(" minutes. Giving up."));
	    return;
	}

    // Keep retrying yet with exponential back-off delays
    const time_t retryIntervalSec = 10 * (1 << _retryCount); // Exponential back-off delay (starting from 10 seconds)
    trace.NOTE(std::string("OMIQuery::NoOp() basic query failed. Will try to start the task again in ")
                .append(std::to_string(retryIntervalSec)).append(" seconds."));
    Logger::LogError("Connection to OMI server failed; query task (" + _query + ") not started. Will try to start the task again in "
            + std::to_string(retryIntervalSec) + " seconds.");
    _timer.expires_from_now(boost::posix_time::seconds(retryIntervalSec));
    _timer.async_wait(boost::bind(&OmiTask::TryToStartAndRetryIfFailed, this, boost::asio::placeholders::error));
    _retryCount++;
}

void
OmiTask::Cancel()
{
	Trace trace(Trace::OMIIngest, "OmiTask::Cancel");
	std::lock_guard<std::mutex> lock(_mutex);
	_cancelled = true;
	_timer.cancel();
}

void
OmiTask::DoWork(const boost::system::error_code& error)
{
	Trace trace(Trace::OMIIngest, "OmiTask::DoWork");
	if (error == boost::asio::error::operation_aborted) {
		// If the timer was cancelled, we have to assume the entire configuration may have been
		// deleted; don't touch it. When an MdsdConfig object is told to self-destruct, it first
		// cancels all timer-driven actions, then it waits some period of time, then it actually
		// deletes the object. When the timers are cancelled, the handlers are called with the
		// cancellation message. The MdsdConfig object is *probably* still valid, and as long
		// as the timer isn't rescheduled, all should be well. But I'm playing it safe here
		// and assuming an explicit cancel operation means "the config is gone".
		//
		// Of course, if the MdsdConfig is deleted, all the associated objects, including this
		// very OmiTask object, get deleted as well. Thus, the "don't touch nothin'" rule.
		trace.NOTE("Timer cancelled");
		return;
	}

	// Note that, as written, we do NOT hold the lock here; our use of the class instance
	// needs to be readonly. If that changes, revisit this locking pattern.
	_omiConn->RunQuery(_qibase);
	trace.NOTE("Back from RunQuery");

	std::lock_guard<std::mutex> lock(_mutex);
	if (error || _cancelled) {
		return;
	}
	trace.NOTE("Rescheduling " + _query);
	_qibase += MdsTime(_sampleRate);
	_nextTime = _nextTime + boost::posix_time::seconds(_sampleRate);
	_timer.expires_at(_nextTime);
	_timer.async_wait(boost::bind(&OmiTask::DoWork, this, boost::asio::placeholders::error));
}

// vim: se sw=8 :
