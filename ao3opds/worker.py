#!/usr/bin/env python
""" Provides a worker for running background tasks for ao3opds.app.

Run this as a separate process via:
`celery -A worker.celery worker`

For more information, see:
https://blog.miguelgrinberg.com/post/celery-and-the-flask-application-factory-pattern
"""
from ao3opds.app import celery, create_app

app = create_app()
app.app_context().push()
