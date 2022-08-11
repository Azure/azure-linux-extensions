import time
import datetime
import traceback
"""import shlex
import subprocess
from subprocess import * """
import json

try:
    from urllib.parse import urlparse #python3+
except ImportError:
    from urlparse import urlparse #python2
try:
    import http.client as httpclient #python3+
except ImportError:
    import httplib as httpclient #python2

# define IMDS uri and header
imds_uri = 'http://169.254.169.254/metadata/instance?api-version=2021-11-01'
imds_header = {
    "Metadata":"true"
}
imds_request_method = 'GET'

# HTTP call wrapper
def imds_http_call(method, http_uri, headers):
    imds_result_json = None
    try:
        uri_obj = urlparse(http_uri)
        http_connection = httpclient.HTTPConnection(uri_obj.hostname, timeout=60)
        if uri_obj.query is not None:
            http_connection.request(method=method, url=(uri_obj.path +'?'+ uri_obj.query), headers=headers)
        else:
            http_connection.request(method=method, url=(uri_obj.path), headers=headers)

        http_resp = http_connection.getresponse()

        if http_resp is not None:
                # cast to httpclient constants to int for python2 + python3 compatibility
                if http_resp.status != int(httpclient.OK) and http_resp.status != int(httpclient.ACCEPTED):
                    errorMsg = "IMDS request failed with HTTP status code: {0}".format(http_resp.status)
                    raise Exception(errorMsg)

                result_content = http_resp.read().decode('utf-8')
                imds_result_json = json.loads(result_content)
        else:
            raise Exception("No response from IMDS get request")

        return imds_result_json
    except Exception as e:
        errorMsg = "Failed to call IMDS http with error: {0}, stack trace: {1}".format(e, traceback.format_exc())
        print(errorMsg)
        raise e
    finally:
        http_connection.close()

def get_imds_metadata():
    retry_count_max = 3
    retry_count = 0
    imds_result_json = None
    while retry_count < retry_count_max:
        try:
            imds_result_json = imds_http_call(imds_request_method, imds_uri, imds_header)
            break
        except Exception as e:
            retry_count += 1
            print("Encountered exception while getting IMDS metadata")
            if retry_count < retry_count_max:
                time.sleep(5)  # sleep for 5 seconds before retrying.
            else:
                raise e

    return imds_result_json