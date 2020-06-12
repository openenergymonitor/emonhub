#!/bin/bash
homedir=$1

# default
if [ "$homedir" = "" ]; then
  homedir="/home/pi"
fi

emonhub_location=/etc/emonhub/emonhub.conf
path=$homedir/emonhub/conf/nodes

if [ ! -d $path ]; then
  echo "$path directory does not exist"
  exit 0
fi

if [ ! -f $emonhub_location ]; then
  echo "emonhub location does not exist"
  exit 0
fi

max=31
for var in `seq 2 $max`
do
  if grep "^\[\[$var\]\]" $emonhub_location; then
    echo "Node $var already present"
  else
    if [ -f $path/$var ]; then
      echo "">>$emonhub_location
      cat $path/$var >> $emonhub_location
      echo "Added node $var to emonhub.conf"
    fi
  fi
done
