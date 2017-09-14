// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "OMIQuery.hh"
#include "OmiTask.hh"
#include "MdsSchemaMetadata.hh"
#include "MdsValue.hh"
#include "Trace.hh"
#include "Logger.hh"
#include "CanonicalEntity.hh"
#include "Engine.hh"
#include "MdsdConfig.hh"
#include "MdsEntityName.hh"
#include "Credentials.hh"
#include "Batch.hh"
#include "Utility.hh"

#include <iostream>
#include <algorithm>
#include <unordered_map>

#include <unistd.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <sys/stat.h>
#include <cctype>

extern "C" {
#include <sys/time.h>
}

using std::vector;
using std::pair;

OMIQuery::OMIQuery(PipeStage *head, const std::string& ns, const std::string& qry, bool doUpload)
	: _pipeHead(head), _name_space(ns), _queryexpr(qry), _uploadData(doUpload), _connTimeoutMS(90000)
{
	Trace trace(Trace::OMIIngest, "OMIQuery::Constructor");

        if (MdsdUtil::NotValidName(_name_space)) {
                throw std::invalid_argument("OMIQuery namespace must not be empty");
        } else if (MdsdUtil::IsEmptyOrWhiteSpace(_queryexpr)) {
                throw std::invalid_argument("OMIQuery query expression must not be empty");
	}

	const std::string from = "from";
	const std::string& whitespace = " \t";
	std::string queryLower = _queryexpr;
	std::transform(queryLower.begin(), queryLower.end(), queryLower.begin(), ::tolower);

	size_t frompos = queryLower.find(from);
	if (std::string::npos == frompos) {
		throw std::invalid_argument("Invalid syntax in OMI query expression (invalid class name specification)");
	}

	std::string substr1 = _queryexpr.substr(frompos + from.length());
	auto strBegin = substr1.find_first_not_of(whitespace);
	if (std::string::npos == strBegin) {
		throw std::invalid_argument("Invalid syntax in OMI query expression (invalid class name specification)");
	}
	auto strEnd = substr1.find_first_of(whitespace, strBegin);
	_classname = substr1.substr(strBegin, strEnd-strBegin);
        if (MdsdUtil::NotValidName(_classname)) {
                throw std::invalid_argument("OMIQuery class must not be empty");
        }

	_schemaId = OmiTask::SchemaId(ns, qry);
	if (0 == _schemaId) {
		throw std::invalid_argument("No schemaID has been allocated for this namespace and query");
	}

	trace.NOTE("Query namespace(" + _name_space + ") class(" + _classname + ") queryexp(" + _queryexpr + ")");
}

OMIQuery::~OMIQuery()
{
	Trace trace(Trace::OMIIngest, "OMIQuery::Destructor");

	// Leave the processing pipeline alone; the OmiTask will have cleaned it up.
}

void OMIQuery::SetConnTimeout(unsigned int milliSeconds)
{
    Trace trace(Trace::OMIIngest, "OMIQuery::SetConnTimeout");
	_connTimeoutMS = milliSeconds;
    trace.NOTE("Set OMI connection timeout(MS)=" + std::to_string(_connTimeoutMS));
}

std::unique_ptr<mi::Client> OMIQuery::CreateNewClient()
{
	Trace trace(Trace::OMIIngest, "OMIQuery::CreateNewClient");
	bool resultOk = true;
	std::unique_ptr<mi::Client> client;	// Points to nothing
	try {
		client.reset(new mi::Client());	// Make it own the newly allocated object
		mi::String locator = SCX_SOCKET_VAL;
		if (trace.IsActive()) {
			std::ostringstream msg;
			msg << "locator='" << locator.Str() << "'; Timeout(MS)=" << _connTimeoutMS;
			trace.NOTE(msg.str());
		}
		resultOk = client->Connect(locator, "", "", _connTimeoutMS*1000);
		if (!resultOk) {
		    LogError("Error: Unable to connect to OMI service. (Is OMI installed and started?)");
		    client.reset();
		}
	}
	catch(...)
	{
		LogError("Error: Exception thrown while connecting to OMI service. (Is OMI functional?)");
		client.reset();	// Deletes what it pointed to, if anythinq
		resultOk = false;
	}
	trace.NOTE("ResultStatus=" + std::to_string(resultOk));
	return client;
}

bool OMIQuery::NoOp()
{
    Trace trace(Trace::OMIIngest, "OMIQuery::NoOp");
    bool resultOK = true;

    try 
    {
        auto client = CreateNewClient();
        if (client) {
            resultOK = client->NoOp(_connTimeoutMS*1000);
            if (!resultOK) {
                LogError("Error: OMI NoOp() failed. Is OMI functional?");
            }
            else {
                trace.NOTE("NoOp finished Successfully.");
            }
            client->Disconnect();
        }
        else {
            resultOK = false;
        }
    }
    catch(...)
    {
        LogError("Error: Exception thrown while performing OMI NoOp" );
        resultOK = false;
    }

    return resultOK;
}

