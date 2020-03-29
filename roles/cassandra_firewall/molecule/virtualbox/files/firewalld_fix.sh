#!/usr/bin/env bash
# Fix firewalld on RedHat docker instances
# https://vander.host/knowledgebase/operating-systems/failed-to-load-nf_conntrack-module-when-starting-firewalld/

set -e;
set -u;

mkdir -p "/lib/modules/$(uname -r)";
touch "/lib/modules/$(uname -r)/modules.{builtin,order}";

for i in /sys/module/*;
do
echo "kernel/${i##**/}.ko";
done >> "/lib/modules/$(uname -r)/modules.builtin"
