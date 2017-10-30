#!/bin/bash

ENV=lbaasv2_newton
BASE_DIR=/openstack

enabled_var="enable_$ENV"

if [[ ! ${!enabled_var} == 1 ]]
then
    echo "$ENV disabled"
    exit 0
else
    echo "installing $ENV"
fi

DIR=$BASE_DIR/$ENV

# initialize the environment
cd $BASE_DIR/
tempest init $ENV
virtualenv $ENV
cp -R $BASE_DIR/environments/${ENV}/. $DIR/
cp $BASE_DIR/environments/${ENV}/init-$ENV $BASE_DIR/init-$ENV
chmod +x $BASE_DIR/init-$ENV 

# Get correct version of the software to test and
# copy to the working directory for the environemnt
mkdir $DIR/build
cd $DIR/build
git clone -b newton-eol https://github.com/openstack/neutron-lbaas.git
mv $DIR/build/neutron-lbaas/neutron_lbaas $DIR/
mv $DIR/build/neutron-lbaas/requirements.txt $DIR/neutron_lbaas/requirements.txt
mv $DIR/build/neutron-lbaas/test-requirements.txt $DIR/neutron_lbaas/test-requirements.txt

# keep tempest at 12.1.0 which is before test.py was refactored
sed -i '/tempest/d' $DIR/neutron_lbaas/test-requirements.txt
echo 'tempest==12.1.0 # Apache-2.0' >> $DIR/neutron_lbaas/test-requirements.txt

# get rid of the unused source and branches
rm -rf $DIR/build

# install in the virtualenv for the environment
cd $DIR
/bin/bash -c "cd $DIR \
              && source ./bin/activate \
              && pip install -r ./neutron_lbaas/requirements.txt \
              && pip install -r ./neutron_lbaas/test-requirements.txt \
              && mkdir $DIR/tempest \
              && cp -Rf $DIR/lib/python2.7/site-packages/tempest/* $DIR/tempest/ \
              && pip install --upgrade tempest f5-openstack-agent junitxml python-heatclient f5-sdk \
              && pip install python-keystoneclient python-glanceclient python-novaclient python-neutronclient python-heatclient"

# patch files
find $DIR/neutron_lbaas/tests/tempest/v2 -exec sed -i 's/127.0/128.0/g' {} \; 2>/dev/null

# clean up container files
find $DIR/tools -type f -exec chmod +x {} \;
chmod +x $DIR/run_tests.sh

# create reports directory
mkdir $DIR/reports

