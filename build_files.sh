#!/bin/bash
echo "Updating and installing python"
sudo apt update
sudo apt install python3
echo "Using Python version:"
pip install -r requirements.txt
python3.12 manage.py collectstatic --noinput