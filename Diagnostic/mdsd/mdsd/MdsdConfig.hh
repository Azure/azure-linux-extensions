// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#ifndef _MDSDCONFIG_HH_
#define _MDSDCONFIG_HH_

#include "TableSchema.hh"
#include "Batch.hh"
#include "IdentityColumns.hh"
#include "Priority.hh"
#include "EventHubCmd.hh"
#include "CfgEventAnnotationType.hh"
#include <string>
#include <deque>
#include <vector>
#include <map>
#include <unordered_map>
#include <unordered_set>
#include <iterator>
#include <utility>
#include <iostream>
#include <mutex>
#include <stddef.h>
#include <boost/asio.hpp>

class Credentials;
class OmiTask;
class ITask;
class MdsdExtension;

namespace mdsd {
	struct OboDirectConfig;
    class EventPubCfg;
    class MdsdEventCfg;
    enum class EventType;
}

class MdsdConfig
{
public:
	/// <summary>
	/// Create an MdsdConfiguration from a configuration file
	/// </summary>
	/// <param name='path'>Pathname of the config file to load</param>
	MdsdConfig(std::string path, std::string autokeyConfigPath);
	~MdsdConfig();

	/// <summary>
	/// Initialize configuring activities, including loading autokey,
	/// flushing batches etc.
	/// </summary>
	void Initialize();

	/// <summary>
	/// Load a configuration file into an existing MdsdConfiguration
	/// </summary>
	/// <param name='path'>Pathname of the config file to load</param>
	void LoadFromConfigFile(std::string path);


	//////////// Parser Warnings and Errors //////////

	typedef enum { anySeverity=15, info = 8, warning = 4, error = 2, fatal = 1 } severity_t;

	/// <summary>Return the readable name of a severity code</summary>
	/// <param name="severity">The severity code</param>
	const std::string& SeverityToString(severity_t severity) const;

	/// <summary>
	/// Record a message (warning, error, fatal error, etc) for this location in the parse of the file. This
	/// method always adds a newline (\n) to the end of each message.
	/// </summary>
	/// <param name="severity">The severity of the message (e.g. Info, Warning, Error, Fatal, etc.)</param>
	/// <param name="msg">The message to be recorded</param>
	void AddMessage(severity_t severity, const std::string& msg);

	/// <summary>True if messages were recorded via MdsdConfig::AddMessage()</summary>
	bool GotMessages(int mask) const;

	/// <summary>Write all recorded messages to a stream</summary>
	void MessagesToStream(std::ostream& output, int mask) const;

	class Message {
	public:
		Message(const std::string& f, long l, severity_t s, const std::string& m)
			: filename(f), line(l), severity(s), msg(m) {}
		~Message() {}

		std::string filename;
		long line;
		severity_t severity;
		std::string msg;
	};

	///////////// Configuration Settings //////////////

	/// <summary>Indicates if some useful/productive settings have made it into the config</summary>
	bool IsUseful() const { return _isUseful; }

	/// <summary>True if <MonitoringManagement> element has been loaded once</summary>
	bool MonitoringManagementSeen() const { return _monitoringManagementSeen; }
	void MonitoringManagementSeen(bool state) { _monitoringManagementSeen = state; }

	/// <summary>Prefix for all event names.</summary>
	const std::string& Namespace() const { return nameSpace; }
	void Namespace(const std::string& name) { nameSpace = name; }

	/// <summary>Version suffix for event names. "5" yields a suffix of "Ver5v0".</summary>
	int EventVersion() const { return eventVersion; }
	void EventVersion(int ver) { eventVersion = ver; }

	/// <summary>Config file timestamp.</summary>
	const std::string& Timestamp() const { return timeStamp; }
	void Timestamp(const std::string& ts) { timeStamp = ts; }

	/// <summary>Number of partitions to spread across in MDS tables</summary>
	unsigned int PartitionCount() const { return _partitionCount; }
	void PartitionCount(unsigned int count) { _partitionCount = count; }

	/// <summary>How long to keep data in the agent</summary>
	unsigned long DefaultRetention() const { return _defaultRetention; }
	void DefaultRetention(unsigned long count) { _defaultRetention = count; }


	//////////// Identity ///////

	// Add an identity column to the set
	bool AddIdentityColumn(const std::string& colname, const std::string& colval);
	// Push name/value or name/type pairs into destination containers
	void GetIdentityColumnValues(std::back_insert_iterator<ident_vect_t>);
	void GetIdentityColumnTypes(std::back_insert_iterator<ident_vect_t>);

