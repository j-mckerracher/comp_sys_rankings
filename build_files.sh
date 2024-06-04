#!/bin/bash
echo "Using Python version:"
python3 --version

pip3 install -r requirements.txt
python3 manage.py collectstatic --noinput
