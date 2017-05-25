#!/bin/bash

ENV=lbaasv2_f5driver_mitaka
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
git clone -b mitaka https://github.com/F5Networks/f5-openstack-lbaasv2-driver.git
cp -R $DIR/build/f5-openstack-lbaasv2-driver/f5lbaasdriver $DIR/

# install in the virtualenv for the environment
cd $DIR
echo `pwd`
/bin/bash -c "cd $DIR \
              && source ./bin/activate \
              && cd build/f5-openstack-lbaasv2-driver \
              && pip install --upgrade -r requirements.test.txt \
              && cd ../.. \
              && mkdir tempest \
              && cp -Rf ./lib/python2.7/site-packages/tempest/* ./tempest/ \
              && pip install --upgrade f5-openstack-agent tempest junitxml python-heatclient \
              && pip install --upgrade f5-openstack-test f5-sdk \
              && pip install python-keystoneclient python-glanceclient python-novaclient python-neutronclient python-heatclient"


# get rid of the unused source and branches
rm -rf $DIR/build

# clean up container files
find $DIR/tools -type f -exec chmod +x {} \;
chmod +x $DIR/run_tests.sh

