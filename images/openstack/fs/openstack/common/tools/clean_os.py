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
import os, sys, re, time, termios, tty
import keystoneclient.v3.client as ksclient
import keystoneauth1
import neutronclient.v2_0.client as netclient
import novaclient.client as compclient
import heatclient.client as heatclient

from neutronclient.common.exceptions import NotFound

def _get_keystone_session(project_name=None):
    auth_url = str(os.environ['OS_AUTH_URL']).replace('2.0','3')
    project_domain_id = 'default'
    if 'OS_DOMAIN_ID' in os.environ:
        project_domain_id = os.environ['OS_DOMAIN_ID']
    user_domain_id = 'default'
    if 'OS_USER_DOMAIN_ID' in os.environ:
        user_domain_id = os.environ['OS_USER_DOMAIN_ID']
    from keystoneauth1.identity import v3 
    if not project_name:
        project_name=os.environ['OS_TENANT_NAME']
      
    auth = v3.Password(username=os.environ['OS_USERNAME'],
                       password=os.environ['OS_PASSWORD'],
                       project_name=project_name,
                       user_domain_id='default',
                       project_domain_id='default',
                       auth_url=auth_url)                 
    sess = keystoneauth1.session.Session(auth=auth, verify=False)
    return sess


def _get_keystone_client():
    return ksclient.Client(session=_get_keystone_session())


def _get_neutron_client():
    return netclient.Client(session=_get_keystone_session())


def _get_nova_client():
    return compclient.Client('2.1', session=_get_keystone_session())


def _get_heat_client(tenant_name=None, tenant_id=None):
    kc = _get_keystone_client()
    if tenant_id:
        tenant_name = kc.projects.get(tenant_id).name
    if not tenant_name:
        tenant_name = os.environ['OS_TENANT_NAME']
    if not tenant_id:
        tenant_id = kc.projects.find(name=tenant_name).id
    ks = _get_keystone_session(project_name=tenant_name)
    heat_sid = kc.services.find(type='orchestration').id
    heat_url = kc.endpoints.find(service_id=heat_sid, interface='public').url 
    heat_url = heat_url.replace('%(tenant_id)s',tenant_id)
    return heatclient.Client('1', endpoint=heat_url, token=ks.get_token())


def _getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def _yes_or_no(question):
    # reply = str(raw_input(question+' (y/n): ')).lower().strip()
    sys.stdout.write("%s [Y/N]: " % question)
    sys.stdout.flush()
    reply = str(_getch()).lower().strip()
    sys.stdout.write('%s\n' % reply)
    if reply[0] == 'y':
        return True
    if reply[0] == 'n':
        return False
    else:
        return _yes_or_no("Please enter y for yes or n for no: ")


def _get_tenants():
    kc = _get_keystone_client()
    tenants = kc.projects.list()
    tenants_to_remove = []
    exempt_tenants = ['admin','service']
    for tenant in tenants:
        if tenant.name not in exempt_tenants:
            if tenant.parent_id == 'default':
                if not _yes_or_no("remove %s project?" % tenant.name):
                    exempt_tenants.append(tenant.id)
                else:
                    tenants_to_remove.append(tenant.id)
            else:
                exempt_tenants.append(tenant.id)
        else:
            exempt_tenants.append(tenant.id)
    return (exempt_tenants, tenants_to_remove)