	// Get Tenant/Role/RoleInstance values. Return related Alias values if alias is used.
	void GetIdentityValues(std::string & tenant, std::string& role, std::string& roleInstance);

	// Aliases for the special Tenant, Role, and RoleInstance identity elements
	void SetTenantAlias(const std::string& name) { _tenantNameAlias = name; }
	void SetRoleAlias(const std::string& name) { _roleNameAlias = name; }
	void SetRoleInstanceAlias(const std::string& name) { _roleInstanceNameAlias = name; }
	const std::string& TenantAlias() const { return _tenantNameAlias; }
	const std::string& RoleAlias() const { return _roleNameAlias; }
	const std::string& RoleInstanceAlias() const { return _roleInstanceNameAlias; }

	const ident_vect_t * GetIdentityVector() { return &identityColumns; }

	const std::string & AgentIdentity() const { return _agentIdentity; }

	//////////// Envelope ///////

	using EnvelopeColumn = std::pair<std::string, std::string>;
	void AddEnvelopeColumn(std::string && name, std::string && value);
	void ForeachEnvelopeColumn(const std::function<void(const EnvelopeColumn&)>&);

	/////////// Table Schemas and Event Sources //////////

	/// <summary>Add a schema to configuration. Once invoked, the caller no longer owns the schema object.</summary>
	/// <param name="schema">
	/// Pointer to the schema to be added. Once handed to AddSchema, the caller no longer owns the pointer.
	/// </param>
	void AddSchema(TableSchema* schema);

	/// <summary>Add a source to the configuration. The source name can be mapped to an already-known schema.</summary>
	/// <param name="source">The name by which the source identities itself</param>
	/// <param name="schema">The name of the schema</param>
	void AddSource(const std::string& source, const std::string& schema);
	bool IsValidSource(const std::string& source) { return (sources.count(source) > 0); }

	/// <summary>Add a source to the configuration. The source name will only be valid for dynamic schema input protocols.</summary>
	/// <param name="source">The name by which the source identities itself</param>
	void AddDynamicSchemaSource(const std::string& source);
	bool IsValidDynamicSchemaSource(const std::string& source) { return (_dynamic_sources.count(source) > 0); }

	/// <summary>Get the table schema for a source; return 0 if the source is unknown</summary>
	/// <param name="source">The name by which the event source identifies itself</param>
	TableSchema* GetSchema(const std::string& source) const;

	//////////// OMI Tasks //////////////
	void AddOmiTask(OmiTask *task);
	void AddOmiTask(const std::string &ev, Priority pri, Credentials *creds, bool noNPD,
			const std::string &nmsp, const std::string &qry, time_t rate);

	void ForeachOmiTask(const std::function<void(OmiTask*)>&);

	//////////// Arbitrary Tasks //////////////
	void AddTask(ITask *task);
	void ForeachTask(const std::function<void(ITask*)>&);

	//////////// Extensions //////////////
	/// <summary>
	/// Add an extension object to configuration. Once invoked, the caller
	/// no longer owns the extension object.
	/// <param name="extension"> Pointer to the extension object.
	/// Once handed to AddExtension, the caller no longer owns the pointer.
	/// </param>
	/// </summary>
	void AddExtension(MdsdExtension * extension);
	size_t GetNumExtensions() const { return extensions.size(); }
	void ForeachExtension(const std::function<void(MdsdExtension*)>&);

	//////////// Credentials //////////////

	/// <summary>Add a Credential to configuration. Once invoked, the caller no longer owns the creds object.</summary>
	/// <param name="creds">
	/// Pointer to the Credentials to be added. Once handed to AddCredentials, the caller no longer owns the pointer.
	/// </param>
	/// <param name="makeDefault">True if these should be the default credentials for this configuration</param>
	void AddCredentials(Credentials* creds, bool makeDefault);

	/// <summary>Get the credentials for a moniker; return 0 if the moniker is unknown</summary>
	/// <param name="moniker">The moniker of the credential of interest</param>
	Credentials* GetCredentials(const std::string& moniker) const;

	/// <summary>Get the default credentials. Returns 0 if there is no default.</summary>
	Credentials* GetDefaultCredentials() const { return _defaultCreds; }

	/// <summary>Get default moniker. Throw exception if no default is found.</summary>
	std::string GetDefaultMoniker() const;

	/// <summary>Get the autokey URI, if any, for a [moniker,tablename] pair.</summary>
	std::string GetAutokey(const std::string& moniker, const std::string& fullTableName);

