// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <boost/bind.hpp>
#include <boost/date_time/posix_time/posix_time_types.hpp>
#include "MdsdConfig.hh"
#include "CfgCtxRoot.hh"
#include "ConfigParser.hh"
#include "TableSchema.hh"
#include "Subscription.hh"
#include "Batch.hh"
#include "Credentials.hh"
#include "OmiTask.hh"
#include "MdsdExtension.hh"
#include "ITask.hh"
#include "Crypto.hh"
#include "Logger.hh"
#include "Utility.hh"
#include "Trace.hh"
#include "EventHubCmd.hh"
#include "ConfigUpdateCmd.hh"
#include "CmdXmlCommon.hh"
#include "EventHubUploaderId.hh"
#include "EventHubUploaderMgr.hh"
#include "EventHubType.hh"
#include "EventPubCfg.hh"
#include "MdsdEventCfg.hh"
#include "LocalSink.hh"
#include "EventType.hh"

#include <fstream>
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <iterator>
#include <vector>
#include <utility>
#include <ctime>
#include <cpprest/pplx/threadpool.h>

extern "C" {
#include <unistd.h>
}

using std::string;
using std::vector;
using std::pair;
using std::make_pair;

// The set of batches that aren't associated with any particular config instance. (Thus the
// nullptr initializer.)
//
// This global static could be associated with the BatchSet class just as easily as the
// MdsdConfig class.
BatchSet MdsdConfig::_localBatches { nullptr };

MdsdConfig::MdsdConfig(string path, string autokeyConfigPath) :
    configFilePath(path),
    _autokeyConfigFilePath(autokeyConfigPath),
    eventVersion(1), _isUseful(false),
	_defaultCreds(nullptr), _batchSet(this), _batchFlushTimer(crossplat::threadpool::shared_instance().service()),
	_agentIdentity(MdsdUtil::GetHostname()),
	_autoKeyReloadTimer(crossplat::threadpool::shared_instance().service()), _monitoringManagementSeen(false),
	_hasAutoKey(false),
	_mdsdEventCfg(std::make_shared<mdsd::MdsdEventCfg>()),
	_eventPubCfg(std::make_shared<mdsd::EventPubCfg>(_mdsdEventCfg))
{
	LoadFromConfigFile(path);
}

void
MdsdConfig::Initialize()
{
	Trace trace(Trace::ConfigLoad, "MdsdConfig Initialize");

	InitEventHubPub();

	FlushBatches(boost::system::error_code());		// Also schedules the next flush
}

// No autokey support.
bool
MdsdConfig::LoadAutokey(const boost::system::error_code &e)
{
	Trace trace(Trace::Credentials, "LoadAutoKey");

	return false;
}

// there could be multiple monikers pointing to different storage accounts
// pair: first=moniker, second=container SAS
std::vector<std::pair<std::string, std::string>>
MdsdConfig::ExtractCmdContainerAutoKeys()
{
	Trace trace(Trace::Credentials, "GetContainerCred");
	auto rootContainer = mdsd::CmdXmlCommon::GetRootContainerName();
	std::vector<std::pair<std::string, std::string>> keylist;

	std::unique_lock<std::mutex> lock(_ehMapMutex);
	for (const auto & iter : _autoKeyMap) {
		if (rootContainer == iter.first.second) {
			keylist.push_back(std::make_pair(iter.first.first, iter.second));
		}
	}
	lock.unlock();

	// Get default account to use: either the default credential or the first credential
	Credentials* cred = _defaultCreds;
	if (!cred) {
		cred = credentials.begin()->second;
	}

	if (!cred) {
		TRACEWARN(trace, "No default account is found. No way to do config auto update.");
	}
	else {
		for (const auto & iter : keylist) {
			auto moniker = iter.first;
			if (moniker == cred->Moniker()) {
				cmdContainerSas = iter.second;
				break;
			}
		}
		if (!cmdContainerSas.empty()) {
			TRACEINFO(trace, "Found container SAS to download config command blob: " << cmdContainerSas);
		}
	}

	return keylist;
}

