'''Verify end-to-end data transmission.'''

import json
import os
import re
import sys

import adal
import requests

ENDPOINT = ('https://management.azure.com/subscriptions/{}/resourcegroups/'
            '{}/providers/Microsoft.OperationalInsights/workspaces/{}/api/'
            'query?api-version=2017-01-01-preview')

def check_e2e(hostname):
    '''
    Verify data from computer with provided hostname is
    present in the Log Analytics workspace specified in
    parameters.json, append results to e2eresults.json
    '''
    global success_count
    global success_sources
    global failed_sources
    success_count = 0
    failed_sources = []
    success_sources = []

    with open('{0}/parameters.json'.format(os.getcwd()), 'r') as f:
        parameters = f.read()
        if re.search(r'"<.*>"', parameters):
            print('Please replace placeholders in parameters.json')
            exit()
        parameters = json.loads(parameters)
    
    tenant_id = str(json.loads(subprocess.check_output('az keyvault secret show --name tenant-id --vault-name {0}'.format(key_vault), shell=True))["value"])
    app_id = str(json.loads(subprocess.check_output('az keyvault secret show --name app-id --vault-name {0}'.format(key_vault), shell=True))["value"])
    app_secret = str(json.loads(subprocess.check_output('az keyvault secret show --name app-secret --vault-name {0}'.format(key_vault), shell=True))["value"])
    authority_url = parameters['authority host url'] + '/' + tenant_id
    context = adal.AuthenticationContext(authority_url)
    token = context.acquire_token_with_client_credentials(
        parameters['resource'],
        app_id,
        app_secret)

    head = {'Authorization': 'Bearer ' + token['accessToken']}
    subscription = str(json.loads(subprocess.check_output('az keyvault secret show --name susbscription-id --vault-name {0}'.format(key_vault), shell=True))["value"])
    resource_group = parameters['resource group']
    workspace = str(json.loads(subprocess.check_output('az keyvault secret show --name workspace-id --vault-name {0}'.format(key_vault), shell=True))["value"])
    url = ENDPOINT.format(subscription, resource_group, workspace)

    sources = ['Heartbeat', 'Syslog', 'Perf', 'ApacheAccess_CL', 'MySQL_CL', 'Custom_Log_CL']
    distro = hostname.split('-')[0]
    try:
        with open('{}/e2eresults.json'.format(os.getcwd()), 'r') as infile:
            try:
                results = json.load(infile)
            except ValueError:
                results = {}
    except IOError:
        results = {}
    results[distro] = {}

    print('Verifying data from computer {}'.format(hostname))
    for s in sources:
        query = '%s | where Computer == \'%s\' | take 1' % (s, hostname)
        timespan = 'P10Y'
        r = requests.post(url, headers=head, json={'query':query, 'timespan':timespan})

        if r.status_code == requests.codes.ok:
            r = (json.loads(r.text)['Tables'])[0]
            if len(r['Rows']) < 1:
                results[distro][s] = 'Failure: no logs'
                failed_sources.append(s)
            else:
                results[distro][s] = 'Success'
                success_count += 1
                success_sources.append(s)
        else:
            results[distro][s] = 'Failure: {} {}'.format(r.status_code, r.text)

    results[distro] = [results[distro]]
    print(results)
    with open('{}/e2eresults.json'.format(os.getcwd()), 'w+') as outfile:
        json.dump(results, outfile)
    return results

def main():
    '''Check for data with given hostname.'''
    if len(sys.argv) == 2:
        check_e2e(sys.argv[1])
    else:
        print('Hostname not provided')
        exit()

if __name__ == '__main__':
    main()
