#!/bin/bash

ENV=f5_nova_flavors
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
mkdir $DIR
cp -R $BASE_DIR/environments/${ENV}/. $DIR/
cp $BASE_DIR/environments/${ENV}/init-$ENV $BASE_DIR/init-$ENV
chmod +x $BASE_DIR/init-$ENV

