''' Methods for sending tasks to the Celery worker process.

This is a standard pattern for supporting background tasks in a Flask
app via Celery. For more information, see the Flask documentation:
https://flask.palletsprojects.com/en/2.0.x/patterns/celery/
See also this helpful primer:
https://blog.miguelgrinberg.com/post/celery-and-the-flask-application-factory-pattern
'''

from . import celery

HIGH_PRIORITY = 2
LOW_PRIORITY = 1

# The pattern here splits every task into two methods: a method that
# runs synchronously in the Flask app's process and a method that runs
# asynchronously in the Celery worker's process.
#
# The Celery process method has a `@celery.task` decorator and, by
# convention, has a name of the form `methodname_async`.

def update_user(username, password, session=None, priority=HIGH_PRIORITY):
    """ Stores a user to the database and fetches feeds for them. """
    # TODO: Check if the user was recently updated and, if not, refresh
    # their db record and spawn tasks to refresh their feeds:
    pass

def fetch_feeds(session, priority=HIGH_PRIORITY):
    """ Fetches a list of feeds for an authenticated user. """
    # TODO
    pass

@celery.task
def fetch_feed_async(user_id, feed_type, session=None, priority=HIGH_PRIORITY):
    """ Fetches a list of works and spawns tasks to load the works. """
    # TODO
    pass

def fetch_work(work_id, feed_id, session=None, priority=HIGH_PRIORITY):
    """ Fetches a work. """
    # TODO
    pass

@celery.task
def fetch_work_async(work_id, feed_id, session=None, priority=HIGH_PRIORITY):
    """ Fetches a work asynchronously. """
    # TODO
    pass
