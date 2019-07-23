#!/bin/bash

dir=`dirname "$0"`
cd "$dir"

if [ ! -d env ]; then
  virtualenv -p python3 env
  . env/bin/activate
  pip install -r requirements.txt
else
  . env/bin/activate
fi

make -C src -s
export LD_LIBRARY_PATH=./src

python src/server.py ../image-browser-data/{mscoco,vg_100k,emoji,flaticon,perso}


