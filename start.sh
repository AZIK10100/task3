#!/bin/bash

python manage.py migrate
# python manage.py collectstatic --noinput

python manage.py run_bot &
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT