// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxManagement.hh"
#include "MdsdConfig.hh"
#include "Listener.hh"
#include "Utility.hh"
#include "Trace.hh"
#include <cstdlib>

/////// CfgCtxManagement

subelementmap_t CfgCtxManagement::_subelements = {
	{ "Identity", [](CfgContext* parent) -> CfgContext* { return new CfgCtxIdentity(parent); } },
	{ "AgentResourceUsage", [](CfgContext* parent) -> CfgContext* { return new CfgCtxAgentResourceUsage(parent); } },
	{ "OboDirectPartitionField", [](CfgContext* parent) -> CfgContext* { return new CfgCtxOboDirectPartitionField(parent); } }
};

std::string CfgCtxManagement::_name = "Management";

std::map<std::string, unsigned int> CfgCtxManagement::_eventVolumes = {
	{ "Small", 1 },
	{ "small", 1 },
	{ "Medium", 10 },
	{ "medium", 10 },
	{ "Large", 100 },
	{ "large", 100 }
};

void CfgCtxManagement::Enter(const xmlattr_t& properties)
{
	Trace trace(Trace::ConfigLoad, "CfgCtxManagement::Enter");
	for (const auto& item : properties)
	{
		if (item.first == "eventVolume") {
			auto numPart = _eventVolumes.find(item.second);
			if (numPart != _eventVolumes.end()) {
				Config->PartitionCount(numPart->second);
			} else {
				ERROR("Unknown eventVolume \"" + item.second + "\"");
			}
		}
		else if (item.first == "defaultRetentionInDays") {
			unsigned long retention = std::stoul(item.second);
			if (retention < 1) {
				ERROR("Invalid value for defaultRetentionInDays");
			} else {
				Config->DefaultRetention(retention);
			}
		}
		else {
			Config->AddMessage(MdsdConfig::warning, "<Management> ignoring unexpected attribute " + item.first);
		}
	}
}

////// CfgCtxIdentity

subelementmap_t CfgCtxIdentity::_subelements = {
	{ "IdentityComponent", [](CfgContext* parent) -> CfgContext* { return new CfgCtxIdentityComponent(parent); } }
};

std::string CfgCtxIdentity::_name = "Identity";

void CfgCtxIdentity::Enter(const xmlattr_t& properties)
{
    Config->SetTenantAlias("Tenant");
    Config->SetRoleAlias("Role");
    Config->SetRoleInstanceAlias("RoleInstance");

    for (const auto& item : properties)
    {
        if (item.first == "type") {
            if (item.second == "TenantRole") {
                // Add three identity components based on envariables
                AddEnvariable("Tenant", "MONITORING_TENANT");
                AddEnvariable("Role", "MONITORING_ROLE");
                AddEnvariable("RoleInstance", "MONITORING_ROLE_INSTANCE");
                IdentityWasSet = true;
            } else if (item.second == "ComputerName") {
                // Add a single identity component containing the hostname
                (void)Config->AddIdentityColumn("ComputerName", Config->AgentIdentity());
                IdentityWasSet = true;
            } else {
                WARNING("Ignoring unknown type " + item.second);
            }
        } else if (item.first == "tenantNameAlias") {
	    Config->SetTenantAlias(item.second);
        } else if (item.first == "roleNameAlias") {
	    Config->SetRoleAlias(item.second);
        } else if (item.first == "roleInstanceNameAlias") {
	    Config->SetRoleInstanceAlias(item.second);
        } else {
            WARNING("Ignoring unknown attribute " + item.first);
        }
    }
}

void
CfgCtxIdentity::AddString(const std::string& name, const std::string& value)
{
	if (IdentityWasSet) {
		WARNING("Ignoring extra identity column " + name);
		return;
	}

	if (!(Config->AddIdentityColumn(name, value))) {
		ERROR("Duplicate IdentityComponent " + name);
	}
}

void
CfgCtxIdentity::AddEnvariable(const std::string& name, const std::string& varname)
{
	if (IdentityWasSet) {
		WARNING("Ignoring extra identity column " + name);
		return;
	}

	try {
		std::string Value = MdsdUtil::GetEnvironmentVariable(varname);
		if (!(Config->AddIdentityColumn(name, Value))) {
			ERROR("Duplicate IdentityComponent " + name);
		}
	}
	catch (std::exception & ex) {
		WARNING(std::string(ex.what()) + "; " + name + " not added to identity columns");
	}
}

////// CfgCtxIdentityComponent

subelementmap_t CfgCtxIdentityComponent::_subelements;