void
MdsdConfig::SetMappedMoniker(
	const EventHubSasInfo_t & ehmap
	)
{
	Trace trace(Trace::Credentials, "SetMappedMoniker");
	for (const auto & ehEntry : ehmap) {
		auto & origMoniker = ehEntry.first;
		auto & itemsMap = ehEntry.second;
		for (const auto & item : (*itemsMap)) {
			auto & eventName = item.first;
			auto & newMoniker = item.second.moniker;
			_mdsdEventCfg->UpdateMoniker(eventName, origMoniker, newMoniker);
		}
	}
}

void
MdsdConfig::LoadEventHubKeys(
	const std::vector<std::pair<std::string, std::string>>& keylist
	)
{
	Trace trace(Trace::Credentials, "LoadEventHubKeys");

	for (const auto & iter : keylist) {
		auto & moniker = iter.first; // this is what's in mdsd.xml
		auto & containerSas = iter.second;

		trace.NOTE("Get EventHub cmd XML for moniker " + moniker + ", containerSas " + containerSas);
		if(!_mdsdEventCfg->IsEventHubEnabled(moniker)) {
			trace.NOTE("Moniker " + moniker + " does not have EventHub");
			continue;
		}
		mdsd::EventHubCmd ehCmd(Namespace(), EventVersion(), containerSas);
		ehCmd.ProcessCmdXml();
		_ehNoticeItemsMap[moniker] = ehCmd.GetNoticeXmlItemsTable();
		_ehPubItemsMap[moniker] = ehCmd.GetPublisherXmlItemsTable();
		trace.NOTE("Successfully get EventHub cmd XML items (that include SAS keys) for moniker " + moniker);
		DumpEventPublisherInfo();
	}

	SetMappedMoniker(_ehNoticeItemsMap);
	SetMappedMoniker(_ehPubItemsMap);
}

mdsd::EhCmdXmlItems
MdsdConfig::GetEventNoticeCmdXmlItems(
	const std::string & moniker,
	const std::string & eventName
	)
{
	Trace trace(Trace::Credentials, "MdsdConfig::GetEventNoticeCmdXmlItems");
	return GetEventHubCmdXmlItems(_ehNoticeItemsMap, moniker, eventName, "EventNotice");
}

mdsd::EhCmdXmlItems
MdsdConfig::GetEventPublishCmdXmlItems(
	const std::string & moniker,
	const std::string & eventName
	)
{
	Trace trace(Trace::Credentials, "MdsdConfig::GetEventPublishCmdXmlItems");
	return GetEventHubCmdXmlItems(_ehPubItemsMap, moniker, eventName, "EventPublish");
}

mdsd::EhCmdXmlItems
MdsdConfig::GetEventHubCmdXmlItems(
	EventHubItemsMap_t& ehmap,
	const std::string & moniker,
	const std::string & eventName,
	const std::string & eventType
	)
{
	Trace trace(Trace::Credentials, "MdsdConfig::GetEventHubCmdXmlItems");
	std::lock_guard<std::mutex> lock(_ehMapMutex);

	auto iter = ehmap.find(moniker);

	if (iter == ehmap.end()) {
		std::ostringstream strm;
		strm << "Failed to find " << eventType << " SAS & endpoint for moniker=" << moniker;
		Logger::LogError(strm.str());
		return mdsd::EhCmdXmlItems();
	}
	auto xmlItemsMap = iter->second;
	auto xmlItemsIter = xmlItemsMap->find(eventName);
	if (xmlItemsIter == xmlItemsMap->end()) {
		std::ostringstream strm;
		strm << "Failed to find " << eventType << " SAS & endpoint for event=" << eventName << " (moniker=" << moniker << ").";
		Logger::LogError(strm.str());
		return mdsd::EhCmdXmlItems();
	}

	TRACEINFO(trace, "Found " << eventType << " (SAS & endpoint) for moniker=" << moniker <<
		", event=" << eventName << ": " << xmlItemsIter->second);
	return xmlItemsIter->second;
}


