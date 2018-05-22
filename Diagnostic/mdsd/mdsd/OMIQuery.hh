// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _OMIQUERY_HH_
#define _OMIQUERY_HH_

#include "MI.h"
#include "omiclient/client.h"
#include "Logger.hh"
#include "MdsEntityName.hh"
#include "Pipeline.hh"
#include "SchemaCache.hh"
#include <string>
#include <vector>
#include <utility>
#include <unordered_map>
#include <memory>
#include <mutex>

class MdsdConfig;
class MdsValue;
class CanonicalEntity;
class Credentials;
class Batch;

/*
	OMIQuery provides the APIs to query OMI providers (example: SCX) and upload the results to MDS.
	Example usage:
		OMIQuery* q = new OMIQuery(parameters);
		bool isOK1 = q.RunQuery(...) // query 1
		bool isOK2 = q.RunQuery(...) // query 2

	To run in multi-threading mode, create multiple OMIQuery objects.

*/

typedef std::vector<std::pair<std::string,std::string>> omi_schemalist_t;
typedef std::unordered_map<std::string, MdsValue*> omi_datatable_t;

class OMIQuery
{
public:
	// Create an OMIQuery object. If uploadData is true, the data will be
	// uploaded to MDS azure tables. if uploadData is false, data won't be uploaded.	
	OMIQuery(PipeStage * head, const std::string& name_space, const std::string& queryexpr, bool uploadData = true);

	// Release OMI server connection resources
	~OMIQuery();

	// disable copy and move contructors
	OMIQuery(OMIQuery&& h) = delete;
	OMIQuery& operator=(OMIQuery&& h) = delete;

	OMIQuery(const OMIQuery&) = delete;
	OMIQuery& operator=(const OMIQuery &) = delete;

	// Run a noop query. This can be used to test the connection to server.
	// Return true if success; return false for any failure.
	bool NoOp();

	// Run an OMI query in given namespace with given query expression.
	// Example: name_space = "root/scx", queryexpr = "select Name from SCX_UnixProcess"
	// Return true if success; return false for any failure.
	// Puts the results into CanonicalEntity objects, which it passes to the head of
	// the processing pipeline (_pipehead).
	bool RunQuery(const MdsTime&);

	// Set the connection timeout value in milliSeconds.
	void SetConnTimeout(unsigned int milliSeconds);

	// Enable/disable uploading of data to MDS
	void EnableUpload(bool flag) { _uploadData = flag; }

private:
	void LogError(const std::string &msg) const { Logger::LogError(msg); }

	std::unique_ptr<mi::Client>  CreateNewClient();

	// Given an OMI instance, add its columns to a CanonicalEntity. The function will
	// recursively add the columns of any instances or references included within the instance.
	bool PopulateEntity(CanonicalEntity *, const mi::DInstance&);

	std::string GetClassNameFromQuery(const std::string& queryexpr) const;
	std::string Result_ToString(MI_Result result) const;

	// The top stage of the processing pipeline. All information about the ultimate destination
	// of each OMI record we capture is embedded in the various stages of the pipeline, which was
	// constructed when the config file was loaded.
	PipeStage * _pipeHead;

 	std::string _name_space;	// OMI namespace
 	std::string _queryexpr;		// OMI query (written in CQL)
	std::string _classname;		// Name of the OMI class from which the query pulls data

 	bool _uploadData;		// If false, run query but don't upload data. Good for testing query itself.
	unsigned int _connTimeoutMS;	// timeout in milli-seconds to connect to OMI server for queries.

	SchemaCache::IdType _schemaId;	// Identifies the schema for this query

	// Because same queries are going to be run again and again, use cache to save the schemas.
	// key=querynamespace+queryexpr; value: bool. If the query exists in the table, the
	// schema shouldn't be uploaded any long.

	std::mutex tablemutex;
	std::mutex enginemutex;

	const char * SCX_SOCKET_KEY = "socketfile";
	const char * SCX_SOCKET_VAL = "/var/opt/omi/run/omiserver.sock";
	const char * QUERYLANG = "CQL";
};

#endif

// vim: se sw=8:
