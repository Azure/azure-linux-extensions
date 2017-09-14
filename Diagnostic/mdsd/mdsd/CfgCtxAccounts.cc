// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxAccounts.hh"
#include "MdsdConfig.hh"
#include "Credentials.hh"
#include "Utility.hh"
#include "AzureUtility.hh"
#include "cryptutil.hh"
#include "Trace.hh"
#include <algorithm>

///////// CfgCtxAccounts

subelementmap_t CfgCtxAccounts::_subelements = {
	{ "Account", [](CfgContext* parent) -> CfgContext* { return new CfgCtxAccount(parent); } },
	{ "SharedAccessSignature", [](CfgContext* parent) -> CfgContext* { return new CfgCtxSAS(parent); } },
};

std::string CfgCtxAccounts::_name = "Accounts";

CfgContext*
CfgCtxAccounts::Leave()
{
	return CfgContext::Leave();
}

///////// CfgCtxAccount

void
CfgCtxAccount::Enter(const xmlattr_t& properties)
{
	Trace trace(Trace::ConfigLoad, "CfgCtxAccount::Enter");
	std::string moniker, account, sharedKey, decryptKeyPath, blobEndpoint, tableEndpoint;
	bool makeDefault = false;

	for (const auto& item : properties)
	{
		if (item.first == "moniker") {
			if (moniker.empty()) {
				moniker = item.second;
			}
			else {
				ERROR("\"moniker\" can appear in <Account> only once");
			}
		}
		else if (item.first == "key") {
			sharedKey = item.second;
		}
		else if (item.first == "decryptKeyPath") {
			decryptKeyPath = item.second;
		}
		else if (item.first == "account") {
			account = item.second;
			size_t len = account.length();
			// Squeeze any embedded spaces from the account
			account.erase(std::remove(account.begin(), account.end(), ' '), account.end());
			if (len != account.length()) {
				WARNING("Account cannot contain spaces; blanks were removed");
			}
		}
		else if (item.first == "isDefault") {
			makeDefault = MdsdUtil::to_bool(item.second);
		}
		else if (item.first == "blobEndpoint") {
			blobEndpoint = item.second;
		}
		else if (item.first == "tableEndpoint") {
			tableEndpoint = item.second;
		}
		else {
			WARNING("Ignoring unexpected attribute \"" + item.first + "\"");
		}
	}

	if (moniker.empty()) {
		FATAL("<Account> requires \"moniker\" attribute");
	}
	else {
		// Create the correct credential object based on the attributes
		// Must be shared key
		if (account.empty()) {
			ERROR("\"account\" must be set for shared key moniker");
		} else if (sharedKey.empty()) {
			ERROR("\"key\" must be set for shared key moniker");
		} else {
			if (!decryptKeyPath.empty()) {
				try {
					sharedKey = cryptutil::DecodeAndDecryptString(decryptKeyPath, sharedKey);
				}
				catch (const std::exception& e) {
					ERROR(std::string("Storage key decryption (using private key at ").append(decryptKeyPath).append(") failed with the message: ").append(e.what()));
					return;
				}
				catch (...) {
					ERROR("Unknown exception thrown when decrypting storage key");
					return;
				}
			}

			auto creds = new CredentialType::SharedKey(moniker, account, sharedKey);
			if (!blobEndpoint.empty()) {
				creds->BlobUri(blobEndpoint);
			}
			if (!tableEndpoint.empty()) {
				creds->TableUri(tableEndpoint);
			}

			/* Validate storage account for table access.
			 */
			try {
				MdsdUtil::ValidateStorageCredentialForTable(creds->GetConnectionStringOnly(Credentials::ServiceType::XTable));
				Config->AddCredentials(creds, makeDefault);
			}
			catch (const std::exception& e) {
				ERROR(std::string("Storage credential validation for table storage failed: ").append(e.what()));
			}
			catch (...) {
				ERROR("Unknown exception thrown when validating storage credential for table storage");
			}
		}
	}
}

subelementmap_t CfgCtxAccount::_subelements;

std::string CfgCtxAccount::_name = "Account";

///////// CfgCtxSAS

void
CfgCtxSAS::Enter(const xmlattr_t& properties)
{
	std::string moniker, account, token, decryptKeyPath, blobEndpoint, tableEndpoint;
	bool makeDefault = false;

	for (const auto& item : properties)
	{
		if (item.first == "moniker") {
            moniker = item.second;
		}
		else if (item.first == "key") {
			token = item.second;
			MdsdUtil::ReplaceSubstring(token, "&#38;", "&");
		}
		else if (item.first == "decryptKeyPath") {
			decryptKeyPath = item.second;
		}
		else if (item.first == "account") {
			account = item.second;
			size_t len = account.length();
			// Squeeze any embedded spaces from the account
			account.erase(std::remove(account.begin(), account.end(), ' '), account.end());
			if (len != account.length()) {
				WARNING("Account cannot contain spaces; blanks were removed");
			}
		}
		else if (item.first == "blobEndpoint") {
			blobEndpoint = item.second;
		}
		else if (item.first == "tableEndpoint") {
			tableEndpoint = item.second;
		}
        else if (item.first == "isDefault") {
            makeDefault = MdsdUtil::to_bool(item.second);
        }
		else {
			WARNING("Ignoring unexpected attribute \"" + item.first + "\"");
		}
	}

	if (moniker.empty()) {
		FATAL("\"moniker\" must be specified");
	}
	else if (account.empty()) {
		FATAL("\"account\" must be specified");
	}
	else if (token.empty()) {
		FATAL("\"key\" must be specified");
	} else {
		if (!decryptKeyPath.empty()) {
			try {
				token = cryptutil::DecodeAndDecryptString(decryptKeyPath, token);
				MdsdUtil::ReplaceSubstring(token, "&#38;", "&");
			}
			catch (const std::exception& e) {
				ERROR(std::string("Storage account SAS token decryption (using private key at ").append(decryptKeyPath).append(") failed with the message: ").append(e.what()));
				return;
			}
			catch (...) {
				ERROR("Unknown exception thrown when decrypting storage account SAS token");
				return;
			}
		}

		try {
			auto creds = new CredentialType::SAS(moniker, account, token);
			if (!blobEndpoint.empty()) {
				creds->BlobUri(blobEndpoint);
			}
			if (!tableEndpoint.empty()) {
				creds->TableUri(tableEndpoint);
			}

			if (creds->IsAccountSas()) {
				/* Validate storage account for table access (same as above in shared key)
				 * only if it's an account SAS. */
				MdsdUtil::ValidateStorageCredentialForTable(creds->GetConnectionStringOnly(Credentials::ServiceType::XTable));
			}
			Config->AddCredentials(creds, makeDefault);
		}
		catch (MdsdUtil::MdsdInvalidSASException& e) {
			ERROR(std::string("Invalid SAS token given. Reason: ").append(e.what()));
		}
		catch (const std::exception& e) {
			ERROR(std::string("Storage credential validation for table storage failed: ").append(e.what()));
		}
		catch (...) {
			ERROR("Unknown exception thrown when validating storage credential for table storage");
		}
	}
}

subelementmap_t CfgCtxSAS::_subelements;

std::string CfgCtxSAS::_name = "SharedAccessSignature";

// vim: se sw=8 :