def main():
    kc = _get_keystone_client()
    my_user_id = kc.users.find(name=os.environ['OS_USERNAME']).id
    admin_role_id = kc.roles.find(name='admin').id
    tenants_not_to_remove = []    
    tenants_to_remove = []
    (exempt_tenants, tenants_to_remove) = _get_tenants()

    # assure user is an admin in the project to delete 
    # or else remove skip removal of the project
    proposed_tenants = list(tenants_to_remove)
    for tenant in proposed_tenants:
        try:
            kc.roles.grant(user=my_user_id,
                           project=tenant,
                           role=admin_role_id)
        except:
            print "can not remove tenant %s because admin not granted" % tenant
            if tenant not in tenants_not_to_remove:
                tenants_not_to_remove.append(tenant)
    
    # remove stacks in the tenants
    for tenant in tenants_to_remove:
        hc = _get_heat_client(tenant_id=tenant)
        stacks = hc.stacks.list()
        for stack in stacks:
            tenant = kc.projects.get(stack.stack_user_project_id)
            for tenant_id in tenants_to_remove:
                if tenant.name.startswith(tenant_id):
                    print "deleting stack %s" % stack.stack_name
                    stack.delete()
                    tries = 0
                    while True:
                        stack.get()
                        if stack.stack_status == 'DELETE_COMPLETE':
                            break
                        if stack.stack_status == 'DELETE_FAILED':
                            break
                        time.sleep(5)
                        tries += 1 
                        if tries > 40:
                            print "delete stack %s failed" % stack.stack_name
                            if not tenant in tenants_not_to_remove:
                                tenants_not_to_remove.append(tenant)
                            break

    # remove nova instances
    cc = _get_nova_client()
    try:
        for server in cc.servers.list():
            if server.tenant_id not in exempt_tenants:
                print "deleting server %s" % server.name
                try:
                    server.delete()
                except:
                    print 'could not delete nove server %s' % server.id
                    if server.tenant_id not in tenants_not_to_remove:
                        tenants_not_to_remove.append(server.tenant_id)
    except NotFound:
		pass
		
    # remove floating IPs
    nc = _get_neutron_client()
    try:
        for fip in nc.list_floatingips()['floatingips']:
            if fip['tenant_id'] not in exempt_tenants:
                try:
                    nc.delete_floatingip(fip['id'])
                except:
                    print 'could not delete floating IP %s' % fip['id']
                    if fip['tenant_id'] not in tenants_not_to_remove:
                        tenants_not_to_remove.append(fip['tenant_id'])
    except NotFound:
		pass
    
    # remove routers
    nc = _get_neutron_client()
    try:
        for router in nc.list_routers()['routers']:
            if router['tenant_id'] not in exempt_tenants:
                print 'remove router gateway'
                nc.remove_gateway_router(router['id'])
                for port in nc.list_ports()['ports']:
                    if port['device_id'] == router['id']:
                        print 'remove router port %s' % port['id']
                        nc.remove_interface_router(router['id'],{'port_id': port['id']})
                print 'deleting router %s' % router['id']
                try:
                    nc.delete_router(router['id'])
                except:
                    print 'could not delete router %s' % router['id']
                    if router['tenant_id'] not in tenants_not_to_remove:
                        tenants_not_to_remove.append(router['tenant_id'])
    except NotFound:
		pass
                    
    # remove lbaas pools
    nc = _get_neutron_client()
    try:
        for lbpool in nc.list_lbaas_pools()['pools']:
            if lbpool['tenant_id'] not in exempt_tenants:
                print 'deleting LBaaS pool %s' % lbpool['id']
                try:
                    nc.delete_lbaas_pool(lbpool['id'])
                except:
                    print 'could not delete lbaas pool %s' % lbpool['id']
                    if lbpool['tenant_id'] not in tenants_not_to_remove:
                        tenants_not_to_remove.append(lbpool['tenant_id'])
    except NotFound:
		pass
    
    # remove lbaas listeners
    nc = _get_neutron_client()
    try:
        for lblist in nc.list_listeners()['listeners']:
            if lblist['tenant_id'] not in exempt_tenants:
                print 'deleting LBaaS listener %s' % lblist['id']
                try:
                    nc.delete_listener(lblist['id'])
                except:
                    try:
                        ok_lb_status = ['ACTIVE', 'PENDING_DELETE', 'ERROR']
                        lbstatus = 'UNKNOWN'
                        tries = 0
                        while not lbstatus in ok_lb_status:
                            lbstatus = nc.show_loadbalancer(
                                lblist['loadbalancer_id']
                            )['loadbalancer']['provisioning_status'] 
                            nc.delete_loadbalancer(lblist['loadbalancer_id'])
                            time.sleep(5)
                            if tries > 10:
                                if not lblist['tenant_id'] in tenants_not_to_remove:
                                    tenants_not_to_remove.append(lblist['tenant_id'])
                                    raise Exception('failed to delete lb')
                        nc.delete_listener(lblist['id'])
                    except:
                        if not lblist['tenant_id'] in tenants_not_to_remove:
                            tenants_not_to_remove.append(lblist['tenant_id'])
                        print "could not delete lbaas listener %s" % lblist['id']
    except NotFound:
		pass

    # remove lbaas loadbalancer
    nc = _get_neutron_client()
    try:
        for lb in nc.list_loadbalancers()['loadbalancers']:
            if lb['tenant_id'] not in exempt_tenants:
                print 'deleting LBaaS loadbalancer %s' % lb['id']
                try:
                    nc.delete_loadbalancer(lb['id'])
                except:
                    print 'could not delete lbaas loadbalancer %s' % lb['id']
                    if not lb['tenant_id'] in tenants_not_to_remove:
                        tenants_not_to_remove.append(lb['tenant_id'])
    except NotFound:
		pass
    
    # remove networks
    nc = _get_neutron_client()
    try:
        for net in nc.list_networks()['networks']:
            if net['tenant_id'] not in exempt_tenants:
                try:
                    already_deleted_ports = []
                    for port in nc.list_ports()['ports']:
                        if port['network_id'] == net['id']:
                            if not port['device_owner'].startswith('network'):
                                if 'trunk_details' in port:
                                    sub_ports = port['trunk_details']['sub_ports']
                                    for port in sub_ports:
                                        print 'deleting sub_port %s' % port
                                        nc.delete_port(port)
                                        already_deleted_ports.append(port)
                                    trunk_id = port['trunk_details']['trunk_id']
                                    if trunk_id:
                                        print 'deleting trunk %s' % trunk_id
                                        nc.delete_trunk(trunk_id)
                                print 'deleting port %s' % port['id']
                                nc.delete_port(port['id'])
                            if port['device_owner'].startswith('network:f5'):
                                nc.delete_port(port['id'])
                    for subnet_id in net['subnets']:
                        print 'deleting subnet %s' % subnet_id
                        nc.delete_subnet(subnet_id)
                    print 'deleting network %s' % net['id']
                    nc.delete_network(net['id'])
                except:
                    print 'could not delete network %s' % net['id']
                    if not net['tenant_id'] in tenants_not_to_remove:
                        tenants_not_to_remove.append(net['tenant_id'])
    except NotFound:
		pass

    # remove security groups
    nc = _get_neutron_client()
    try:
        for sg in nc.list_security_groups()['security_groups']:
            if sg['tenant_id'] not in exempt_tenants:
                print "deleting security group %s" % sg['id']
                try:
                    nc.delete_security_group(sg['id'])
                except:
                    print 'could not delete security group %s' % sg['id']
                    if not sg['tenant_id'] in tenants_not_to_remove:
                        tenants_not_to_remove.append(sg['tenant_id'])
    except NotFound:
		pass
    
    # remove project
    kc = _get_keystone_client()
    tenants = kc.projects.list()
    for tenant in tenants:
        if tenant.id not in tenants_not_to_remove and tenant.id not in exempt_tenants:
            if tenant.id in tenants_to_remove:
                tenant.delete()

    
if __name__ == "__main__":
    main()