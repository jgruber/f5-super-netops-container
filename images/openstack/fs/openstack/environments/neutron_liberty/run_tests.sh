#!/bin/bash 

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

NOW=$(date +%Y_%m_%d_%H_%M_%S)
tempest run -t --blacklist-file $DIR/blacklist.txt
testr last --subunit | subunit2junitxml --output-to=${WORKINGDIRECTORY}/reports/${ENV}_${NOW}.xml

