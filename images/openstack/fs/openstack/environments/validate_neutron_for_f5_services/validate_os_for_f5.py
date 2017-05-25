import os, sys, re, time, termios, tty
import keystoneclient.v3.client as ksclient
from keystoneauth1 import identity
from keystoneauth1 import session
import neutronclient.v2_0.client as netclient
import novaclient.client as compclient
import heatclient.client as heatclient


def _get_keystone_session(project_name=None):
    
    if str(os.environ['OS_AUTH_URL']).find('2.0') > 0:
        auth = identity.v2.Password(
            username=os.environ['OS_USERNAME'],
            password=os.environ['OS_PASSWORD'],
            tenant_name=os.environ['OS_TENANT_NAME'],
            auth_url=os.environ['OS_AUTH_URL']
        )
    elif str(os.environ['OS_AUTH_URL']).find('v2') > 0:
        auth = identity.v2.Password(
            username=os.environ['OS_USERNAME'],
            password=os.environ['OS_PASSWORD'],
            tenant_name=os.environ['OS_TENANT_NAME'],
            auth_url=os.environ['OS_AUTH_URL']
        )
    elif str(os.environ['OS_AUTH_URL']).find('v3') > 0:
        project_domain_name = 'default'
        user_domain_name = 'default'
        project_name = 'admin'

        if 'OS_DOMAIN_ID' in os.environ:
            project_domain_id = os.environ['OS_DOMAIN_ID']
        if 'OS_USER_DOMAIN_ID' in os.environ:
            user_domain_id = os.environ['OS_USER_DOMAIN_ID']
        if 'OS_PROJECT_NAME' in os.environ:
            project_name=os.environ['OS_PROJECT_NAME']
        elif 'OS_TENANT_NAME' in os.environ:
            project_name=os.environ['OS_TENANT_NAME']

        auth = identity.v3.Password(
            username=os.environ['OS_USERNAME'],
            user_domain_name=user_domain_name,
            password=os.environ['OS_PASSWORD'],
            project_domain_name=project_domain_name,
            project_name=project_name,
            auth_url=os.environ['OS_AUTH_URL']
        )
    
    sess = session.Session(auth=auth, verify=False)
    return sess


def _get_neutron_client():
    return netclient.Client(session=_get_keystone_session())


def _get_neutron_extensions():
    nc = _get_neutron_client()
    return nc.list_extensions()['extensions']
    

def main():

    extensions = _get_neutron_extensions()
    
    has_agent = False
    has_provider_net = False
    has_binding = False
    has_router = False
    has_ha = False
    has_lbaasv2 = False
    has_l7 = False

    for ext in extensions:
        if ext['alias'] == 'agent':
            has_agent = True
        if ext['alias'] == 'provider':
            has_provider_net = True
        if ext['alias'] == 'binding':
            has_binding = True
        if ext['alias'] == 'router':
            has_router = True
        if ext['alias'] == 'allowed-address-pairs':
            has_ha = True
        if ext['alias'] == 'lbaasv2':  
            has_lbaasv2 = True
        if ext['alias'] == 'l7':
            has_l7 = True

    eligible = True

    if has_agent:
        print "PASS: Neutron supports the agent reporting API"
    else:
        eligible = False
        print "FAIL: Neutron does not support the agent reporting API"

    if has_provider_net:
        print "PASS: Neutron supports provider networks of known types"
    else:
        eligible = False
        print "FAIL: Neutron does not support provider network of known types"

    if has_binding:
        print "PASS: Neutron supports port binding"
    else:
        eligible = False
        print "FAIL: Neutron does not support port binding"

    if has_router:
        print "PASS: Neutron supports logical routers"
    else:
        eligible = False
        print "FAIL: Neutron does not logical routers"

    if has_ha:
        print "PASS: Neutron supports L2 failover clusters"
    else:
        eligible = False
        print "FAIL: Neutron does not support L2 failover clusters"

    if has_lbaasv2:
        print "PASS: Neutron supports LBaaSv2"
    else:
        print "WARNING: Neutron does not support LBaaSv2"

    if has_l7:
        print "PASS: Neutron supports LBaaSv2 L7 rules"
    else:
        print "WARNING: Neutron does not support LBaaSv2 L7 rules"
        
        
    if not eligible:
        print "NEUTRON DOES NOT SUPPORT REQUIRED EXTENSIONS FOR F5 MULTI-TENANT SERVICES"
    else:
        print "NEUTRON SUPPORTS ALL REQUIRED EXTENSIONS FOR F5 MULTI-TENANT SERVICES"
        if not has_lbaasv2:
            print "Neutron does not have LBaaSv2 installed yet."


if __name__ == "__main__":
    main()
