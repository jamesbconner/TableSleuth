# TPCH-DATAGEN
Used the tpch-datagen tool to create 100G of snappy compressed parquet data for the purpose of the test.

## Setup
- git clone https://github.com/gizmodata/tpch-datagen
- cd tpch-datagen
- python -m venv .venv
- . .venv/bin/activate
- pip install --upgrade pip setuptools wheel
- pip install --editable '.[dev]'
- export PYTHONPATH=$(pwd)/src


## Command
tpch-datagen --scale-factor 100 --num-chunks 20 --data-directory /Users/james/Code/TableSleuth/data/raw/ --compression-method snappy
