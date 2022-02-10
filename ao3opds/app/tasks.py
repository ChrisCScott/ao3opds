''' Methods for sending tasks to the Celery worker process.

This module provides background tasks to be run via Celery.

Typical usage will be: A method running in a Flask webserver process
will invoke `methodname_async` to cause the `methodname` task to be
executed asynchronously in a worker process. (`methodname` can be
executed synchronously if desired by calling it directly.)

For more information, see:
https://flask.palletsprojects.com/en/2.0.x/patterns/celery/
https://blog.miguelgrinberg.com/post/celery-and-the-flask-application-factory-pattern
https://docs.celeryproject.org/en/3.1/userguide/calling.html
'''

import datetime
import enum
from typing import Any
import AO3
from . import celery
from ao3opds.opds import AO3WorkOPDS, OPDSPerson, OPDSCategory, OPDSLink
from ao3opds.app.db import get_db, dump_ao3_session
from ao3opds.app.feed import (
    FEED_TYPE_BOOKMARKS, FEED_TYPE_HISTORY, FEED_TYPE_MARKED_FOR_LATER,
    FEED_TYPE_SUBSCRIPTIONS, FEED_TYPES)

# Define task priority levels:
HIGH_PRIORITY = 2  # Tasks requested by the webserver
LOW_PRIORITY = 1  # Tasks performed by background updater

# Update users and works daily. Update feeds more frequently.
USER_UPDATE_FREQUENCY = datetime.timedelta(days=1)
FEED_UPDATE_FREQUENCY = datetime.timedelta(hours=1)
WORK_UPDATE_FREQUENCY = datetime.timedelta(days=1)

# When loading multiple pages, this is the last page that will be loaded
# (indexed at 0, so a value of 20 means 21 pages will be loaded.)
MAX_PAGES_DEFAULT = 20

class FetchMode(enum.Enum):
    NO_FETCH = 0
    UPDATE_STALE = 1
    FORCE = 2

FETCH_MODES_DEFAULT = {
    'USER': FetchMode.UPDATE_STALE,
    'FEED': FetchMode.UPDATE_STALE,
    'WORK': FetchMode.UPDATE_STALE}

def ao3_user_to_db(user_id, ao3_username, ao3_password, session):
    """ Creates or updates an ao3 user record in the database """
    db = get_db()

    # Get the existing record, if any:
    user_record = db.execute(
        "SELECT * FROM ao3 WHERE (user_id = ?)", (user_id,)).fetchone()

    # Update the existing record if it exists:
    if user_record is not None:
        db.execute(
            "UPDATE ao3 SET username = ?, password = ?, session = ?,"
            " updated = CURRENT_TIMESTAMP WHERE (user_id = ?)",
            (ao3_username, ao3_password, dump_ao3_session(session), user_id))
    else:
        db.execute(
            "INSERT INTO ao3 (user_id, username, password, session)"
            " VALUES (?, ?, ?, ?)",
            (user_id, ao3_username, ao3_password, dump_ao3_session(session)))
    db.commit()  # Save changes to file

    new_user_record = db.execute(
        "SELECT * FROM ao3 WHERE (user_id = ?)", (user_id,)).fetchone()

    return (user_record, new_user_record)

@celery.task(bind=True)
def fetch_ao3_user(
        self, user_id, ao3_username, ao3_password, session=None,
        fetch_modes=FETCH_MODES_DEFAULT, priority=HIGH_PRIORITY):
    """ Authenticates a user and stores credentials to the database. """
    db = get_db()

    # Halt if we're being told not to fetch the user.
    if fetch_modes['USER'] == FetchMode.NO_FETCH:
        return session

    # Attempt to authenticate with AO3:
    # raises `AO3.utils.LoginError`
    if session is None or fetch_modes['USER'] == FetchMode.FORCE:
        session = AO3.Session(ao3_username, ao3_password)
    # TODO: Handle failure.

    # Create/update ao3 user record:
    (old_user_record, new_user_record) = ao3_user_to_db(
        user_id, ao3_username, ao3_password, session)
    ao3_user_id = new_user_record['id']

    # Check to see if the AO3 user account changed. If it did, don't
    # delete the feeds - instead, force updates on the feed.
    if (
            old_user_record is not None and
            old_user_record['user_id'] != ao3_username):
        fetch_modes = dict(fetch_modes)  # don't mutate input dict
        fetch_modes['FEED'] = FetchMode.FORCE

    # Fetch feeds for this user.
    # If this method was called asynchronously, generate a new async
    # task for each feed. Otherwise, iterate synchronously.
    if self.request.called_directly:
        fetch_feed_method = fetch_feed
    else:
        fetch_feed_method = fetch_feed_async
    for feed_type in FEED_TYPES:
        fetch_feed_method(
            session, ao3_user_id, feed_type,
            fetch_modes=fetch_modes, priority=priority)

    return session

