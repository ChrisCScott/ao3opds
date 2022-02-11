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

from dataclasses import dataclass
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

@dataclass
class RecordResult:
    """ Struct for returning information about created/updated records.

    Attributes:
        id (int): Primary key for the record that was created/updated.
        table (str): The name of the table of the record.
        id_field (str): The name of the primary key's field.
        updated (bool): True if the record was updated, False otherwise.
        created (bool): True if the record was created, False otherwise.
    """
    id: int
    table: str
    id_field: str
    old_record: Any

    def record(self) -> Any:
        """ Fetches the record that was created or updated. """
        return get_db().execute(
            'SELECT * FROM ' + self.table + ' WHERE ' + self.id_field + ' = ?',
            (self.id,)).fetchone()

def ao3_user_to_db(user_id, ao3_username, ao3_password, session):
    """ Creates or updates an ao3 user record in the database """
    fields = {
        'user_id': user_id,
        'username': ao3_username,
        'password': ao3_password,
        'session': dump_ao3_session(session)}
    keys = ['user_id']
    return record_to_db('ao3', fields, keys)

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
    record = ao3_user_to_db(
        user_id, ao3_username, ao3_password, session)
    ao3_user_id = record.id

    # Check to see if the AO3 user account changed. If it did, don't
    # delete the feeds - instead, force updates on the feed.
    if (
            record.old_record is not None and
            record.old_record['user_id'] != ao3_username):
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

def feed_to_db(ao3_user_id: int, feed_type: str) -> RecordResult:
    """ Gets a feed record from the database, creating it if needed. """
    fields = {
        'user_id': ao3_user_id,
        'feed_type': feed_type}
    keys = ['user_id', 'feed_type']
    return record_to_db('feed', fields, keys)

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
    record = feed_to_db(ao3_user_id, feed_type)
    # TODO: Prevent feed_to_db from updating if the record is not stale
    feed_record = record.record()
    # If it exists and was recently updated, skip it:
    if (
            # TODO: Revise this to make sense with the new
            # feed_to_db logic/return value.
            record.old_record is not None and
            feed_record['updated'] > update_threshold and
            fetch_modes['FEED'] != FetchMode.FORCE):
        return session

    # Update the db records of works for this feed:
    update_feed_works(session, feed_type, record.id, fetch_modes, priority)

    # The feed has been updated, so update its record accordingly:
    db.execute(
        "UPDATE feed SET updated = CURRENT_TIMESTAMP WHERE (feed_id = ?)",
        (record.id,))

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
    fields = {
        'work_id': work_id,
        'feed_id': feed_id}
    keys = ['work_id', 'feed_id']
    return record_to_db('feed_entry', fields, keys)

def _where_clause(table, fields, keys) -> tuple[str, str]:
    """ Builds a WHERE clause from `fields` and `keys`. """
    where_fields = ' WHERE (' + fields[keys[0]]
    for key in keys[1:]:
        where_fields += ' AND ' + fields[key] + ' = ?'
    where_fields = ')'
    where_values = tuple(fields[key] for key in keys)
    return (where_fields, where_values)

def _insert_query(table, fields, keys):
    """ Builds an INSERT query. """
    # Build a string of fields for use in an INSERT clause:
    fields_iter = iter(fields)
    insert_fields = ' (' + next(fields_iter)
    for field in fields_iter:
        insert_fields += ', ' + field
    insert_fields = ')'
    insert_values = ' VALUES (?'
    for _ in range(len(fields) - 1):
        insert_values += ', ?'
    insert_values = ')'
    insert_query = 'INSERT INTO ' + table + insert_fields + insert_values
    return (insert_query, fields.values())

def _update_query(
        table, fields, keys, updated_field, where_clause, where_values):
    """ """
    # Build a string of fields to update:
    # Get the names of fields we'll be updating:
    non_key_fields = [field for field in fields if field not in keys]
    # We can optionally update a field to the current timestamp,
    # so build a string for that too:
    updated_clause = (
        updated_field + ' = CURRENT_TIMESTAMP' if updated_field else None)
    # Build a comma-separated list of field names (we handle the
    # updated field a bit differently, so handle it separately)
    if not non_key_fields:
        update_fields = updated_clause
    else:
        update_fields = non_key_fields[0] + ' = ?'
        for field in non_key_fields[1:]:
            update_fields += ', ' + field + ' = ?'
        if updated_clause:
            update_fields += ', ' + updated_clause
    # Be sure to pass in the updated values before the values
    # we query in the WHERE clause to find this record:
    update_values = tuple(
        value for key, value in fields.items() if key in non_key_fields)
    update_query = 'UPDATE ' + table + ' SET ' + update_fields + where_clause
    return (update_query, update_values + where_values)

