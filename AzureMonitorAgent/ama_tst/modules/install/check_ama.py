import re
import sys
import socket
import xml.dom.minidom
if sys.version_info[0] == 3:
    import urllib.request as urllib
    import urllib.error as urlerror

elif sys.version_info[0] == 2:
    import urllib2 as urllib
    import urllib2 as urlerror
    
try:
    import requests
except ImportError:
    pass

from error_codes import *
from errors      import error_info, get_input
from helpers     import get_package_version
from connect.check_endpts import check_internet_connect

AMA_URL = 'https://docs.microsoft.com/en-us/azure/azure-monitor/agents/azure-monitor-agent-extension-versions'
# Timeout for fetching latest AMA version (in seconds)
AMA_VERSION_FETCH_TIMEOUT = 60

def get_latest_ama_version(curr_version):
    # python2 and python3 compatible
    # Set timeout to prevent hanging
    timeout = AMA_VERSION_FETCH_TIMEOUT
    
    try:
        if sys.version_info[0] == 3:
            # Python 3 - try urllib first, then requests as fallback
            try:
                r = urllib.urlopen(AMA_URL, timeout=timeout).read()
            except AttributeError:
                # If urllib doesn't work, try requests
                r = requests.get(AMA_URL, timeout=timeout).text
        else:
            # Python 2 - use urllib2 which supports timeout
            r = urllib.urlopen(AMA_URL, timeout=timeout).read()
            
    except socket.timeout:
        return None, "Connection timed out after {0} seconds while trying to fetch latest AMA version from {1}. Please check your network connectivity and firewall settings.".format(timeout, AMA_URL)
    except Exception as e:
        # More specific timeout detection
        error_str = str(e).lower()
        error_type = type(e).__name__
        
        # Check for various timeout conditions
        if (error_type == 'timeout' or 
            'timeout' in error_str or 
            'timed out' in error_str or
            'read timeout' in error_str or
            'connect timeout' in error_str):
            return None, "Request timed out after {0} seconds while trying to fetch latest AMA version from {1}. This may be due to network connectivity issues or firewall restrictions.".format(timeout, AMA_URL)
        
        # Handle HTTP and URL errors
        if hasattr(e, 'code'):
            return None, "HTTP error {0} while trying to fetch latest AMA version from {1}. The documentation server may be temporarily unavailable.".format(e.code, AMA_URL)
        elif 'urlerror' in error_type.lower() or 'httperror' in error_type.lower():
            return None, "Network error while trying to fetch latest AMA version from {1}: {0}".format(str(e), AMA_URL)
        elif 'name or service not known' in error_str:
            return None, "DNS resolution failed for {1}. Please check the URL and your network settings: {0}".format(str(e), AMA_URL)
        elif 'connection refused' in error_str:
            return None, "Connection refused while trying to connect to {1}. The server may be down: {0}".format(str(e), AMA_URL)
        elif 'network is unreachable' in error_str:
            return None, "Network is unreachable while trying to connect to {1}. Please check your network configuration: {0}".format(str(e), AMA_URL)
        else:
            return None, "Unexpected error while trying to fetch latest AMA version from {1}: {0}".format(str(e), AMA_URL)

    try:
        # Ensure we have a string for both Python 2 and 3 compatibility
        if sys.version_info[0] == 3 and isinstance(r, bytes):
            # Python 3: convert bytes to string
            r = r.decode('utf-8')
        # Python 2: urllib2.urlopen().read() returns str, which works fine with regex
            
        # Find all table rows in tbody and extract all 4th columns (Linux columns)
        # This approach is more robust and handles missing values and multiple rows
        tbody_pattern = r'<tbody>(.*?)</tbody>'
        tbody_match = re.search(tbody_pattern, r, re.DOTALL)
        
        if not tbody_match:
            return None, "Could not find version table in Microsoft documentation"
        
        tbody_content = tbody_match.group(1)
        
        # Find all table rows
        row_pattern = r'<tr[^>]*>(.*?)</tr>'
        rows = re.findall(row_pattern, tbody_content, re.DOTALL)
        
        latest_version = None
        
        # Process each row to find the latest version
        # Since rows are in chronological order (newest first), we want the first non-empty row
        for row in rows:
            # Extract all cells from this row
            cell_pattern = r'<td[^>]*>(.*?)</td>'
            cells = re.findall(cell_pattern, row, re.DOTALL)
            
            # Check if we have at least 4 columns and the 4th column (Linux) is not empty
            if len(cells) >= 4:
                linux_cell = cells[3]  # 4th column (index 3)
                
                # Remove HTML tags and normalize whitespace
                # First replace <br> tags with spaces to avoid concatenation
                clean_content = re.sub(r'<br[^>]*>', ' ', linux_cell)
                # Remove all other HTML tags (including superscript)
                clean_content = re.sub(r'<[^>]+>', '', clean_content)
                # Normalize whitespace
                clean_content = re.sub(r'\s+', ' ', clean_content).strip()
                
                # Skip empty cells
                if not clean_content or clean_content.lower() in ['', 'none', 'n/a']:
                    continue  # Go to next row
                
                # Handle version ranges like "1.26.2-1.26.5"
                # Replace hyphens between versions with commas for easier parsing
                clean_content = re.sub(r'(\d+\.\d+\.\d+(?:\.\d+)?)\s*-\s*(\d+\.\d+\.\d+(?:\.\d+)?)', r'\1, \2', clean_content)
                
                # Find all version numbers in this cell (handles multiple versions)
                # More flexible regex that handles superscript and other text
                version_matches = re.findall(r'(\d+\.\d+\.\d+(?:\.\d+)?)', clean_content)
                
                if version_matches:
                    # If multiple versions found, take the highest one from this cell
                    cell_latest = None
                    for version in version_matches:
                        if cell_latest is None or not comp_versions_ge(cell_latest, version):
                            cell_latest = version
                    
                    # Since this is the first non-empty row we found, use this as the latest
                    latest_version = cell_latest
                    break  # Stop processing rows since we found the latest version
        
        if not latest_version:
            return None, "No version numbers found in Linux columns of Microsoft documentation"
        
        # Compare with current version
        if comp_versions_ge(curr_version, latest_version):
            return None, None  # Current version is up to date
        else:
            return latest_version, None  # New version available
            
    except Exception as e:
        return None, "Error parsing version information from Microsoft documentation: {0}".format(str(e))
    return None, None