def fetch_ao3_user_async(
        user_id, ao3_username, ao3_password,
        session=None, fetch_modes=FETCH_MODES_DEFAULT, priority=HIGH_PRIORITY):
    """ Authenticates and stores a user's credentials asynchronously. """
    # NOTE: Can preprocess paramters here, e.g. by serializing `session`
    return fetch_ao3_user.apply_async(
        args=(user_id, ao3_username, ao3_password),
        kwargs={
            'session':session, 'fetch_modes':fetch_modes, 'priority':priority},
        # TODO: Add other async params, e.g. retry (or define in decorator?)
        priority=priority)

def get_works(
        session: AO3.Session, feed_type: str, max_pages=MAX_PAGES_DEFAULT
    ) -> list[AO3.Work]:
    """ Fetches a list of (non-loaded) works for a feed of a given type. """
    if feed_type == FEED_TYPE_BOOKMARKS:
        return session.get_bookmarks(use_threading=True)
    elif feed_type == FEED_TYPE_HISTORY:
        # TODO: Determine whether to pass `timeout_sleep`
        # (Consider whether there's a way to trigger retries to fill in
        # more works from a user's history)
        return session.get_history(max_pages=max_pages)
    elif feed_type == FEED_TYPE_MARKED_FOR_LATER:
        # TODO: Determine whether to pass `timeout_sleep`
        return session.get_marked_for_later()
    elif feed_type == FEED_TYPE_SUBSCRIPTIONS:
        return session.get_work_subscriptions(use_threading=True)
    else:
        raise ValueError(
            'The `feed_type` value "' + feed_type + '" is not supported')

def match_works_to_records(
        works:list[AO3.Work], records:list
    ) -> tuple(dict[Any, AO3.Work], set(Any), set(AO3.Work)):
    """ Matches works to records. Also finds unmatched works and records
    
    Returns:
        A 3-tuple. The first entry is a mapping of records to works.
        The second entry is a set of unmatched records.
        The third entry is a set of unmatched works.
    """
    matched = dict()
    unmatched_works = set(works)
    unmatched_records = set(records)
    for work in works:
        for record in records:
            if work.id == record['work.work_id']:
                matched[record] = work
                unmatched_records.remove(record)
                unmatched_works.remove(work)
                break
    return (matched, unmatched_records, unmatched_works)

def feed_to_db(ao3_user_id, feed_type):
    """ Gets a feed record from the database, creating it if needed. """
    db = get_db()
    # Check for an existing record:
    feed_record = db.execute(
        'SELECT * FROM feed WHERE (user_id = ? AND feed_type = ?)',
        (ao3_user_id, feed_type)).fetchone()
    if feed_record is not None:
        return (feed_record, False)  # not updated
    # If the record doesn't exist, create it and then grab its id:
    db.execute(
        'INSERT INTO feed (user_id, feed_type) VALUES (?, ?)',
        (ao3_user_id, feed_type))
    db.commit()  # Save changes
    # Grab the updated record:
    feed_record = db.execute(
        'SELECT * FROM feed WHERE (user_id = ? AND feed_type = ?)',
        (ao3_user_id, feed_type)).fetchone()
    return (feed_record, True)  # updated