	/// <summary>Get EventHub cmd XML items (currently SAS and MDS endpoint ID)
	/// for the moniker/eventName combination</summary>
	mdsd::EhCmdXmlItems GetEventNoticeCmdXmlItems(const std::string & moniker, const std::string & eventName);
	mdsd::EhCmdXmlItems GetEventPublishCmdXmlItems(const std::string & moniker, const std::string & eventName);

	///////////// Quotas /////////////
	void AddQuota(const std::string &name, unsigned long limit) { _quotas[name] = limit; }
	bool IsQuotaExceeded(const std::string &name, unsigned long current) const;

	// Record moniker, eventname, storetype, source name information.
	// If the input 'moniker' is empty, use the default one.
	// sourceName can be empty, e.g. OMIQuery.
	void AddMonikerEventInfo(const std::string & moniker, const std::string & eventName,
		StoreType::Type type, const std::string & sourceName, mdsd::EventType eventType);

	// Validate the events in configuration xml
	void ValidateEvents();

	///////// OboDirectConfig (XJsonBlob) //////////
	void AddOboDirectConfig(const std::string& eventName, std::shared_ptr<mdsd::OboDirectConfig>&& oboDirectConfig)
	{
	    _oboDirectConfigsMap.emplace(eventName, std::move(oboDirectConfig));
	}

	// Caller should catch the std::out_of_range exception if the map doesn't contain a key
	// matching eventName.
	std::shared_ptr<mdsd::OboDirectConfig> GetOboDirectConfig(const std::string& eventName) const
	{
	    return _oboDirectConfigsMap.at(eventName);
	}

	///////////// Helpers /////////////

	// Return a reference to the set of batches associated with the current config
	BatchSet& GetBatchSet() { return _batchSet; }
	// Return a reference to the batches that correspond to "local" storageType. These
	// survive config reloads but require considerably more care in terms of resource
	// management.
	// static BatchSet& GetLocalBatchSet() { return _localBatches; }
	// Given MdsEntityName and autoflush interval, find an existing
	// batch (in the appropriate batch set) or make one.
	Batch* GetBatch(const MdsEntityName &, int interval);

	void StopAllTimers();

	void StartScheduledTasks();
	void StopScheduledTasks();

	void SelfDestruct(int seconds);

	bool ValidateConfig(bool isStartupConfig) const;
	std::string GetCmdContainerSas() const { return cmdContainerSas; }


	// key: moniker name; value: a map of key=EventName; value: EventHub cmd XML items (currently SAS and MDS endpoint)
	using EventHubSasInfo_t = std::unordered_map<std::string, std::shared_ptr<std::unordered_map<std::string, mdsd::EhCmdXmlItems>>>;

	void SetOboDirectPartitionFieldNameValue(std::string&& name, std::string&& value);
	std::string GetOboDirectPartitionFieldValue(const std::string& name) const;
	// Currently the VM resource ID is obtained from (and set on) Management/OboDirectParititionField element with name="resourceId"
	// Change this later if another better methods becomes available or if the logic needs to be changed.
	std::string GetResourceId() const { return _resourceId; }

	// Below is for metric event Json object construction purpose
	// Currently, only DerivedEvent's duration attributes are stored
	// (because currently they are the only metric events available for Azure Monitor Json blob sink)
	void SetDurationForEventName(const std::string& eventName, const std::string& duration) { _eventNamesDurationsMap[eventName] = duration; }
	std::string GetDurationForEventName(const std::string& eventName) const
	{
		auto it = _eventNamesDurationsMap.find(eventName);
		return it == _eventNamesDurationsMap.end() ? std::string() : it->second;
	}

	std::shared_ptr<mdsd::MdsdEventCfg>& GetMdsdEventCfg() {
		return _mdsdEventCfg;
	}

	std::shared_ptr<mdsd::EventPubCfg>& GetEventPubCfg() {
		return _eventPubCfg;
	}

private:
	MdsdConfig();	// Disallow empty constructor

	// this is a record of the config file path. The file path can be renamed/moved during
	// 'this' MdsdConfig file time.
	std::string configFilePath;
	std::deque<Message*> messages;
	std::string currentPath;
	long currentLine;
	int msgMask;

    std::string _autokeyConfigFilePath;

	/// <summary>Prefix for all event names.</summary>
	std::string nameSpace;

	/// <summary>Version suffix for event names. "5" yields a suffix of "Ver5v0".</summary>
	int eventVersion;

	/// <summary>Timestamp of the config file.</summary>
	std::string timeStamp;