// Flush the batch set and schedule the next flush. This should be explicitly called
// only once; the method is also the timer-pop handler and thus arranges for itself
// to be called again. The "cancel()" call is a safety measure in case the method is
// called explicitly after loading.
void
MdsdConfig::FlushBatches(const boost::system::error_code &e)
{
	Trace trace(Trace::Scheduler, "MdsdConfig::FlushBatches");

	if (e == boost::asio::error::operation_aborted) {
		trace.NOTE("Timer cancelled");
	} else {
		_batchSet.FlushIfStale();
		_batchFlushTimer.expires_from_now(boost::posix_time::minutes(1));
		_batchFlushTimer.async_wait(boost::bind(&MdsdConfig::FlushBatches, this, boost::asio::placeholders::error));
	}
}

// Stop timers that are not related to scheduled tasks:
// _batchFlushTimer, _autoKeyReloadTimer
void
MdsdConfig::StopAllTimers()
{
	Trace trace(Trace::Scheduler, "MdsdConfig::StopAllTimers");
	_batchFlushTimer.cancel();
	_autoKeyReloadTimer.cancel();
}

MdsdConfig::~MdsdConfig()
{
	Trace trace(Trace::ConfigLoad, "MdsdConfig Destructor");

	StopAllTimers();

	// Configuration load/parse messages
	size_t count = 0;
	for (Message* msgptr : messages) {
		delete msgptr;
		count++;
	}
	trace.NOTE("Removed " + std::to_string(count) + " messages");
	messages.clear();

	// Configured table schemas (distinct from cached MDS-ready forms of those schemas)
	count = 0;
	for (auto iter : schemas) {
		count++;
		std::ostringstream msg;
		msg << "Deleting TableSchema \"" << iter.first << "\" at address " << iter.second;
		trace.NOTE(msg.str());
		delete iter.second;
	}
	trace.NOTE("Removed " + std::to_string(count) + " TableSchemas");
	schemas.clear();

	// Credentials
	count = 0;
	for (auto iter : credentials) {
		count++;
		std::ostringstream msg;
		msg << "Deleting Credentials \"" << iter.first << "\" at address " << iter.second;
		trace.NOTE(msg.str());
		delete iter.second;
	}
	trace.NOTE("Removed " + std::to_string(count) + " Credentials");
	credentials.clear();

	// Event sources
	// Just map source names to TableSchema*, and I've already deleted all the TableSchema objects.
	trace.NOTE("Clearing all source entries");
	sources.clear();

	// OmiTask
	count = 0;
	for (OmiTask* taskptr : _omiTasks) {
		count++;
		std::ostringstream msg;
		msg << "Deleting OmiTask at address " << taskptr;
		trace.NOTE(msg.str());
		taskptr->Cancel();
		delete taskptr;
	}
	trace.NOTE("Removed " + std::to_string(count) + " OmiTask object(s)");
	_omiTasks.clear();

	// ITask
	count = 0;
	for (ITask* taskptr : _tasks) {
		count++;
		std::ostringstream msg;
		msg << "Deleting ITask at address " << taskptr;
		trace.NOTE(msg.str());
		taskptr->cancel();
		delete taskptr;
	}
	trace.NOTE("Removed " + std::to_string(count) + " ITask object(s)");
	_tasks.clear();

	// Mdsd Extensions
	count = 0;
	for (auto & iter : extensions) {
		count++;
		std::ostringstream msg;
		msg << "Deleting MdsdExtension \"" << iter.first << "\" at address " << iter.second;
		trace.NOTE(msg.str());
		delete iter.second;
	}
	trace.NOTE("Removed " + std::to_string(count) + " MdsdExtension");
	extensions.clear();

	// BatchSet() - gets destroyed when this destructor completes
	// No need to flush; the BatchSet destructor will do that

	// Autokey map contains no pointers so it gets cleaned up correctly when this destructor completes
	trace.NOTE("Clearing autokey map");
	_autoKeyMap.clear();

	_defaultCreds = 0;	// Already deleted it while clearing the credentials vector
}

