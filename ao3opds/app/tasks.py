''' Methods for sending tasks to the Celery worker process.

This is a standard pattern for supporting background tasks in a Flask
app via Celery. For more information, see the Flask documentation:
https://flask.palletsprojects.com/en/2.0.x/patterns/celery/
See also this helpful primer:
https://blog.miguelgrinberg.com/post/celery-and-the-flask-application-factory-pattern
'''

import datetime
import AO3
from ao3opds.app.db import get_db, load_ao3_session, dump_ao3_session
from ao3opds.app.feed import FEED_FETCH_METHODS
from . import celery

HIGH_PRIORITY = 2
LOW_PRIORITY = 1

# Update users and works daily. Update feeds more frequently.
USER_UPDATE_FREQUENCY = datetime.timedelta(days=1)
FEED_UPDATE_FREQUENCY = datetime.timedelta(hours=1)
WORK_UPDATE_FREQUENCY = datetime.timedelta(days=1)

# The pattern here splits every task into two methods: a method that
# runs synchronously in the Flask app's process and a method that runs
# asynchronously in the Celery worker's process.
#
# The Celery process method has a `@celery.task` decorator and, by
# convention, has a name of the form `methodname_async`.

@celery.task
def fetch_user_async(
        user_id, ao3_username, ao3_password,
        session=None, fetch_all=True, priority=HIGH_PRIORITY):
    """ Authenticates a user and stores credentials to the database. """
    db = get_db()

    # Attempt to authenticate with AO3:
    # raises `AO3.utils.LoginError`
    if session is not None:
        session = AO3.Session(ao3_username, ao3_password)
    # TODO: Handle failure.

    # Get the existing record, if any:
    user_record = db.execute(
        "SELECT * FROM ao3 WHERE user_id = ?", (user_id,)).fetchone()

    # Update the existing record if it exists:
    if user_record is not None:
        db.execute(
            "UPDATE ao3 SET username = ?, password = ?, session = ?,"
            " updated = CURRENT_TIMESTAMP WHERE user_id = ?",
            (ao3_username, ao3_password, dump_ao3_session(session), user_id))
    else:
        db.execute(
            "INSERT INTO ao3 (user_id, username, password, session)"
            " VALUES (?, ?, ?, ?)",
            (user_id, ao3_username, ao3_password, dump_ao3_session(session)))
    db.commit()  # Save changes to file

    # TODO: Check to see if the AO3 user account changed. If it did,
    # don't delete the feeds - instead, force updates (via a new `force`
    # parameter to `fetch_feeds` and related methods).

    if fetch_all:
        fetch_feeds(session, user_id, priority=priority)

    return session

def fetch_user(
        user_id, ao3_username, ao3_password,
        session=None, fetch_all=True, priority=HIGH_PRIORITY):
    """ Authenticates and stores a user's credentials asynchronously. """
    # NOTE: Can preprocess paramters here, e.g. by serializing `session`
    return fetch_user_async.apply_async(
        (user_id, ao3_username, ao3_password, session, fetch_all, priority),
        # TODO: Add other async params, e.g. retry (or define in decorator?)
        priority=priority)

def fetch_feeds(session, user_id, priority=HIGH_PRIORITY):
    """ Fetches a list of feeds for an authenticated user. """
    # Generate an async task for each feed:
    for feed_type in FEED_FETCH_METHODS:
        fetch_feed(session, user_id, feed_type, priority)

@celery.task
def fetch_feed_async(
        session, user_id, feed_type,
        fetch_all=True, priority=HIGH_PRIORITY):
    """ Fetches a feed for an authenticated user. """
    # TODO: Check for existing record of this feed_type for this user_id
    # and, if it exists, skip if it was recently updated.

    # TODO: Get a list of works for this feed (note that using the
    # FEED_FETCH_METHOD method won't work, as it fetches all the works
    # and renders to OPDS; will need to fetch just the non-loaded works)

    # TODO: Add feed record to the database. Need to update if there's
    # an existing record, or insert if no such record exists.

    # TODO: Spawn a task for each work, passing it this feed's ID.
    pass

def fetch_feed(
        session, user_id, feed_type,
        fetch_all=True, priority=HIGH_PRIORITY):
    """ Fetches a feed for an authenticated user. """
    # NOTE: Can preprocess parameters here, e.g. by serializing `session`
    return fetch_feed_async.apply_async(
        (session, user_id, feed_type, fetch_all, priority),
        # TODO: Add other async params, e.g. retry (or define in decorator?)
        priority=priority)

@celery.task
def fetch_work_async(session, feed_id, work_id):
    """ Fetches a work for a feed using an authenticated user session. """
    # TODO: Check for existing record of this work and, if it exists,
    # skip if it was recently updated.

    # TODO: Load an AO3.Work for `work_id` using `session`

    # TODO: Add work record to the database. Need to update if there's
    # an existing record, or insert if no such record exists.

    # TODO: Add records to category, author, and link tables, and relate
    # this work to them via work_author and work_category tables.
    pass

def fetch_work(
        session, feed_id, work_id, priority=HIGH_PRIORITY):
    """ Fetches a work for a feed using an authenticated user session. """
    # NOTE: Can preprocess parameters here, e.g. by serializing `session`
    return fetch_work_async.apply_async(
        (session, feed_id, work_id),
        # TODO: Add other async params, e.g. retry (or define in decorator?)
        priority=priority)
