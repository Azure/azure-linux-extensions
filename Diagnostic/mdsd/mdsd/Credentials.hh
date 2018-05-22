// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CREDENTIALS_HH_
#define _CREDENTIALS_HH_

#include <string>
#include <iostream>
#include "MdsTime.hh"
#include "MdsEntityName.hh"
#include "EventHubCmd.hh"

class MdsdConfig;

class Credentials {

	friend std::ostream& operator<<(std::ostream &os, const Credentials& creds);

public:
	enum SecretType { None, Key, SAS };
	// EventPublish: Event data directly publishing to EventHub.
	enum class ServiceType { XTable, Blob, EventPublish };
	static const std::string& ServiceType_to_string(ServiceType svcType);

	Credentials(const std::string& moniker, SecretType type) : _moniker(moniker), _secretType(type) {}
	virtual ~Credentials() {}

	const std::string Moniker() const { return _moniker; }
	SecretType Type() const { return _secretType; }

	virtual bool useAutoKey() const { return false; }

	virtual std::string AccountName() const = 0;

	virtual bool ConnectionString(const MdsEntityName &target, ServiceType svcType,
		std::string &fullSvcName, std::string &connstr,
		MdsTime &expires) const = 0;

	virtual const std::string TypeName() const = 0;

	virtual bool accessAnyTable() const  { return (Type() == Key || useAutoKey() ); }

private:
	const std::string _moniker;
	SecretType _secretType;

	Credentials() = delete;
};

std::ostream& operator<<(std::ostream &os, const Credentials& creds);
std::ostream& operator<<(std::ostream &os, Credentials::ServiceType svcType);

namespace CredentialType {


class invalid_type : public std::logic_error
{
public:
	invalid_type(Credentials::ServiceType svcType)
		: std::logic_error("Service type ["
		                 + Credentials::ServiceType_to_string(svcType)
				 + "] not supported by this operation")
		{ }
};

static inline std::string MakePublicCloudEndpoint(const std::string& acct, Credentials::ServiceType svcType)
{
	std::string result;
	result.reserve(33 + acct.size());

	result.append("https://").append(acct);
	if (svcType == Credentials::ServiceType::Blob) {
		result.append(".blob.core.windows.net");
	} else if (svcType == Credentials::ServiceType::XTable) {
		result.append(".table.core.windows.net");
	} else {
		throw invalid_type(svcType);
	}

	return result;
}

class SharedKey : public Credentials {
public:
	SharedKey(const std::string& moniker, const std::string &name, const std::string &key)
		: Credentials(moniker, SecretType::Key), _accountName(name), _secret(key),
		  _blobUri(MakePublicCloudEndpoint(name, ServiceType::Blob)),
		  _tableUri(MakePublicCloudEndpoint(name, ServiceType::XTable)) {}

	std::string AccountName() const { return _accountName; }
	bool ConnectionString(const MdsEntityName &target, ServiceType svcType,
		std::string &fullSvcName, std::string &connstr, MdsTime &expires) const;
	const std::string TypeName() const { return std::string{"SharedKey"}; }

	void TableUri(const std::string& uri) { _tableUri = uri; }
	void BlobUri(const std::string& uri) { _blobUri = uri; }

	// To get the connection string only, without passing target. Will throw if svcType is neither blob nor table.
	std::string GetConnectionStringOnly(ServiceType svcType) const;

private:
	std::string _accountName;
	std::string _secret;
	std::string _blobUri;
	std::string _tableUri;
};

class AutoKey : public Credentials {
public:
	AutoKey(const std::string& moniker, MdsdConfig *config) : Credentials(moniker, SecretType::SAS), _config(config) {}

	std::string AccountName() const { return std::string{"AutoKey"}; }
	bool ConnectionString(const MdsEntityName &target, ServiceType svcType,
		std::string &fullSvcName, std::string &connstr, MdsTime &expires) const;

	const std::string TypeName() const { return std::string{"AutoKey"}; }
	bool useAutoKey() const { return true; }
	static MdsTime GetExpireTimeFromSasSE(const std::string & sas);

	mdsd::EhCmdXmlItems GetEhParameters(const std::string& eventName, Credentials::ServiceType eventType) const;

private:
	MdsdConfig *_config;
};

class SAS : public Credentials {
public:
	SAS(const std::string& moniker, const std::string& acct, const std::string &token);

	std::string AccountName() const { return _accountName; }
	bool ConnectionString(const MdsEntityName &target, ServiceType svcType,
		std::string &fullSvcName, std::string &connstr, MdsTime &expires) const;
	const std::string TypeName() const { return std::string{"SAS"}; }
	const std::string Token() const { return _secret; }
	bool IsAccountSas() const { return _isAccountSas; }
	bool accessAnyTable() const  { return _isAccountSas; }

	void BlobUri(const std::string& uri) { _blobUri = uri; }
	void TableUri(const std::string& uri) { _tableUri = uri; }

	// To get the connection string only, without passing target. Will throw if svcType is neither blob nor table.
	std::string GetConnectionStringOnly(ServiceType svcType) const;

private:
	std::string _secret;
	std::string _accountName;
	std::string _blobUri;
	std::string _tableUri;
	bool _isAccountSas;
};

class Local : public Credentials {
public:
	Local() : Credentials(std::string{"(LOCAL)"}, SecretType::None) {}

	std::string AccountName() const { return std::string{"Local"}; }
	bool ConnectionString(const MdsEntityName &target, ServiceType svcType,
		std::string &fullSvcName, std::string &connstr, MdsTime &expires) const;
	const std::string TypeName() const { return std::string{"Local"}; }
};

}

#endif // _CREDENTIALS_HH_
// vim: set ai sw=8 :