void
MdsdConfig::LoadFromConfigFile(string path)
{
	// Create an appropriate root document context
	CfgCtxRoot root(this);
	// Instantiate a new parser with the context
	ConfigParser parser(&root, this);

	// Open the path
	std::ifstream infile(path);
	if (!infile) {
		AddMessage(error, "Failed to open config file " + path + " for reading");
		return;
	}

	// Remember where we were when we were asked to load this file
	string previousPath(currentPath);
	long previousLine(currentLine);
	currentPath = path;
	currentLine = 0;

	// Read one line at a time, hand it to the parser's parse_chunk() method
	string line;
	while (std::getline(infile, line)) {
		NextLine();
		parser.ParseChunk(line);
	}
	if (!infile.eof()) {
		if (infile.bad()) {
			AddMessage(error, "Corrupted stream");
		}
		else if (infile.fail()) {
			AddMessage(error, "IO operation failed");
		}
		else {
			AddMessage(error, "std::getline returned 0 for unknown reason");
		}
	}

	currentPath = previousPath;
	currentLine = previousLine;
}

void
MdsdConfig::AddMessage(severity_t s, const std::string& msg)
{
	Message* newmsg = new MdsdConfig::Message(currentPath, currentLine, s, msg);
	messages.push_back(newmsg);
}

bool
MdsdConfig::GotMessages(int mask) const
{
	for (const auto& msg : messages) {
		if (msg->severity & mask) {
			return true;
		}
	}
	return false;
}

void
MdsdConfig::MessagesToStream(std::ostream& output, int mask) const {
	for (const auto& msg : messages) {
		if (msg->severity & mask) {
			output << msg->filename << "(" << msg->line << ") " << SeverityToString(msg->severity)
			       << ": " << msg->msg << "\n";
		}
	}
	output << std::flush;
}

// File scope constants
static const std::string
	_str_fatal = "Fatal",
	_str_error = "Error",
	_str_warning = "Warning",
	_str_info = "Info",
	_str_unknown = "?"
;

const std::string&
MdsdConfig::SeverityToString(MdsdConfig::severity_t severity) const
{
	switch (severity) {
		case MdsdConfig::info:		return _str_info;
		case MdsdConfig::warning:	return _str_warning;
		case MdsdConfig::error:		return _str_error;
		case MdsdConfig::fatal:		return _str_fatal;
		default:			return _str_unknown;		// Should never happen
	}
}

void
MdsdConfig::AddSchema(TableSchema* schema)
{
	if (schemas.count(schema->Name())) {
		AddMessage(error, "Duplicate schema " + schema->Name() + " ignored");
		delete schema;
	}
	else {
		schemas[schema->Name()] = schema;
	}
}

void
MdsdConfig::AddCredentials(Credentials* creds, bool makeDefault)
{
	if (credentials.count(creds->Moniker())) {
		AddMessage(error, "Duplicate creds " + creds->Moniker() + " ignored");
		delete creds;
		return;
	}

	credentials[creds->Moniker()] = creds;
	if (makeDefault) {
		if (_defaultCreds) {
			AddMessage(error, "Cannot make " + creds->Moniker() + " default; another is already set");
		} else {
			_defaultCreds = creds;
		}
	}
}

void
MdsdConfig::AddSource(const string& source, const string& schema)
{
	if (schema.length() > 0 && schemas.count(schema) == 0) {
		AddMessage(error, "Undefined schema " + schema + " referenced");
	}
	else if (sources.count(source)) {
		AddMessage(error, "Source " + source + " already mapped to a schema; ignored");
	}
	else {
		sources[source] = schemas[schema];
	}
}

