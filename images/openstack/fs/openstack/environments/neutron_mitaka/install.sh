#!/bin/bash

ENV=neutron_mitaka
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

# mitaka-eol version of neutron-lbaas
cd $DIR/build

git clone -b mitaka-eol https://github.com/openstack/neutron.git
cd $DIR/build/neutron
mv $DIR/build/neutron/neutron $DIR/neutron
mv $DIR/build/neutron/requirements.txt $DIR/neutron/requirements.txt
mv $DIR/build/neutron/test-requirements.txt $DIR/neutron/test-requirements.txt

# get rid of the unused source and branches
rm -rf $DIR/build

# install in the virtualenv for the environment
cd $DIR
/bin/bash -c "cd $DIR \
              && source ./bin/activate \
              && pip install -r ./neutron/requirements.txt \
              && pip install -r ./neutron/test-requirements.txt \
              && pip install 'tempest>=11.0.0,<12.1.0' \
              && mkdir $DIR/tempest \
              && cp -Rf $DIR/lib/python2.7/site-packages/tempest/* $DIR/tempest/ \
              && pip install --upgrade tempest junitxml python-heatclient"

# clean up container files
find $DIR/tools -type f -exec chmod +x {} \;
chmod +x $DIR/run_tests.sh

# create reports directory
mkdir $DIR/reports