def record_to_db(
        table: str, fields: dict[str, Any], keys: list[str],
        id_field:str='id', updated_field:str|None='updated') -> RecordResult:
    """ Creates or updates a record in `table`.
    
    Arguments:
        table (str): the name of the table in which to create/update
            a record.
        fields (dict[str, Any]): A mapping from field names to values.
            If inserting, all fields will be inserted with the mapped
            values. If updating, only fields not found in `keys` will
            be updated.
        keys (list[str]): Names of fields which are used to query the
            database for an existing record (as WHERE clause
            parameters). Each value in `keys` must also be a key of
            `fields` with a corresponding value (used in the query).
        id (str): The name of the primary key field for `table`.
            Optional. Defaults to "id".
        updated_field (str | None): A convenience parameter. If not
            None, the field with this name will be set to
            `CURRENT_TIMESTAMP` in an UPDATE operation. Defaults to
            "updated". Optional.

    Returns:
        (Any) The created/updated record, including all fields
    """
    db = get_db()
    # Build the WHERE clause for SELECT and UPDATE queries:
    where_clause, where_values = _where_clause(fields, keys)
    # Look for an existing record:
    cursor = db.execute(
        'SELECT * FROM ' + table + where_clause, where_values)
    record = cursor.fetchone()
    record_id = record[id_field] if record is not None else None
    # If no existing record, insert one:
    if record is None:
        insert_query, insert_values = _insert_query(table, fields, keys)
        cursor = db.execute(insert_query, insert_values)
        record_id = cursor.lastrowid
    # If there is an existing record, update it:
    else:
        update_query, update_values = _update_query(
            table, fields, keys, updated_field, where_clause, where_values)
        db.execute(update_query, update_values)
    db.commit()  # Save changes
    # Collect the new/updated record to return to the user:
    return RecordResult(record_id, table, id_field, record)

def link_author_to_work(work_id: int, author_id: int):
    """ Links an author record to a work record in the database. """
    fields = {
        'work_id': work_id,
        'author_id': author_id}
    keys = ['work_id', 'author_id']
    return record_to_db('work_author', fields, keys)

def author_to_db(author: OPDSPerson, work_id=None) -> RecordResult:
    """ Creates or updates an author record in the database. """
    fields = {
        'name': author.name,
        'email': author.email,
        'uri': author.uri}
    keys = ['name']
    record = record_to_db('author', fields, keys)
    # Link the author to a work if a work_id was provided:
    if work_id is not None:
        link_author_to_work(record.id, work_id)
    # Collect the new/updated record to return to the user:
    return record

def category_to_db(category: OPDSCategory, work_id=None):
    """ Creates or updates a category record. """
    fields = {
        'term': category.term,
        'scheme': category.scheme,
        'label': category.label}
    keys = list(fields)
    record = record_to_db('category', fields, keys)
    # Add a linking record if one does not yet exist:
    if work_id is not None:
        link_category_to_work(record.id, work_id)
    return record

def link_category_to_work(category_id, work_id):
    """ Links a category record to a work record in the database. """
    fields = {
        'work_id': work_id,
        'category_id': category_id}
    keys = list(fields)
    return record_to_db('work_category', fields, keys)

def link_to_db(link: OPDSLink, work_id):
    """ Creates or updates a link record in the database. """
    fields = {
        'work_id': work_id,
        'href': link.href,
        'rel': link.rel,
        'link_type': link.type}
    keys = list(fields)
    return record_to_db('link', fields, keys)

def work_to_db(work: AO3.Work):
    """ Creates or updates a work record in the database """
    # Use our OPDS code to convert the AO3 data into the fields we want:
    opds_work = AO3WorkOPDS(work)
    fields = {
        'work_id': opds_work.id,
        'title': opds_work.title,
        'work_updated': opds_work.updated,
        'work_language': opds_work.language,
        'publisher': opds_work.publisher,
        'summary': opds_work.summary}
    keys = ['work_id']
    record = record_to_db('work', fields, keys)

    # Add author/category/link records for this work
    for author in opds_work.authors:
        author_to_db(author, record.id)
    for category in opds_work.categories:
        category_to_db(category, record.id)
    for link in opds_work.links:
        link_to_db(link, record.id)

    return record

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
    record = work_to_db(work)

    # If the work is newly-added, link it to the feed:
    if feed_entry_record is None:
        link_work_to_feed(record.id, feed_id)

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