void
MdsdConfig::AddDynamicSchemaSource(const string& source)
{
	if (_dynamic_sources.count(source)) {
		AddMessage(error, "Dynamic Schema Source " + source + " has already been configured; ignored");
	}
	else
	{
		_dynamic_sources.insert(source);
	}
}

bool
MdsdConfig::AddIdentityColumn(const string& colname, const string& colval)
{
	for (auto iter = identityColumns.begin(); iter != identityColumns.end(); ++iter) {
		if (iter->first == colname) {
			AddMessage(error, "Ignoring duplicate identity column " + colname);
			return false;
		}
	}

	identityColumns.push_back(make_pair(colname, colval));
	return true;
}

void
MdsdConfig::GetIdentityColumnValues(std::back_insert_iterator<vector<pair<string, string> > > destination)
{
	std::copy(identityColumns.begin(), identityColumns.end(), destination);
}

void
MdsdConfig::GetIdentityColumnTypes(std::back_insert_iterator<vector<pair<string, string> > > destination)
{
	for (auto iter = identityColumns.begin(); iter != identityColumns.end(); ++iter) {
		destination = make_pair(iter->first, "mt:wstr");
	}
}

void
MdsdConfig::GetIdentityValues(std::string & tenant, std::string& role, std::string& roleInstance)
{
	ident_vect_t identityColumns;
    GetIdentityColumnValues(std::back_inserter(identityColumns));

	for (const auto & col : identityColumns) {
		if (col.first.compare(TenantAlias()) == 0) {
			tenant = col.second;
		}
		else if (col.first.compare(RoleAlias()) == 0) {
			role = col.second;
		}
		else if (col.first.compare(RoleInstanceAlias()) == 0) {
			roleInstance = col.second;
		}
	}
}

void
MdsdConfig::AddEnvelopeColumn(std::string && name, std::string && value)
{
	for (const EnvelopeColumn & column : _envelopeColumns) {
		if (column.first == name) {
			throw std::runtime_error("Column already in envelope");
		}
	}
	_envelopeColumns.emplace_back(name, value);
}

void
MdsdConfig::ForeachEnvelopeColumn(const std::function<void(const EnvelopeColumn&)>& process)
{
	for (const EnvelopeColumn & column : _envelopeColumns) {
		process(column);
	}
}

TableSchema*
MdsdConfig::GetSchema(const string& source) const
{
	const auto &iter = sources.find(source);
	if (iter == sources.end()) {
		return 0;
	}

	return iter->second;
}

Credentials*
MdsdConfig::GetCredentials(const string& moniker) const
{
	const auto &iter = credentials.find(moniker);
	if (iter == credentials.end()) {
		return 0;
	}

	return iter->second;
}

std::string
MdsdConfig::GetAutokey(const std::string& moniker, const std::string& fullTableName)
{
	std::lock_guard<std::mutex> lock(_aKMmutex);

	auto iter = _autoKeyMap.find(std::make_pair(moniker, fullTableName));
	if (iter == _autoKeyMap.end()) {
		return std::string();
	}
	return iter->second;
}

void
MdsdConfig::DumpAutokeyTable(std::ostream &os)
{
	os << "Dump format: <MonikerName, ItemName>" << std::endl;
	for (const auto & iter : _autoKeyMap) {
		os << "<" << iter.first.first << "," << iter.first.second << ">" << std::endl;
	}
}

bool
MdsdConfig::IsQuotaExceeded(const std::string &name, unsigned long current) const
{
	Trace trace(Trace::ConfigUse, "MdsdConfig:IsQuotaExceeded");

	auto iter = _quotas.find(name);

	if (iter == _quotas.end()) {
		trace.NOTE("Check against unset quota " + name);
		return false;
	}

	return (current > iter->second);
}

void
MdsdConfig::AddOmiTask(OmiTask *task)
{
	// Defer the creation of the batch; autokey data might not yet be loaded.
	// The task will create the batch when an attempt is made to start it
	_omiTasks.push_back(task);
	_isUseful = true;
}