// Execute the query; put the results in CanonicalEntity instances and
// pass them into the processing pipeline associated with this query.
bool OMIQuery::RunQuery(const MdsTime& qibase)
{	
	Trace trace(Trace::OMIIngest, "OMIQuery::RunQuery");
	trace.NOTE("\nrun query: " + _name_space + " : " +  _queryexpr);

	bool resultOK = true;
	MdsTime queryTime;	// Default constructor sets this to the current time
	mi::Array<mi::DInstance> instanceList;
	mi::Result result = MI_RESULT_OK;
	try {
		auto client = CreateNewClient();
		if (! client) {
			return false;
		}

		resultOK = client->EnumerateInstances(_name_space.c_str(), _classname.c_str(), true, _connTimeoutMS*1000, 
			    instanceList, QUERYLANG, _queryexpr.c_str(), result);
		if (!resultOK || (result != MI_RESULT_OK)) {
			LogError("Error: OMI EnumerateInstances failed");
			resultOK = false;
		}
		client->Disconnect();
	}
	catch(const std::exception& e)
	{
		resultOK = false;
		LogError("Error: OMI RunQuery() unexpected exception: " + std::string(e.what()));
	}
	catch(...)
	{
		resultOK = false;
		LogError(std::string("Error: OMI RunQuery() unexpected exception:"));
	}

	if (resultOK) {
		MI_Uint32 count = instanceList.GetSize();
		trace.NOTE("Found instances count=" + std::to_string(count));
		_pipeHead->Start(qibase);
		for (MI_Uint32 i = 0; i < count; i++)
		{
			CanonicalEntity * ce = new CanonicalEntity(instanceList[i].Count());
			resultOK = PopulateEntity(ce, instanceList[i]);
			if (resultOK) {
				// Suppress a CanonicalEntity with zero columns; could happen, means
				// nothing is wrong, just no data
				if (ce->size()) {
					ce->SetPreciseTime(queryTime);
					ce->SetSchemaId(_schemaId);
					_pipeHead->Process(ce);
				} else {
					delete ce;
				}
			} else {
				Logger::LogWarn("Problem(s) detected with this OMI instance; dropping it");
				delete ce;
			}
		}
		_pipeHead->Done();
	}

	trace.NOTE("RunQuery finished with resultOK=" + std::to_string(resultOK));

	return resultOK;
}

bool
OMIQuery::PopulateEntity(CanonicalEntity *ce, const mi::DInstance& item)
{
	Trace trace(Trace::OMIIngest, "OMIQuery::PopulateEntity");
	mi::Uint32 count = item.Count();
	trace.NOTE("Instance has #items=" + std::to_string(count));

	try {
	for (mi::Uint32 i = 0; i < count; i++) {
		mi::String name;
		if (!item.GetName(i, name)) {
			LogError("While processing OMI results, failed to get name of column " + std::to_string(i));
			return false;
		}
		std::string namestr (name.Str());

                mi::Type type;
                MI_Value value;
                bool isNull = false;
                bool isKey = false;

                if (!item.GetValue(name, &value, type, isNull, isKey)) {
                        LogError("While processing OMI results, failed to get value for column " + std::to_string(i));
                        return false;
                }

		if (isNull) {
			ce->AddColumn(namestr, "[NULL]");
			if (trace.IsActive()) {
				std::ostringstream msg;
				msg << "Item[" << i << "]: " << namestr << " (OMI type " << type << ") is NULL";
				trace.NOTE(msg.str());
			}
		} else if (type == MI_INSTANCE || type == MI_REFERENCE) {
			trace.NOTE("Item[" + std::to_string(i) + "] is an Instance/Reference");
			mi::DInstance subitem;
			bool resultOK;
			if (type == MI_INSTANCE) {
				resultOK = item.GetInstance(name, subitem);
			} else {
				resultOK = item.GetReference(name, subitem);
			}
			resultOK = resultOK && PopulateEntity(ce, subitem);
			if (!resultOK) {
				LogError("While processing OMI results, failed to unpack instance/reference");
				return false;
			}
		} else {
			std::ostringstream msg;
			bool resultOK = true;
			msg << "Item[" << i << "]: " << namestr << " (MI_Type " << type << ")";
			try {
				MdsValue * mdsvalue = new MdsValue { value, type };
				ce->AddColumn(namestr, mdsvalue);
				msg << " " << mdsvalue->TypeToString() << " " << *mdsvalue;
			}
			catch (std::exception & e) {
				resultOK = false;
				msg << " failed type conversion (" << e.what() << ")";
			}
			trace.NOTE(msg.str());
			if (!resultOK)
				return false;
		}
	}
	return true;
	}
	catch (...) {
		LogError("Unknown exception caught in OMIQuery::PopulateEntity");
	}
	return false;
}

