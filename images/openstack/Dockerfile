############################################################
# Dockerfile to build f5-super-netops enablement container
# Based on Alpine Linux, seasoned with OpenStack clients 
# and testing libraries
############################################################

# Start with an awesome, tiny Linux distro.
FROM f5devcentral/f5-super-netops-container:base

LABEL maintainer "h.patel@f5.com, n.pearce@f5.com"

# Set the SNOPS image name
ENV SNOPS_IMAGE openstack

# Copy in base FS from repo
COPY fs /

#Add libraries to compile ansible
RUN apk add --update gcc python2-dev linux-headers libc-dev libffi libffi-dev openssl openssl-dev py-virtualenv util-linux

#install ansible
RUN pip install f5-sdk netaddr python-openstackclient python-keystoneclient python-neutronclient python-heatclient Tempest 
RUN pip install ipython


# add interesting f5 tools
RUN git clone -b mitaka https://github.com/F5Networks/f5-openstack-agent.git
RUN pip install /f5-openstack-agent/
RUN rm -rf /f5-openstack-agent

# Uncomment the ENV setting to enable specific testing environments

# test that neutron has extension to support F5 LBaaS and other multi-tenant service
ENV enable_validate_neutron_for_f5_services=1

# test neutron in a liberty openstack cloud
ENV enable_neutron_liberty=0

# test neutron lbaasv2 in a liberty openstack cloud 
ENV enable_lbaasv2_liberty=0

# test neutron in a mitaka openstack cloud
ENV enable_neutron_mitaka=1

# test neutron lbaasv2 in a mitaka openstack cloud 
ENV enable_lbaasv2_mitaka=1

# test f5 lbaasv2 in a mitaka openstack cloud
ENV enable_lbaasv2_f5driver_mitaka=1

# test neutron in a newton openstack cloud
ENV enable_neutron_newton=1

# test neutron lbaasv2 in a newton openstack cloud 
ENV enable_lbaasv2_newton=1

# test neutron in a ocata openstack cloud
ENV enable_neutron_ocata=0

# test neutron lbaasv2 in a ocata openstack cloud 
ENV enable_lbaasv2_ocata=0

# create TMOS Virtual Edition images for OpenStack
ENV enable_image_importer=1

# create Nova Flavor for TMOS Virtual Editions
ENV enable_f5_nova_flavors=1

RUN /openstack/environments/install.sh

WORKDIR /openstack
# run interactively
ENV PS1="SNOPS OpenStack> "

CMD /bin/bash 