void
MdsdConfig::ForeachOmiTask(const std::function<void(OmiTask*)>& fn)
{
	std::for_each(_omiTasks.begin(), _omiTasks.end(), fn);
}

void
MdsdConfig::AddTask(ITask *task)
{
        Trace trace(Trace::Scheduler, "MdsdConfig::AddTask");
	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << "Adding task " << task;
		trace.NOTE(msg.str());
	}
	_tasks.push_back(task);
	_isUseful = true;
}

void
MdsdConfig::ForeachTask(const std::function<void(ITask*)>& fn)
{
        Trace trace(Trace::Scheduler, "MdsdConfig::ForeachTask");
	trace.NOTE("Invoking function on " + std::to_string(_tasks.size()) + " task(s)");
	std::for_each(_tasks.begin(), _tasks.end(), fn);
}


void
MdsdConfig::AddExtension(MdsdExtension * extension)
{
	Trace trace (Trace::ConfigUse, "MdsdConfig::AddExtension");
	if (!extension) {
		return;
	}

	const std::string& extname = extension->Name();
	if (extensions.count(extname)) {
		AddMessage(error, "Duplicate Extension " + extname + " ignored.");
		delete extension;
		extension = nullptr;
	}
	else {
		extensions[extname] = extension;
		_isUseful = true;
	}
}

void
MdsdConfig::ForeachExtension(const std::function<void(MdsdExtension*)>& fn)
{
	Trace trace (Trace::ConfigUse, "MdsdConfig::ForeachExtension");
	for (const auto & kv : extensions) {
		trace.NOTE("Walking MdsdExtension with name='" + kv.first + "'");
		fn(kv.second);
	}
}


void
MdsdConfig::StartScheduledTasks()
{
        Trace trace(Trace::Scheduler, "MdsdConfig::StartScheduledTasks");
        ForeachOmiTask([](OmiTask *job) { job->Start(); });
        ForeachTask([](ITask *task) { task->start(); });
}

void
MdsdConfig::StopScheduledTasks()
{
        Trace trace(Trace::Scheduler, "MdsdConfig::StopScheduledTasks");
	ForeachOmiTask([](OmiTask *job) { job->Cancel(); });
        ForeachTask([](ITask *task) { task->cancel(); });
}

// Tells this configuration to remove itself in the future. The config takes
// steps immediately to stop generating work for itself, then schedules the
// final cleanup action to take place after the requested delay.
void
MdsdConfig::SelfDestruct(int seconds)
{
	Trace trace(Trace::ConfigUse, "MdsdConfig::SelfDestruct");
	StopScheduledTasks();
	StopAllTimers();

	// Flush any data we're still holding on to. Don't use FlushBatches; that
	// will restart the autoflush timer, and we just stopped that. One last
	// flush will happen when the Destroyer calls delete.
	_batchSet.Flush();

	// Create a deadline_timer on the heap; when it expires, call our Destroyer helper
	auto timer = new boost::asio::deadline_timer(crossplat::threadpool::shared_instance().service());
	timer->expires_from_now(boost::posix_time::seconds(seconds));
	timer->async_wait(boost::bind(MdsdConfig::Destroyer, this, timer));
}

// This static private method does the final delete. Also deletes the heap timer.
void
MdsdConfig::Destroyer(MdsdConfig *config, boost::asio::deadline_timer *timer)
{
	Trace trace(Trace::ConfigUse, "MdsdConfig:Destroyer");

	std::ostringstream msg;
	msg << "Deleting MdsdConfig at " << config;
	trace.NOTE(msg.str());
	delete config;
	delete timer;
}

// Create a batch for a given target. If one has already been created for that target,
// return the one we're already using.
Batch*
MdsdConfig::GetBatch(const MdsEntityName &target, int interval)
{
	if (target.GetStoreType() == StoreType::Local) {
		return _localBatches.GetBatch(target, interval);
	} else {
		return _batchSet.GetBatch(target, interval);
	}
}

