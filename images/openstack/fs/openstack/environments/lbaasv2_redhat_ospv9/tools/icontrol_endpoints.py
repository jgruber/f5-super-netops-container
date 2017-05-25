import os, sys, re
import keystoneclient.v2_0.client as ksclient
import neutronclient.v2_0.client as netclient

def _strip_version(endpoint):
    """Strip version from the last component of endpoint if present."""
    if endpoint.endswith('/'):
        endpoint = endpoint[:-1]
    url_bits = endpoint.split('/')
    if re.match(r'v\d+\.?\d*', url_bits[-1]):
        endpoint = '/'.join(url_bits[:-1])
    return endpoint


def _get_keystone_client():
    return ksclient.Client(username=os.environ['OS_USERNAME'],
                           password=os.environ['OS_PASSWORD'],
                           tenant_name=os.environ['OS_TENANT_NAME'],
                           auth_url=os.environ['OS_AUTH_URL'])


def _get_neutron_client():
    keystone_client = _get_keystone_client()
    neutron_endpoint = _strip_version(
        keystone_client.service_catalog.url_for(
            service_type='network',
            endpoint_type='publicURL'
        )
    )
    return netclient.Client(endpoint_url=neutron_endpoint,
                            token=keystone_client.auth_token)
                            

def _get_icontrol_endpoints():
    nc = _get_neutron_client()
    agents = nc.list_agents()['agents']
    endpoints = {}
    for agent in agents:
        if agent['binary'] == 'f5-oslbaasv2-agent':
            iceps = agent['configurations']['icontrol_endpoints']
            for ice in iceps.keys():
                endpoints[ice] = 1
    print ",".join(endpoints.keys())
    

def main():
    _get_icontrol_endpoints()
    
if __name__ == "__main__":
    main()
