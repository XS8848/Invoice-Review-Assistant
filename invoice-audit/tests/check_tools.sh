#!/usr/bin/env bash
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH
PY=/conda/miniconda3/envs/SF157/bin/python
$PY -c "import pytest, locust; print('pytest', pytest.__version__, '| locust', locust.__version__)"
