#!/bin/bash
set -eux

rm -rf dist $HOME/.cache/aws_list_all/
python -m pip install --upgrade flake8 yapf pytest twine
python -m pip install -e .
aws_list_all --help
pytest
flake8
yapf -d -r aws_list_all/

rm -rf dist/
python -m build
twine check dist/*
twine upload dist/*
