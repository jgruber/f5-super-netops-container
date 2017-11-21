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
import keystoneclient.v3.client as ksclientv3
import keystoneclient.v2_0.client as ksclientv2
import keystoneauth1
import neutronclient.v2_0.client as netclient
import novaclient.client as compclient
import heatclient.client as heatclient

from neutronclient.common.exceptions import NotFound

def _get_keystone_session(project_name=None, version=3):
    if 'OS_AUTH_URL' not in os.environ:
        print ("Please set the OS_AUTH_URL environment variable"
               " or source your cloud rc file first.")
        sys.exit(1)
    if 'OS_USERNAME' not in os.environ:
        print ("Please set the OS_USERNAME environment variable"
               " or source your cloud rc file first.")
        sys.exit(1)
    if 'OS_PASSWORD' not in os.environ:
        print ("Please set the OS_PASSWORD environment variable"
               " or source your cloud rc file first.")
        sys.exit(1)
    project_domain_id = 'default'
    if 'OS_DOMAIN_ID' in os.environ:
        project_domain_id = os.environ['OS_DOMAIN_ID']
    user_domain_id = 'default'
    if 'OS_USER_DOMAIN_ID' in os.environ:
        user_domain_id = os.environ['OS_USER_DOMAIN_ID']
    tenant_name = 'admin'
    if 'OS_TENANT_NAME' in os.environ:
        tenant_name = os.environ['OS_TENANT_NAME']
    if not project_name:
        if 'OS_PROJECT_NAME' not in os.environ:
            project_name=tenant_name
        else:
            project_name=os.environ['OS_PROJECT_NAME']

    if version == 3:
        auth_url = str(os.environ['OS_AUTH_URL']).replace('2.0','3')
    else:
        auth_url = os.path.dirname(os.environ['OS_AUTH_URL']) + '/v2.0'
    from keystoneauth1.identity import v2, v3
    authv2 = v2.Password(username=os.environ['OS_USERNAME'],
                       password=os.environ['OS_PASSWORD'],
                       tenant_name=tenant_name,
                       auth_url=auth_url)
    authv3 = v3.Password(username=os.environ['OS_USERNAME'],
                       password=os.environ['OS_PASSWORD'],
                       project_name=project_name,
                       user_domain_id='default',
                       project_domain_id='default',
                       auth_url=auth_url)
    if version == 3:
        return keystoneauth1.session.Session(auth=authv3, verify=False)
    else:
        return keystoneauth1.session.Session(auth=authv2, verify=False)


def _get_keystone_client(version=3):
    if version == 2:
        return ksclientv2.Client(session=_get_keystone_session(version=2))
    else:
        return ksclientv3.Client(session=_get_keystone_session())

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


def _delete_stacks_in_tenant(tenant_id):
    try:
        hc = _get_heat_client(tenant_id=tenant_id)
        stacks = hc.stacks.list()
        for stack in stacks:
            tenant = kc.projects.get(stack.stack_user_project_id)
            if tenant.name.startswith(tenant_id):
                print "|- deleting stack %s" % stack.stack_name
                stack.delete()
                tries = 0
                while True:
                    stack.get()
                    if stack.stack_status == 'DELETE_COMPLETE':
                        return True
                    if stack.stack_status == 'DELETE_FAILED':
                        print "|--- delete stack %s failed" % stack.stack_name
                        return False
                    time.sleep(5)
                    tries += 1
                    if tries > 40:
                        print "|--- delete stack %s failed" % stack.stack_name
                        return False
    except NotFound:
		pass
    return True


def _delete_servers_in_tenant(tenant_id):
    try:
        cc = _get_nova_client()
        for server in cc.servers.list():
            if server.tenant_id == tenant_id:
                print "|- deleting server %s" % server.name
                tries = 0
                while True:
                    try:
                        server.delete()
                        return True
                    except:
                        print '|--- could not delete nova server %s' % server.id
                        return False
    except NotFound:
		pass
    return True


def _delete_floating_ips(tenant_id):
    try:
        nc = _get_neutron_client()
        for fip in nc.list_floatingips()['floatingips']:
            if fip['tenant_id'] == tenant_id:
                try:
                    nc.delete_floatingip(fip['id'])
                    return True
                except:
                    print '|--- could not delete floating IP %s' % fip['id']
                    return False
    except NotFound:
		pass
    return True


def _delete_routers(tenant_id):
    try:
        nc = _get_neutron_client()
        for router in nc.list_routers()['routers']:
            if router['tenant_id'] == tenant_id:
                print '|- deleting router %s' % router['id']
                print '|--- removing router gateway'
                nc.remove_gateway_router(router['id'])
                for port in nc.list_ports()['ports']:
                    if port['device_id'] == router['id']:
                        print '|--- remove router port %s' % port['id']
                        nc.remove_interface_router(
                                router['id'],{'port_id': port['id']})
                try:
                    nc.delete_router(router['id'])
                    return True
                except:
                    print '|--- could not delete router %s' % router['id']
                    return False
    except NotFound:
		pass
    return True


