import imp
import os
import json
import time
from Common import CommonVariables

try:
    import http.client as httpclient #python3+
except ImportError:
    import httplib as httpclient #python2

import xml.etree.ElementTree as ET

class IMDSUtil(object):
    '''this class is used to get security type information from IMDS'''
    def __init__(self, logger):
        self.logger = logger
    
    def get_http_util(self):
        """
        Importing WAAgentUtil automatically causes unit tests to fail because WAAgentUtil
        tries to find and load waagent's source code right when you import it.
        And HttpUtil imports WAAgentUtil internally (again, causing unittests to fail very unproductively).
        Therefore putting the import here and mocking this method in the test helps the test proceed productively.
        """
        from HttpUtil import HttpUtil
        return HttpUtil(self.logger)

    def get_fault_reason(self, content_xml):
        '''This function parse the xml content '''
        try:
            xml_root = ET.fromstring(content_xml)
        except:
            self.logger.log("Exception occured while parsing error xml.")
            return "Unknown"
        detail_element = xml_root.find('Details')
        if detail_element is not None and (detail_element.text is not None and len(detail_element.text) > 0):
            return detail_element.text
        else:
            return "Unknown"

    
    def _get_security_type_IMDS_helper(self,http_util):
        retry_count_max = 3
        retry_count = 0
        imds_endpoint_uri = self.getUri(CommonVariables.IMDS_API_Version,CommonVariables.IMDS_SecurityProfile_subDir)   
        self.logger.log("IMDS end point url: {0}".format(imds_endpoint_uri))
        while retry_count<retry_count_max:
            try:
                result = http_util.Call(method ='GET',
                         http_uri=imds_endpoint_uri,
                         headers=CommonVariables.IMDS_msg_headers,
                         data = "",
                         use_https=False
                )
                if result is not None:
                    self.logger.log("{0} {1}".format(result.status,result.getheaders()))
                    result_content = result.read()
                    self.logger.log("result content is {0}".format(result_content))

                    http_util.connection.close()
                    if result.status != int(httpclient.OK) and result.status != int(httpclient.ACCEPTED):
                        reason = self.get_fault_reason(result_content)
                        raise Exception("IMDS call GET request was not accepted. Error: {0}".format(reason))
                    return result_content.decode()
                else:
                    raise Exception("No response from IMDS GET request.")
            except Exception as ex:
                retry_count += 1
                self.logger.log("Encountered exception from IMDS GET request to IMDS (attempt #{0}: \n{1}".format(str(retry_count),str(ex)))
                if retry_count<retry_count_max:
                    time.sleep(10) #sleep for 10 second before retyring
                else:
                    raise ex

    def getUri(self,api_version,subdirectory):
        '''This function creates IMDS Uri'''
        uri = "http://{0}".format(CommonVariables.static_IMDS_IP)
        uri = os.path.join(uri,subdirectory)
        uri = "{0}?api-version={1}".format(uri,api_version)
        return uri

    def get_security_type_IMDS(self):
        '''This function returns security type of VM.'''
        '''['','TrustedLaunch','ConfidentialVM']'''
        http_util = self.get_http_util()
        security_profile = json.loads(self._get_security_type_IMDS_helper(http_util=http_util))
        if not 'securityType' in security_profile:
            raise Exception("VM security profile does not have securityType.")
        return security_profile['securityType']