# 
def comp_versions_ge(version1, version2):
    """
    compare two versions, see if the first is newer than / the same as the second
    """
    versions1 = [int(v) for v in version1.split(".")]
    versions2 = [int(v) for v in version2.split(".")]
    for i in range(max(len(versions1), len(versions2))):
        v1 = versions1[i] if i < len(versions1) else 0
        v2 = versions2[i] if i < len(versions2) else 0
        if v1 > v2:
            return True
        elif v1 < v2:
            return False
    return True

def ask_update_old_version(ama_version, curr_ama_version):
    print("--------------------------------------------------------------------------------")
    print("You are currently running AMA Version {0}. There is a newer version\n"\
          "available which may fix your issue (version {1}).".format(ama_version, curr_ama_version))
    answer = get_input("Do you want to update? (y/n)", (lambda x : x.lower() in ['y','yes','n','no']),\
                       "Please type either 'y'/'yes' or 'n'/'no' to proceed.")
    # user does want to update
    if (answer.lower() in ['y', 'yes']):
        print("--------------------------------------------------------------------------------")
        print("Please follow the instructions given here:")
        print("\n    https://docs.microsoft.com/en-us/azure/azure-monitor/agents/azure-monitor-agent-manage\n")
        return USER_EXIT
    # user doesn't want to update
    elif (answer.lower() in ['n', 'no']):
        print("Continuing on with troubleshooter...")
        print("--------------------------------------------------------------------------------")
        return NO_ERROR

def check_ama(interactive):
    (ama_version, e) = get_package_version('azuremonitoragent')
    if e is not None:
        error_info.append((e,))
        return ERR_AMA_INSTALL

    ama_version = ama_version.split('-')[0]
    if not comp_versions_ge(ama_version, '1.21.0'):
        error_info.append((ama_version,))
        return ERR_OLD_AMA_VER

    print("Current AMA version: {0}".format(ama_version))
    (newer_ama_version, e) = get_latest_ama_version(ama_version)
    
    if newer_ama_version is None:
        if e is None:
            # No error and no newer version found - current version is up to date
            print("AMA version is up to date (latest version)")
            return NO_ERROR
        else:
            # There was an error fetching the latest version
            print("Unable to determine latest AMA version")
            print("Error: {0}".format(e))
            
            # Add error details to error_info for reporting
            error_info.append((e,))
            
            # Check if we have general internet connectivity
            checked_internet = check_internet_connect()
            if checked_internet != NO_ERROR:
                # No internet connectivity - this is a broader issue
                print("Internet connectivity test also failed. Skipping version check...")
                print("This may indicate broader network connectivity issues.")
                print("--------------------------------------------------------------------------------")
                return ERR_GETTING_AMA_VER  # Return error code for version check failure
            else:
                # Internet works but AMA version check failed - this might be specific to the documentation site
                print("Internet connectivity is working, but unable to access AMA documentation.")
                print("This could be due to firewall restrictions or temporary server issues.")
                print("The troubleshooter will continue, but version information may be outdated.")
                print("--------------------------------------------------------------------------------")
                return ERR_GETTING_AMA_VER  # Return error code for version check failure
    else:
        # Found a newer version available
        print("Update available: {0} -> {1}".format(ama_version, newer_ama_version))
        if interactive:
            if ask_update_old_version(ama_version, newer_ama_version) == USER_EXIT:
                return USER_EXIT

    return NO_ERROR