std::string CfgCtxIdentityComponent::_name = "IdentityComponent";

void CfgCtxIdentityComponent::Enter(const xmlattr_t& properties)
{
	IsValid = true;		// Assume this will be a valid definition
	IgnoreBody = ExtraBody = false;

	std::string Envariable;
	bool useHostname = false;

	_ctxidentity = dynamic_cast<CfgCtxIdentity*>(ParentContext);
	if (!_ctxidentity) {
		FATAL("Found <IdentityComponent> in <" + ParentContext->Name() + ">; that can't happen");
		IsValid = false;	// Bummer; invalid
		return;
	}

	for (const auto& item : properties)
	{
		if (item.first == "name") {
			ComponentName = item.second;
		} else if (item.first == "envariable") {
			Envariable = item.second;
		} else if (item.first == "useComputerName") {
			useHostname = MdsdUtil::to_bool(item.second);
		} else {
			ERROR("<IdentityComponent> ignoring unexpected attribute " + item.first);
		}
	}

	if (ComponentName.empty()) {
		ERROR("<IdentityComponent> requires attribute \"name\"");
		IsValid = false;	// Bummer; invalid
	} else if (!Envariable.empty() && useHostname) {
		ERROR("Cannot specify both useComputerName and envariable for the same <IdentityComponent>");
		IsValid = false;
	} else if (!Envariable.empty() || useHostname) {
		IgnoreBody = true;
		if (useHostname) {
			_ctxidentity->AddString(ComponentName, Config->AgentIdentity());
		} else {
			_ctxidentity->AddEnvariable(ComponentName, Envariable);
		}
	}
	// If !IgnoreBody && IsValid, then the Leave() method will add the accumulated
	// string to the Identity column set
	if (!IsValid) {
		IgnoreBody = true;
	}
}

void
CfgCtxIdentityComponent::HandleBody(const std::string& body)
{
	if (IgnoreBody) {
		ExtraBody = true;	// We'll ignore it and warn about it
	} else {
		Body += body;
	}
}

CfgContext* CfgCtxIdentityComponent::Leave()
{
	if (!IsValid) {
		WARNING("Skipping invalid IdentityComponent");
	} else if (ExtraBody) {
			WARNING("Ignoring extra content for IdentityComponent; hope that's okay");
	} else if (!IgnoreBody) {
		if (empty_or_whitespace()) {
			WARNING("Empty value for IdentityComponent; hope that's okay");
		}
		_ctxidentity->AddString(ComponentName, Body);
	}
	return ParentContext;
}

////// CfgCtxAgentResourceUsage

subelementmap_t CfgCtxAgentResourceUsage::_subelements;

std::string CfgCtxAgentResourceUsage::_name = "AgentResourceUsage";

void CfgCtxAgentResourceUsage::Enter(const xmlattr_t& properties)
{
	for (const auto& item : properties)
	{
		if (item.first == "diskQuotaInMB") {
			unsigned long diskQuota = std::stoul(item.second);
			if (diskQuota < 1) {
				ERROR("diskQuotaInMB must be greater than zero");
			} else {
				Config->AddQuota("disk", diskQuota);
			}
		} else if (item.first == "dupeWindowSeconds") {
			unsigned long dupeWindow = std::stoul(item.second);
			if (dupeWindow < 60) {
				WARNING("dupeWindowSeconds must be >= 60");
				dupeWindow = 60;
			} else if (dupeWindow > 3600) {
				WARNING("dupeWindowSeconds must be <= 3600");
				dupeWindow = 3600;
			}
			Listener::setDupeWindow(dupeWindow);
		} else {
			ERROR("<AgentResourceUsage> ignoring unexpected attribute " + item.first);
		}
	}
}

////// CfgCtxOboDirectPartitionField

subelementmap_t CfgCtxOboDirectPartitionField::_subelements;

std::string CfgCtxOboDirectPartitionField::_name = "OboDirectPartitionField";

void CfgCtxOboDirectPartitionField::Enter(const xmlattr_t& properties)
{
	std::string name, value;

	for (const auto& item : properties) {
		if (item.first == "name") {
			name = item.second;
		}
		else if (item.first == "value") {
			value = item.second;
		}
		else {
			WARNING("Ignoring unknown attribute " + item.first);
		}
	}

	if (name.empty() || value.empty()) {
		ERROR("<OboDirectPartitionField> requires both 'name' and 'value' attributes.");
		return;
	}

	Config->SetOboDirectPartitionFieldNameValue(std::move(name), std::move(value));
}

// vim: se sw=8 :
