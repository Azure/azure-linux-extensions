import json
import os
import sys
import requests
import adal

def check_e2e(hostname):
    with open('{}/parameters.json'.format(os.getcwd()), 'r') as f:
        parameters = f.read()
    parameters = json.loads(parameters)

    authority_url = parameters['authority host url'] + '/' + parameters['tenant']
    context = adal.AuthenticationContext(authority_url)
    token = context.acquire_token_with_client_credentials(
                parameters['resource'],
                parameters['app id'],
                parameters['app secret'])
                
    head = {'Authorization': 'Bearer ' + token['accessToken']}
    subscription = parameters['subscription']
    resource_group = parameters['resource group']
    workspace = parameters['workspace']
    url = ('https://management.azure.com/subscriptions/{}/resourcegroups/{}/'
           'providers/Microsoft.OperationalInsights/workspaces/{}/api/'
           'query?api-version=2017-01-01-preview').format(subscription, resource_group, workspace)

    sources = ['Syslog', 'Perf', 'Heartbeat', 'ApacheAccess_CL', 'MySQL_CL'] # custom ?
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
        timespan = 'PT1H'
        r = requests.post(url, headers=head, json={'query':query,'timespan':timespan})

        if r.status_code == requests.codes.ok:
            r = (json.loads(r.text)['Tables'])[0]
            if len(r['Rows']) < 1:
                results[distro][s] = 'Failure: no logs'
            else:
                results[distro][s] = 'Success'
        else:
            results[distro][s] = 'Failure: {} {}'.format(r.status_code, json.loads(r.text)['error']['message'])

    results[distro] = [results[distro]]
    print(results)
    with open('{}/e2eresults.json'.format(os.getcwd()), 'w+') as outfile:
        json.dump(results, outfile)
    return results

def main():
    if len(sys.argv) == 2:
        check_e2e(sys.argv[1])
    else:
        print('Hostname not provided')
        exit()

if __name__ == '__main__' :
    main()