bool
MdsdConfig::ValidateConfig(
    bool isStartupConfig
    ) const
{
    Trace trace(Trace::ConfigUse, "MdsdConfig::ValidateConfig");

    if (!IsUseful()) {
        std::ostringstream msg;
        msg << "No productive configuration resulted from loading config file(s): " << configFilePath << ".";
        if (!isStartupConfig) {
            msg << " New configuration ignored.\n";
        }
        msg << "Warnings detected:\n";
        MessagesToStream(msg, MdsdConfig::warning);
        Logger::LogWarn(msg);
    }
    if (GotMessages(MdsdConfig::fatal)) {
        std::ostringstream msg;
        msg << "Fatal errors while loading configuration " << configFilePath << ":" << std::endl;
        MessagesToStream(msg, MdsdConfig::fatal);
        if (!isStartupConfig) {
            msg << "\nNew configuration ignored; using previous configuration";
        }
        Logger::LogError(msg);
        return false;
    }
    if (GotMessages(MdsdConfig::error)) {
        std::ostringstream msg;
        msg << "Config file " << configFilePath << " parsing errors:\n";
        MessagesToStream(msg, MdsdConfig::error);
        Logger::LogError(msg);
        return false;
    }
    if (GotMessages(MdsdConfig::warning)) {
        std::ostringstream msg;
        msg << "Config file " << configFilePath << "parsing warnings:\n";
        MessagesToStream(msg, MdsdConfig::warning);
        Logger::LogWarn(msg);
    }

    return true;
}

void
MdsdConfig::DumpEventPublisherInfo()
{
    Trace trace(Trace::ConfigLoad, "MdsdConfig::DumpEventPublisherInfo");

    if (!trace.IsActive()) {
        return;
    }
    if (_ehPubItemsMap.empty()) {
        TRACEINFO(trace, "EventPublisher map is empty");
    }
    else {
        for (const auto & iter : _ehPubItemsMap) {
            auto moniker = iter.first;
            auto itemsmap = iter.second;
            if (itemsmap->empty()) {
                TRACEINFO(trace, "Moniker='" << moniker << "'; Event: N/A.");
            }
            else {
                for (const auto& item : (*itemsmap)) {
                    auto eventname = item.first;
                    auto ehinfo = item.second;
                    TRACEINFO(trace, "Moniker='" << moniker << "'; EventName='"
                        << eventname << "'; EHInfo: " << ehinfo);
                }
            }
        }
    }
}

std::string
MdsdConfig::GetDefaultMoniker() const
{
	auto defaultCreds = GetDefaultCredentials();
	if (!defaultCreds) {
		throw std::runtime_error("No default credential is found.");
	}
	return defaultCreds->Moniker();
}

void
MdsdConfig::AddMonikerEventInfo(
	const std::string & moniker,
	const std::string & eventName,
	StoreType::Type type,
	const std::string & sourceName,
	mdsd::EventType eventType
	)
{
	Trace trace(Trace::ConfigLoad, "AddMonikerEventInfo");
	try {
		auto monikerToUse = moniker.empty()? GetDefaultMoniker() : moniker;
		_mdsdEventCfg->AddEventSinkCfgInfoItem({eventName, monikerToUse, type, sourceName, eventType });
		TRACEINFO(trace, "Saved event=" << eventName << " moniker=" << monikerToUse);
	}
	catch(const std::exception& ex) {
		AddMessage(fatal, std::string("AddMonikerEventInfo() failed: ") + ex.what());
	}
}

void
MdsdConfig::SetOboDirectPartitionFieldNameValue(std::string&& name, std::string&& value)
{
	_oboDirectPartitionFieldsMap.emplace(name, value);
	if (name == "resourceId") {
	    _resourceId = value;
	}
}


