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
import eventlet

eventlet.monkey_patch()

import os, sys, re, time, termios, tty
import argparse
import ConfigParser
from f5.bigip import ManagementRoot
from f5_openstack_agent.lbaasv2.drivers.bigip import system_helper
import requests
import sys


requests.packages.urllib3.disable_warnings()


def clean(bigip):
    sh = system_helper.SystemHelper()
    folders = bigip.tm.sys.folders.get_collection()
    for folder in folders:
        env="%s_" % bigip.environment_prefix
        if folder.name.startswith(env):
            if _yes_or_no("remove BIG-IP tenant folder %s?" % folder.name):
                print "removing BIG-IP tenant folder %s" % folder.name
                try:                                                      
                    vses = bigip.tm.ltm.virtuals.get_collection()    
                    for vs in vses:                                        
                        if vs.partition == folder.name:               
                            vs.delete()                                   
                    vaddrs = bigip.tm.ltm.virtual_address_s.get_collection()
                    for va in vaddrs:                                      
                        if va.partition == folder.name:               
                            va.delete()                                   
                    upps = bigip.tm.ltm.persistence.universals.get_collection()    
                    for upp in upps:                                               
                        if upp.partition == folder.name:              
                            upp.delete()                          
                    rules = bigip.tm.ltm.rules.get_collection(partition=folder.name)
                    for rule in rules:                                              
                        if rule.partition == folder.name:                           
                            rule.delete()                                           
                    sh.purge_folder_contents(bigip, folder=folder.name)     
                    sh.delete_folder(bigip, folder.name)                           
                except:                                                
                    current_folders = bigip.tm.sys.folders.get_collection()         
                    for cf in current_folders:                              
                        if cf.name == folder.name:                                 
                            raise     


def _yes_or_no(question):
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


def _getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def parse_args():
    parser = argparse.ArgumentParser(
        description='Utility to clear bigip',
    )
    parser.add_argument(
        '--config-file', help="Path to f5-openstack-agent.ini",
        metavar='config_file',
        required=True
    )
    return parser.parse_args()


def parse_config(config_file):
    config = ConfigParser.ConfigParser()
    config.readfp(open(config_file))

    bigips = []
    try:
        config_addrs = config.get("DEFAULT", 'icontrol_hostname')
        config_user = config.get("DEFAULT", 'icontrol_username')
        config_pass = config.get("DEFAULT", 'icontrol_password')
        config_env = config.get("DEFAULT", 'environment_prefix')
    except ConfigParser.NoOptionError as err:
        print(err.message)
        return bigips

    for config_addr in config_addrs.split(','):
        bigip = ManagementRoot(hostname=config_addr,
                                username=config_user,
                                password=config_pass)
        bigip.environment_prefix=config_env
        bigips.append(bigip)

    return bigips


def main(args):
    # Parse the config file
    bigips = parse_config(args.config_file)
    for bigip in bigips:
        try:
            clean(bigip)
        except Exception as err:
            print(err.message)


if __name__ == "__main__":
    sys.exit(main(parse_args()))