def update_feed_works(session, feed_type, feed_id, fetch_modes, priority):
    """ Removes """
    db = get_db()

    # Get the set of works for this feed from AO3:
    # TODO: Send this to a different task? If we fail on load, this task
    # will be retried, but it might be skipped since the feed will have
    # been recently updated (unless we can pass `force` on retry... but
    # we shouldn't do that, as it will flow down)
    # IDEA: Try this, and if it fails, update the db entry so that
    # updated=0 (which will cause a reattempt on next call.)
    works = set(get_works(session, feed_type))

    # Get the set of works for this feed from the database:
    work_records = set(db.execute(
        'SELECT work.id, work.work_id, work.feed_id, work.updated, '
        'feed_entry.id, feed_entry.updated '
        'FROM work JOIN feed_entry ON work.id = feed_entry.work_id '
        'WHERE (feed_entry.feed_id = ?)', (feed_id,)
    ).fetchall())

    # Separate the works and records into matched/unmatched groups:
    matched, unmatched_records, unmatched_works = match_works_to_records(
        works, work_records)

    # Remove unmatched records from this feed:
    for record in unmatched_records:
        db.execute(
            'DELETE FROM feed_entry WHERE (id = ?)', (record['feed_entry.id'],))
    db.commit()

    # If we're fetching everything, don't skip existing works:
    # TODO: Think about this. Should we include works already associated
    # with the feed in the update if (a) feed is set to UPDATE,
    # (b) feed is set to FORCE, (c) work is set to UPDATE,
    # (d) work is set to FORCE, or (e) always?
    if fetch_modes['WORK'] == FetchMode.FORCE:
        unmatched_works.update(matched.values())

    # Add new (and maybe existing) works to this feed:
    for work in unmatched_works:
        # Spawn a task for each work:
        fetch_work(
            session, feed_id, work.id,
            fetch_modes=fetch_modes, priority=priority)

@celery.task
def fetch_feed(
        session: AO3.Session, ao3_user_id, feed_type,
        fetch_modes=FETCH_MODES_DEFAULT, priority=HIGH_PRIORITY):
    """ Fetches a feed for an authenticated user. """
    db = get_db()
    update_threshold = datetime.datetime.now() - FEED_UPDATE_FREQUENCY

    # Check for existing record of this feed_type for this user_id:
    feed_record, feed_is_new = feed_to_db(ao3_user_id, feed_type)
    # If it exists and was recently updated, skip it:
    if (
            not feed_is_new and
            feed_record['updated'] > update_threshold and
            fetch_modes['FEED'] != FetchMode.FORCE):
        return session

    # Store this value for convenience:
    feed_id = feed_record['id']

    # Update the db records of works for this feed:
    update_feed_works(session, feed_type, feed_id, fetch_modes, priority)

    # The feed has been updated, so update its record accordingly:
    db.execute(
        "UPDATE feed SET updated = CURRENT_TIMESTAMP WHERE (feed_id = ?)",
        (feed_id,))

    return session

def fetch_feed_async(
        session, ao3_user_id, feed_type,
        fetch_modes=FETCH_MODES_DEFAULT, priority=HIGH_PRIORITY):
    """ Fetches a feed for an authenticated user. """
    # NOTE: Can preprocess parameters here, e.g. by serializing `session`
    return fetch_feed.apply_async(
        (session, ao3_user_id, feed_type, fetch_modes, priority),
        # TODO: Add other async params, e.g. retry (or define in decorator?)
        priority=priority)

