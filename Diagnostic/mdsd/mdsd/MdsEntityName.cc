// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "MdsEntityName.hh"
#include "MdsdConfig.hh"
#include "Credentials.hh"
#include "Crypto.hh"
#include "Utility.hh"
#include "Logger.hh"
#include "Trace.hh"
#include <sstream>

using std::string;

// MdsEntityName for SchemasTable in the account identified by these creds
MdsEntityName::MdsEntityName(const MdsdConfig *config, const Credentials *creds) : _creds(creds)
{
	Trace trace(Trace::EntityName, "MdsEntityName constructor for SchemasTable");
	if (!config) {
		throw std::invalid_argument("Internal error: null config ptr");
	} else if (!creds) {
		throw std::invalid_argument("Internal error: null credentials");
	}

	_storeType = StoreType::XTable;
	_physTableName = _basename = "SchemasTable";
	_isConstant = true;
	_isSchemasTable = true;
}

// Constructor for arbitrary table in some store (local or remote) accessed via a specific moniker.
MdsEntityName::MdsEntityName(const std::string &eventName, bool noPerNDay, const MdsdConfig *config,
                        const std::string &acct, StoreType::Type sinkType, bool isFullName)
	: _basename(eventName), _isConstant(true), _isSchemasTable(false), _storeType(sinkType), _creds(nullptr),
	  _physTableName(eventName),
	  _eventName(eventName), _eventVersion(config->EventVersion())
{
	Trace trace(Trace::EntityName, "MdsEntityName constructor");

	if (eventName.empty()) {
		throw std::invalid_argument("eventName must not be empty");
	}

	auto maxNameLength = StoreType::max_name_length(_storeType);

        if (sinkType == StoreType::Type::Local || sinkType == StoreType::Type::File) {
		// Local table names never get encoded/shortened. Also, they need no credentials and no MdsdConfig
		if (_basename.length() > maxNameLength) {
			std::ostringstream msg;
			msg << "Event name \"" << _basename << "\" is too long for requested storeType (max "
			    << maxNameLength << " bytes)";
			throw std::invalid_argument(msg.str());
		}
		if (trace.IsActive()) {
			std::ostringstream msg;
			msg << "Local/File EventName \"" << eventName << "\" yields basename \"" << _basename<< "\" and _isConstant="
			    << _isConstant;
			trace.NOTE(msg.str());
		}
		return;
	}

	if (!config) {
		throw std::invalid_argument("Internal error: null config ptr");
	}
	if (acct.empty()) {
                if (! (_creds = config->GetDefaultCredentials())) {
                        throw std::invalid_argument("No default credentials were defined");
                }
        } else {
                if (! (_creds = config->GetCredentials(acct))) {
                        throw std::invalid_argument("No definition found for account moniker " + acct);
                }
        }

	// The access credentials can influence how the actual name of the entity is computed, so
	// we have to look inside.
	if (isFullName && noPerNDay) {
		_isConstant = true;
		trace.NOTE("Marked as isFullName without NDay suffix");
	} else if (_creds->accessAnyTable()) {
		std::ostringstream augmentedName;
		if (isFullName) {
			augmentedName << eventName;
			trace.NOTE("Marked as isFullName and gets NDay suffix");
		} else {
			augmentedName << config->Namespace() << eventName << "Ver" << config->EventVersion() << "v0";
		}
		_basename = _physTableName = augmentedName.str();
		_isConstant = noPerNDay;	// This name might vary

		// The basename plus perNDay suffix (if any) must fit within the maximum entity name size
		// for MDS. If it doesn't, replace the basename with "T" followed by the MD5 hash of the
		// basename (without perNDay suffix), which is always short enough.
		// See Windows MA source NetTransport.cpp:GetNDayEventName()
		size_t limit = maxNameLength - (_isConstant?0:8);
		if (_basename.size() > limit) {
			trace.NOTE("Basename " + _basename + " too long; using MD5 hash");
			_basename = "T" + Crypto::MD5HashString(_basename).to_string();
		}
	} else if (auto SAScreds = dynamic_cast<const CredentialType::SAS*>(_creds)) {
		if (!isFullName) {
			std::ostringstream augmentedName;
			augmentedName << config->Namespace() << eventName << "Ver" << config->EventVersion() << "v0";
			_physTableName = augmentedName.str();
		}
		// SAS (non-account SAS) includes the tablename; extract it from there. Even if isFullName is set, we have to try this
		std::map<string, string> qry;
		MdsdUtil::ParseQueryString(SAScreds->Token(), qry);
		auto item = qry.find("tn");
		if (item != qry.end()) {
			_basename = item->second;
		} else if (!SAScreds->IsAccountSas()) {
			// We'll just use what we were given; it'll probably fail later, too.
			Logger::LogError("Table SAS lacks [tn=]: " + SAScreds->Token());
		}
	}

	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << "EventName \"" << eventName << "\" yields basename \"" << _basename<< "\", physTableName \"";
		msg << _physTableName << "\", and _isConstant=" << _isConstant;
		trace.NOTE(msg.str());
	}
}

std::string
MdsEntityName::Name() const
{
	Trace trace(Trace::EntityName, "MdsEntityName::Name");

	if (_isConstant) {
		trace.NOTE("Using " + _basename);
		return _basename;
	}

	std::string fullname = _basename + MdsdUtil::GetTenDaySuffix();
	trace.NOTE("Computed table name " + fullname);
	return fullname;
}

std::ostream&
operator<<(std::ostream &str, const MdsEntityName &target)
{
	switch(target._storeType) {
	case StoreType::None:
		str << "[None]"; break;
	case StoreType::XTable:
		str << "[XTable]"; break;
	case StoreType::Local:
		str << "[Local]"; break;
	case StoreType::File:
		str << "[File]"; break;
	default:
		str << "[unknown]"; break;
	}

	str << target._basename;

	if (! target._isConstant) {
		str << "*";
	}
	return str;
}

// vim: se sw=8 :