	std::map<const std::string, TableSchema*> schemas;
	std::map<const std::string, Credentials*> credentials;
	std::map<const std::string, TableSchema*> sources;
	std::unordered_set<std::string> _dynamic_sources;
	ident_vect_t identityColumns;
	std::vector<EnvelopeColumn> _envelopeColumns;
	std::string _tenantNameAlias;
	std::string _roleNameAlias;
	std::string _roleInstanceNameAlias;
	std::vector<OmiTask*> _omiTasks;
	std::vector<ITask*> _tasks;
	std::map<const std::string, MdsdExtension*> extensions;

	std::string _resourceId;

	unsigned int _partitionCount;
	unsigned long _defaultRetention;

	bool _isUseful;

	Credentials* _defaultCreds;

	BatchSet _batchSet;
	boost::asio::deadline_timer _batchFlushTimer;
	void FlushBatches(const boost::system::error_code &);
	static BatchSet _localBatches;

	std::string _agentIdentity;

	std::map<std::pair<std::string, std::string>, std::string> _autoKeyMap;
	std::mutex _aKMmutex;
	boost::asio::deadline_timer _autoKeyReloadTimer;

	bool LoadAutokey(const boost::system::error_code &);
	void DumpAutokeyTable(std::ostream &os);

	std::mutex _ehMapMutex;
	// key: (original, not mapped) moniker;
	// value: a map of key=EventName; value: EventHub cmd XML items (currently SAS and MDS endpoint)
	using EventHubItemsMap_t = std::unordered_map<std::string, std::shared_ptr<std::unordered_map<std::string, mdsd::EhCmdXmlItems>>>;
	EventHubItemsMap_t _ehNoticeItemsMap;
	EventHubItemsMap_t _ehPubItemsMap;

	mdsd::EhCmdXmlItems GetEventHubCmdXmlItems(EventHubItemsMap_t& ehmap, const std::string & moniker,
		const std::string & eventName, const std::string & eventType);

	void LoadEventHubKeys(const std::vector<std::pair<std::string, std::string>>& keylist);
	void DumpEventPublisherInfo();
	void SetMappedMoniker(const EventHubSasInfo_t & ehmap);

	// For EventHub notice, create uploaders in EH manager,
	// then set the SAS key and start the uploaders.
	void InitEventHubNotice();

	// Initialize EventHub publishers, set SAS keys
	void InitEventHubPub();


	// Make sure each annotated event exists
	void ValidateAnnotations();

	// Make sure each event publisher has some SAS key, either embedded, or from AutoKey
	void ValidateEventHubPubKeys();

	// Make sure each event publisher has a LocalSink object that'll publish data for it.
	void ValidateEventHubPubSinks();

	void SetupEventHubPubEmbeddedKeys();
	void SetEventHubPubForLocalSinks();

	// key: event name; value: mdsd::OboDirectConfig
	std::unordered_map<std::string, std::shared_ptr<mdsd::OboDirectConfig>> _oboDirectConfigsMap;

	// key: OboDirect partition field name (e.g., "resourceId"); value: value (e.g., "SUBSCRIPTIONS/91D12660-3DEC-467A-BE2A-213B5544DDC0/RESOURCEGROUPS/RMANDASHOERG/PROVIDERS/MICROSOFT.DEVICES/IOTHUBS/SHOEHUBSCUS3")
	std::unordered_map<std::string, std::string> _oboDirectPartitionFieldsMap;

	// key: eventName (e.g., "WADMetricsPT1MP10DV2S"); value: duration (e.g., "PT1M")
	// Currently only DerivedEvent's durations are stored.
	std::unordered_map<std::string, std::string> _eventNamesDurationsMap;

	static void Destroyer(MdsdConfig *, boost::asio::deadline_timer *);

	std::map<std::string, unsigned long> _quotas;

	bool _monitoringManagementSeen;
	std::string cmdContainerSas;

	// true if autokey is used in any account; false otherwise.
	bool _hasAutoKey;

	std::shared_ptr<mdsd::MdsdEventCfg> _mdsdEventCfg;
	std::shared_ptr<mdsd::EventPubCfg> _eventPubCfg;

	/// <summary>
	/// Set the line number of the file being parsed. Used when recording messages generated during parsing.
	/// </summary>
	/// <param name="num">The line sequence number of the chunk being handed to the parser</param>
	void SetLineNumber(long num) { currentLine = num; }

	/// <summary>Increment the line number indicator for the next chunk to be parsed</summary>
	void NextLine() { currentLine++; }
	std::vector<std::pair<std::string, std::string>> ExtractCmdContainerAutoKeys();
};

#endif //_MDSDCONFIG_HH_

// vim: se sw=8 :
