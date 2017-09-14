// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _AZUREUTILITY_HH_
#define _AZUREUTILITY_HH_

#include <string>
#include <stdexcept>

namespace azure { namespace storage { class storage_exception; }}

namespace MdsdUtil {

/// <summary>Validate the storage credential (shared key or SAS) for table storage.
/// Returns silently if it's valid. Throws an exception if it's not valid.
/// The storage credential is invalid if it is incorrect, or
/// if the storage account doesn't support table storage (e.g., Premium
/// or Blob storage account). The caller must catch the exception.</summary>
void ValidateStorageCredentialForTable(const std::string& connStr);

/// <summary>Check the passed SAS token for its validity.
/// Currently this is mainly to validate an account SAS for its minimal
/// requirements (e.g., services, permissions, ...). We may perform
/// more thorough SAS token validation here, even for a service SAS
/// but it's currently out of scope.
/// Returns silently iff it's any valid SAS (but it doesn't check much about
/// a service SAS). Sets isValidAccountSas true if the sastoken is
/// a valid account SAS with needed services and permissions.
/// Throws an exception if the SAS token is invalid (currently only as an account SAS)</summary>
void ValidateSAS(const std::string& sastoken, bool& isValidAccountSas);

class MdsdInvalidSASException : public std::runtime_error
{
public:
	MdsdInvalidSASException(const std::string& message)
		: std::runtime_error(message)
	{}
};


/// <summary>Returns true iff the passed storage exception indicates
/// the error code is "ContainerAlreadyExists".</summary>
bool ContainerAlreadyExistsException(const azure::storage::storage_exception& e);

/// <summary>Creates the specified container using the given connection string.
/// This function may throw an exception and the caller should handle any.</summary>
void CreateContainer(const std::string& connectionString, const std::string& containerName);

}

#endif // _AZUREUTILITY_HH_