std::string
MdsdConfig::GetOboDirectPartitionFieldValue(const std::string& name) const
{
	if (name.empty()) {
		throw std::invalid_argument("MdsdConfig::GetOboDirectPartitionFieldValue(name): name cannot be empty");
	}

	std::string value;
	auto it = _oboDirectPartitionFieldsMap.find(name);
	if (it != _oboDirectPartitionFieldsMap.end()) {
		value = it->second;
	}
	else {
		Logger::LogWarn("OboDirectPartitionField with name='" + name
				+ "' not found. Make sure the mdsd.xml includes the corresponding "
				"Management/OboDirectPartitionField element. Returning an empty string "
				"as the result value.");
	}

	return value;
}

void
MdsdConfig::ValidateEvents()
{
	Trace trace(Trace::ConfigLoad, "MdsdConfig::ValidateEvents");
	try {
		ValidateAnnotations();
		ValidateEventHubPubKeys();
		ValidateEventHubPubSinks();
	}
	catch(const std::exception & ex) {
		AddMessage(error, std::string("MdsdConfig::ValidateEvents() failed: ") + ex.what());
	}
}

void
MdsdConfig::ValidateAnnotations()
{
	for (const auto & name : _mdsdEventCfg->GetInvalidAnnotations()) {
		AddMessage(MdsdConfig::error, "Unknown name '" + name + "' in EventStreamingAnnotation");
	}
}

void
MdsdConfig::ValidateEventHubPubKeys()
{
	for (const auto & publisherName : _eventPubCfg->CheckForInconsistencies(_hasAutoKey)) {
		AddMessage(MdsdConfig::error,
			"Failed to find event publisher SAS key for item '" + publisherName + "'");
	}
}

void
MdsdConfig::ValidateEventHubPubSinks()
{
	for (const auto & publisherName: _mdsdEventCfg->GetEventPublishers())
	{
		if (!LocalSink::Lookup(publisherName)) {
			AddMessage(error, "failed to find LocalSink object for Event Publisher " + publisherName);
		} else {
		    _isUseful = true;  // Found a valid event publisher
		}
	}
}

void
MdsdConfig::InitEventHubPub()
{
	Trace trace(Trace::ConfigUse, "MdsdConfig::InitEventHubPub");

	SetEventHubPubForLocalSinks();

	// create uploaders first before setting SAS key
	mdsd::EventHubUploaderMgr::GetInstance().CreateUploaders(mdsd::EventHubType::Publish,
		_eventPubCfg->GetNameMonikers());

	SetupEventHubPubEmbeddedKeys();
}

void
MdsdConfig::SetupEventHubPubEmbeddedKeys()
{
	Trace trace(Trace::ConfigUse, "MdsdConfig::SetupEventHubPubEmbeddedKeys");

	auto& ehUploaderMgr = mdsd::EventHubUploaderMgr::GetInstance();
	auto ehtype = mdsd::EventHubType::Publish;

	for (const auto & item : _eventPubCfg->GetEmbeddedSasData()) {
		auto & publisherName = item.first;
		auto & monikerSasMap = item.second;

		for (const auto & keyItem : monikerSasMap) {
			auto & moniker = keyItem.first;
			auto & saskey = keyItem.second;
			ehUploaderMgr.SetSasAndStart(mdsd::EventHubUploaderId(ehtype, moniker, publisherName), saskey);
		}
	}
}

void
MdsdConfig::SetEventHubPubForLocalSinks()
{
	Trace trace(Trace::ConfigUse, "MdsdConfig::SetEventHubPubForLocalSinks");

	std::string tenant, role, roleInstance;
	GetIdentityValues(tenant, role, roleInstance);

	for (const auto & item : _eventPubCfg->GetNameMonikers()) {
		auto & publisherName = item.first;
		auto sinkObj = LocalSink::Lookup(publisherName);

		if (!sinkObj) {
			throw std::runtime_error("SetEventHubPubForLocalSinks(): failed to find LocalSink object for "
				+ publisherName);
		}
		else {
			std::string duration = GetDurationForEventName(publisherName);
			auto & monikers = item.second;
			sinkObj->SetEventPublishInfo(monikers, std::move(duration), tenant, role, roleInstance);
		}
	}
}

// vim: sw=8