def link_work_to_feed(work_id, feed_id):
    """ Creates or updates a `feed_entry` row to link a work to a feed.
    
    Note that `work_id` references the `id` field of the `work` table
    (not `work.work_id`!)
    """
    db = get_db()
    # Look for an existing linking record:
    feed_entry_record = db.execute(
        'SELECT * from feed_entry WHERE (feed_id = ?, work_id = ?)',
    # If no existing record, insert one:
    if feed_entry_record is None:
        db.execute(
            'INSERT INTO feed_entry (feed_id, work_id) VALUES (?, ?)',
            (feed_id, work_id))
    # If there is an existing record, update it:
    else:
        db.execute(
            'UPDATE feed_entry SET updated = CURRENT_TIMESTAMP '
            'WHERE (work_id = ? AND feed_id = ?)',
            (work_id, feed_id))
    db.commit()
    # Return Collect the new/updated record to return to the user:
    return db.execute(
        'SELECT * FROM feed_entry WHERE (work_id = ?, feed_id = ?)',
        (work_id, feed_id)).fetchone()

def link_author_to_work(author: OPDSPerson, work_id):
    """ Links an author record to a work record in the database. """
    db = get_db()
    # Look for an existing author record matching this author:
    author_record = db.execute(
        'SELECT * FROM author WHERE (name = ?, email = ?, uri = ?)',
        (author.name, author.email, author.uri)).fetchone()
    # TODO: If no existing record, insert one:
    # TODO: If there is an existing record, update it:
    # TODO: Look for an existing linking record connecting this author
    # to this work.
    # TODO: Add a linking record if one does not yet exist:

def link_category_to_work(category: OPDSCategory, work_id):
    """ Links a category record to a work record in the database. """
    db = get_db()
    # Look for an existing category record matching this category:
    category_record = db.execute(
        'SELECT * FROM category WHERE (term = ?, scheme = ?, label = ?)',
        (category.term, category.scheme, category.label)).fetchone()
    # TODO: If no existing record, insert one:
    # TODO: If there is an existing record, update it:
    # TODO: Look for an existing linking record connecting this category
    # to this work.
    # TODO: Add a linking record if one does not yet exist:

def link_link_to_work(link: OPDSLink, work_id):
    """ Links a link record to a work record in the database. """
    db = get_db()
    # Look for an existing category record matching this category:
    category_record = db.execute(
        'SELECT * FROM link WHERE (href = ? AND rel = ? AND link_type = ?)',
        (link.href, link.rel, link.type)).fetchone()
    # TODO: If no existing record, insert one:
    # TODO: If there is an existing record, update it:

def work_to_db(work: AO3.Work, work_id=None):
    """ Creates or updates a work record in the database """
    db = get_db()
    # Use our OPDS code to convert the AO3 data into the fields we want:
    opds_work = AO3WorkOPDS(work)
    values = (
        opds_work.id, opds_work.title, opds_work.updated, opds_work.language,
        opds_work.publisher, opds_work.summary)
    # Insert or update the work:
    if work_id is None:  # Work doesn't exist; insert a new one.
        cursor = db.execute(
            'INSERT INTO work (work_id, title, work_updated, '
            'work_language, publisher, summary) '
            'VALUES (?, ?, ?, ?, ?, ?)', values)
        work_id = cursor.lastrowid
    else:  # Work exists; update it.
        db.execute(
            'UPDATE work SET work_id = ?, title = ?, work_updated = ?, '
            'work_language = ?, publisher = ?, summary = ? '
            'WHERE (id = ?)', values + (work_id,))
    # Add author/category/link records for this work
    for author in opds_work.authors:
        link_author_to_work(author, work_id)
    for category in opds_work.categories:
        link_category_to_work(category, work_id)
    for link in opds_work.links:
        link_link_to_work(link, work_id)

    db.commit()  # Save changes
    # Load the inserted/updated record and return it:
    work_record = db.execute(
        'SELECT * FROM work WHERE (id = ?)', (work_id,)).fetchone()
    return work_record

@celery.task
def fetch_work(session, feed_id, ao3_work_id, fetch_modes=FETCH_MODES_DEFAULT):
    """ Fetches a work for a feed using an authenticated user session. """
    db = get_db()
    update_threshold = datetime.datetime.now() - FEED_UPDATE_FREQUENCY

    # Check for existing record of this work and a feed-work connection:
    work_record = db.execute(
        'SELECT * FROM work WHERE (work_id = ?)',(ao3_work_id,)).fetchone()

    # If the work exists, ensure that it is associated with the feed:
    # (We do this now to avoid dataloss if we fail to load the work)
    if work_record is not None:
        feed_entry_record = link_work_to_feed(work_record['id'], feed_id)
    else:
        feed_entry_record = None

    # If the work exists and was recently updated, skip it:
    if (
            work_record is not None and
            work_record['updated'] > update_threshold and
            fetch_modes['WORK'] != FetchMode.FORCE):
        return session

    # Load an AO3.Work for `work_id` using `session`
    # TODO: use try-except to deal with errors/rate-limiting (retry?)
    work = AO3.Work(
        ao3_work_id, session=session, load=True, load_chapters=False)

    # Add work record to the database.
    # (This also adds dependent author/category/link records)
    work_id = work_record['id'] if work_record is not None else None
    work_record = work_to_db(work, work_id)

    # If the work is newly-added, link it to the feed:
    if feed_entry_record is None:
        link_work_to_feed(work_record['id'], feed_id)

    return session

def fetch_work_async(
        session, feed_id, ao3_work_id,
        fetch_modes=FETCH_MODES_DEFAULT, priority=HIGH_PRIORITY):
    """ Fetches a work for a feed using an authenticated user session. """
    # NOTE: Can preprocess parameters here, e.g. by serializing `session`
    return fetch_work.apply_async(
        args=(session, feed_id, ao3_work_id),
        kwargs={'fetch_modes':fetch_modes},
        # TODO: Add other async params, e.g. retry (or define in decorator?)
        priority=priority)
