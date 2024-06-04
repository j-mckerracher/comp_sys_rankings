#!/usr/bin/env bash
echo "Installing requirements"
pip install -r requirements.txt
python manage.py collectstatic