def _delete_loadbalancers(tenant_id):
    lbaas_deleted = True
    try:
        nc = _get_neutron_client()
        for lb in nc.list_lbaas_loadbalancers()['loadbalancers']:
            if lb.get('tenant_id') == tenant_id:
                print ('|- deleting loadbalancer %s' % lb.get('id'))
                # TODO: delete l7policies
                try:

                    for listener in lb.get('listeners'):
                        print "|--- delete listener %s" % listener.get('id')
                        nc.delete_listener(listener.get('id'))
                    for pool in lb.get('pools'):
                        pool = nc.show_lbaas_pool(pool['id']).get('pool')
                        if pool.get('healthmonitor_id'):
                            print "|--- delete monitor %s" % pool.get(
                                'healthmonitor_id')
                            nc.delete_lbaas_healthmonitor(
                                pool.get('healthmonitor_id'))
                        members = nc.list_lbaas_members(pool.get('id'))
                        for member in members:
                            print "|--- deleted member %s" % member.get('id')
                            nc.delete_lbaas_member(
                                member.get('id'), pool.get('id'))
                        print "|--- deleted pool %s" % pool.get('id')
                        nc.delete_lbaas_pool(pool.get('id'))

                    tries = 0
                    delete_failed = False
                    while True:
                        try:
                            if tries > 40:
                                print "X--- delete loadbalancer timed out"
                                delete_failed = True
                                raise Exception('timed out')
                            tries += 1
                            lb = nc.show_loadbalancer(
                                lb.get('id')).get('loadbalancer')
                            status = lb.get('provisioning_status')
                            if status.find('PENDING') == -1:
                                if status.find('DELETE') == -1:
                                    nc.delete_loadbalancer(lb.get('id'))
                                    time.sleep(2)
                                else:
                                    break
                            else:
                                time.sleep(2)
                                tries += 1
                        except:
                            if delete_failed:
                                raise Exception('timed out')
                except:
                    lbaas_deleted = False
    except NotFound:
        pass
    return lbaas_deleted


def _delete_networks(tenant_id):
    delete_networks = True
    try:
        nc = _get_neutron_client()
        for net in nc.list_networks()['networks']:
            if net['tenant_id'] == tenant_id:
                print ('|- deleting network %s' % net.get('id'))
                try:
                    already_deleted_ports = []
                    for port in nc.list_ports()['ports']:
                        if port['network_id'] == net['id']:
                            if not port['device_owner'].startswith('network'):
                                if 'trunk_details' in port:
                                    sub_ports = \
                                        port['trunk_details']['sub_ports']
                                    for port in sub_ports:
                                        print '|--- deleting sub_port %s' % port
                                        nc.delete_port(port)
                                        already_deleted_ports.append(port)
                                    trunk_id = port['trunk_details']['trunk_id']
                                    if trunk_id:
                                        print '|--- deleting trunk %s' % trunk_id
                                        nc.delete_trunk(trunk_id)
                                print '|--- deleting port %s' % port['id']
                                nc.delete_port(port['id'])
                            if port['device_owner'].startswith('network:f5'):
                                print '|--- deleting f5 port %s ' % port['id']
                                nc.delete_port(port['id'])
                    for subnet_id in net['subnets']:
                        print '|--- deleting subnet %s' % subnet_id
                        nc.delete_subnet(subnet_id)
                    nc.delete_network(net['id'])
                    print '|--- deleted network %s' % net['id']
                except:
                    print 'X--- could not delete network %s' % net['id']
                    delete_networks = False
    except NotFound:
        pass
    return delete_networks


def _delete_security_groups(tenant_id):
    try:
        nc = _get_neutron_client()
        for sg in nc.list_security_groups()['security_groups']:
            if sg['tenant_id'] == tenant_id:
                print "|- deleting security group %s" % sg['id']
                try:
                    nc.delete_security_group(sg['id'])
                except:
                    print 'X--- could not delete security group %s' % sg['id']
                    return False
    except NotFound:
		pass
    return True


def _delete_tenant_resources(tenant_id):
    tenant_deleted = True
    print "+ Delete project %s resources: " % tenant_id
    if not _delete_stacks_in_tenant(tenant_id):
        tenant_deleted = False
    if not _delete_servers_in_tenant(tenant_id):
        tenant_deleted = False
    if not _delete_floating_ips(tenant_id):
        tenant_deleted = False
    if not _delete_loadbalancers(tenant_id):
        tenant_deleted = False
    if not _delete_networks(tenant_id):
        tenant_deleted = False
    if not _delete_security_groups(tenant_id):
        tenant_deleted = False
    return tenant_deleted


def main():
    kc = _get_keystone_client()
    my_user_id = kc.users.find(name=os.environ['OS_USERNAME']).id
    admin_role_id = kc.roles.find(name='admin').id
    tenants_to_remove = []
    (exempt_tenants, tenants_to_remove) = _get_tenants()

    # assure tenant is not exempt and that they current user is
    # an admin in the project to delete or else remove skip
    # removal of the project
    proposed_tenants = list(tenants_to_remove)
    for tenant in proposed_tenants:
        if tenant in exempt_tenants:
            print "can not remove reserved tenant %s" % tenant
            tenants_to_remove.remove(tenant)
        else:
            try:
                kc.roles.grant(user=my_user_id,
                               project=tenant,
                               role=admin_role_id)
            except:
                print "can not remove tenant %s: admin not granted" % tenant
                tenants_to_remove.remove(tenant)

    print "\nDeleting %d OpenStack project(s)\n" % len(tenants_to_remove)

    tries = 0;
    while True:
        tenants_deleted = True
        for tenant_id in tenants_to_remove:
            try:
                tenant_resources_deleted = _delete_tenant_resources(tenant_id)
            except NotFound:
               tenants_deleted = False

            if tenant_resources_deleted:
                kc = _get_keystone_client()
                for t in kc.projects.list():
                    if t.id == tenant_id:
                        try:
                            t.delete()
                        except NotFound:
                            pass
            else:
                tenants_deleted = False
        if tenants_deleted:
            break
        else:
            time.sleep(2)
            tries += 1
            if tries > 40:
                print "ERROR: Giving up.. "


if __name__ == "__main__":
    main()
