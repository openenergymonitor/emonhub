#!/bin/bash
echo "EUID: $EUID"
emonhub_location=/home/pi/data/emonhub.conf
path=/home/pi/emonhub/conf/nodes

max=31
for var in `seq 2 $max`
do
  if ! grep "\[$var\]" $emonhub_location; then
    if [ -f $path/$var ]; then
      cat $path/$var >> $emonhub_location
      echo "">>$emonhub_location
      echo "Added node $var to emonhub.conf"
    fi
  else
    echo "Node $var already present"
  fi
done