namespace std {
template <> struct hash<MI_Result>
{
	size_t operator()(const MI_Result & res) const
	{
		return static_cast<size_t>(res);
	}
};
}

std::string OMIQuery::Result_ToString(MI_Result result) const
{
    static std::unordered_map<MI_Result, const char *> resultCodes = 
    {
        { MI_RESULT_OK, "MI_RESULT_OK" },
        { MI_RESULT_FAILED, "MI_RESULT_FAILED" },
        { MI_RESULT_ACCESS_DENIED, "MI_RESULT_ACCESS_DENIED" },
        { MI_RESULT_INVALID_NAMESPACE, "MI_RESULT_INVALID_NAMESPACE" },
        { MI_RESULT_INVALID_PARAMETER, "MI_RESULT_INVALID_PARAMETER" },
        { MI_RESULT_INVALID_CLASS, "MI_RESULT_INVALID_CLASS" },
        { MI_RESULT_NOT_FOUND, "MI_RESULT_NOT_FOUND" },
        { MI_RESULT_NOT_SUPPORTED, "MI_RESULT_NOT_SUPPORTED" },
        { MI_RESULT_CLASS_HAS_CHILDREN, "MI_RESULT_CLASS_HAS_CHILDREN" },
        { MI_RESULT_CLASS_HAS_INSTANCES, "MI_RESULT_CLASS_HAS_INSTANCES" },
        { MI_RESULT_INVALID_SUPERCLASS, "MI_RESULT_INVALID_SUPERCLASS" },
        { MI_RESULT_ALREADY_EXISTS, "MI_RESULT_ALREADY_EXISTS" },
        { MI_RESULT_NO_SUCH_PROPERTY, "MI_RESULT_NO_SUCH_PROPERTY" },
        { MI_RESULT_TYPE_MISMATCH, "MI_RESULT_TYPE_MISMATCH" },
        { MI_RESULT_QUERY_LANGUAGE_NOT_SUPPORTED, "MI_RESULT_QUERY_LANGUAGE_NOT_SUPPORTED" },
        { MI_RESULT_INVALID_QUERY, "MI_RESULT_INVALID_QUERY" },
        { MI_RESULT_METHOD_NOT_AVAILABLE, "MI_RESULT_METHOD_NOT_AVAILABLE" },
        { MI_RESULT_METHOD_NOT_FOUND, "MI_RESULT_METHOD_NOT_FOUND" },
        { MI_RESULT_NAMESPACE_NOT_EMPTY, "MI_RESULT_NAMESPACE_NOT_EMPTY" },
        { MI_RESULT_INVALID_ENUMERATION_CONTEXT, "MI_RESULT_INVALID_ENUMERATION_CONTEXT" },
        { MI_RESULT_INVALID_OPERATION_TIMEOUT, "MI_RESULT_INVALID_OPERATION_TIMEOUT" },
        { MI_RESULT_PULL_HAS_BEEN_ABANDONED, "MI_RESULT_PULL_HAS_BEEN_ABANDONED" },
        { MI_RESULT_PULL_CANNOT_BE_ABANDONED, "MI_RESULT_PULL_CANNOT_BE_ABANDONED" },
        { MI_RESULT_FILTERED_ENUMERATION_NOT_SUPPORTED, "MI_RESULT_FILTERED_ENUMERATION_NOT_SUPPORTED" },
        { MI_RESULT_CONTINUATION_ON_ERROR_NOT_SUPPORTED, "MI_RESULT_CONTINUATION_ON_ERROR_NOT_SUPPORTED" },
        { MI_RESULT_SERVER_LIMITS_EXCEEDED, "MI_RESULT_SERVER_LIMITS_EXCEEDED" },
        { MI_RESULT_SERVER_IS_SHUTTING_DOWN, "MI_RESULT_SERVER_IS_SHUTTING_DOWN" },
        { MI_RESULT_CANCELED, "MI_RESULT_CANCELED" },
        { MI_RESULT_OPEN_FAILED, "MI_RESULT_OPEN_FAILED" },
        { MI_RESULT_INVALID_CLASS_HIERARCHY, "MI_RESULT_INVALID_CLASS_HIERARCHY" },
        { MI_RESULT_WOULD_BLOCK, "MI_RESULT_WOULD_BLOCK" },
        { MI_RESULT_TIME_OUT, "MI_RESULT_TIME_OUT" }
    };

    auto const & iter = resultCodes.find(result);
    if (iter != resultCodes.end()) {
    	return std::string(iter->second);
    }

    /* Not found! */
    return std::string("MI_ERROR_CODE_") + std::to_string(result);
}

// vim: set sw=8 :
