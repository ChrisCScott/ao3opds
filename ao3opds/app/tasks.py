''' Methods for sending tasks to the Celery worker process.

This is a standard pattern for supporting background tasks in a Flask
app via Celery. For more information, see the Flask documentation:
https://flask.palletsprojects.com/en/2.0.x/patterns/celery/
See also this helpful primer:
https://blog.miguelgrinberg.com/post/celery-and-the-flask-application-factory-pattern
'''

import datetime
from typing import Any
import AO3
from ao3opds.opds import AO3WorkOPDS, OPDSPerson, OPDSCategory, OPDSLink
from ao3opds.app.db import get_db, load_ao3_session, dump_ao3_session
from ao3opds.app.feed import (
    FEED_TYPE_BOOKMARKS, FEED_TYPE_HISTORY, FEED_TYPE_MARKED_FOR_LATER,
    FEED_TYPE_SUBSCRIPTIONS)
from . import celery

HIGH_PRIORITY = 2
LOW_PRIORITY = 1

# Update users and works daily. Update feeds more frequently.
USER_UPDATE_FREQUENCY = datetime.timedelta(days=1)
FEED_UPDATE_FREQUENCY = datetime.timedelta(hours=1)
WORK_UPDATE_FREQUENCY = datetime.timedelta(days=1)

# When loading multiple pages, this is the last page that will be loaded
# (indexed at 0, so a value of 20 means 21 pages will be loaded.)
MAX_PAGES_DEFAULT = 20

# The pattern here splits every task into two methods: a method that
# runs synchronously in the Flask app's process and a method that runs
# asynchronously in the Celery worker's process.
#
# The Celery process method has a `@celery.task` decorator and, by
# convention, has a name of the form `methodname_async`.

@celery.task
def fetch_user_async(
        user_id, ao3_username, ao3_password,
        session=None, fetch_all=True, force=False, priority=HIGH_PRIORITY):
    """ Authenticates a user and stores credentials to the database. """
    db = get_db()

    # Attempt to authenticate with AO3:
    # raises `AO3.utils.LoginError`
    if session is None or force:
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
        for feed_type in FEED_FETCH_METHODS:
            fetch_feed(session, user_id, feed_type, fetch_all, priority)

    return session

def fetch_user(
        user_id, ao3_username, ao3_password,
        session=None, fetch_all=True, force=False, priority=HIGH_PRIORITY):
    """ Authenticates and stores a user's credentials asynchronously. """
    # NOTE: Can preprocess paramters here, e.g. by serializing `session`
    return fetch_user_async.apply_async(
        args=(user_id, ao3_username, ao3_password),
        kwargs={
            'session':session, 'fetch_all':fetch_all, 'force':force,
            'priority':priority},
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

@celery.task
def fetch_feed_async(
        session: AO3.Session, user_id, feed_type,
        fetch_all=True, force=False, priority=HIGH_PRIORITY):
    """ Fetches a feed for an authenticated user. """
    db = get_db()
    update_threshold = datetime.datetime.now() - FEED_UPDATE_FREQUENCY

    # Check for existing record of this feed_type for this user_id:
    feed_record = db.execute(
        'SELECT * FROM feed WHERE (user_id = ? and feed_type = ?)',
        (user_id, feed_type)).fetchone()
    # If the record doesn't exist, create it and then grab its id:
    if feed_record is None:
        db.execute(
            'INSERT INTO feed (user_id, feed_type) VALUES (?, ?)',
            (user_id, feed_type))
        db.commit()  # Save changes
        feed_record = db.execute(
            'SELECT * FROM feed WHERE (user_id = ? and feed_type = ?)',
            (user_id, feed_type)).fetchone()
    # If it exists and was recently updated, skip it:
    elif feed_record['updated'] > update_threshold and not force:
        return session

    # Store this value for convenience:
    feed_id = feed_record['id']

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
        'WHERE feed_entry.feed_id = ?', (feed_id,)
    ).fetchall())

    # Separate the works and records into matched/unmatched groups:
    matched, unmatched_records, unmatched_works = match_works_to_records(
        works, work_records)

    # Remove unmatched records from this feed:
    for record in unmatched_records:
        db.execute(
            'DELETE FROM feed_entry WHERE id = ?', (record['feed_entry.id'],))
    db.commit()

    # If we're fetching everything, don't skip existing works:
    if fetch_all:
        unmatched_works.update(matched.values())
    # Add new (and maybe existing) works to this feed:
    for work in unmatched_works:
        # Spawn a task for each work:
        fetch_work(session, feed_id, work.id, force=force, priority=priority)

    return session

def fetch_feed(
        session, user_id, feed_type,
        fetch_all=True, force=False, priority=HIGH_PRIORITY):
    """ Fetches a feed for an authenticated user. """
    # NOTE: Can preprocess parameters here, e.g. by serializing `session`
    return fetch_feed_async.apply_async(
        (session, user_id, feed_type, fetch_all, priority),
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
        'SELECT * from feed_entry WHERE (work_id = ?, feed_id = ?)',
        (work_id, feed_id)).fetchone()
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
        'SELECT * FROM link WHERE (href = ?, rel = ?, link_type = ?)',
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
        'SELECT * FROM work WHERE id = ?', (work_id,)).fetchone()
    return work_record

@celery.task
def fetch_work_async(session, feed_id, ao3_work_id, force=False):
    """ Fetches a work for a feed using an authenticated user session. """
    db = get_db()
    update_threshold = datetime.datetime.now() - FEED_UPDATE_FREQUENCY

    # Check for existing record of this work and a feed-work connection:
    work_record = db.execute(
        'SELECT * FROM work WHERE work_id = ?',(ao3_work_id,)).fetchone()

    # If the work exists, ensure that it is associated with the feed:
    # (We do this now to avoid)
    if work_record is not None:
        feed_entry_record = link_work_to_feed(work_record['id'], feed_id)
    else:
        feed_entry_record = None

    # If the work exists and was recently updated skip it:
    if work_record is not None and work_record['updated'] > update_threshold:
        return session

    # Load an AO3.Work for `work_id` using `session`
    # TODO: use try-except to deal with errors/rate-limiting (retry?)
    work = AO3.Work(
        ao3_work_id, session=session, load=True, load_chapters=False)

    # Add work record to the database. Need to update if there's
    # an existing record, or insert if no such record exists.
    if work_record is None: # Insert if no existing record
        pass
    # TODO: Add records to category, author, and link tables, and relate
    # this work to them via work_author and work_category tables.
    pass

def fetch_work(
        session, feed_id, ao3_work_id, force=False, priority=HIGH_PRIORITY):
    """ Fetches a work for a feed using an authenticated user session. """
    # NOTE: Can preprocess parameters here, e.g. by serializing `session`
    return fetch_work_async.apply_async(
        args=(session, feed_id, ao3_work_id),
        kwargs={'force':force},
        # TODO: Add other async params, e.g. retry (or define in decorator?)
        priority=priority)
