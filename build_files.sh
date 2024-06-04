#!/bin/bash
echo "Using Python version:"
pip install -r requirements.txt
python3.12 manage.py collectstatic --noinput