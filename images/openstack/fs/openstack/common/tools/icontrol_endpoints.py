#!/usr/bin/env python2
# coding=utf-8
# Copyright 2016 F5 Networks Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
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
