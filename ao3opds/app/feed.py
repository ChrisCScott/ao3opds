import datetime
from flask import (
    Blueprint, g, request, render_template, Response, flash)
from werkzeug.exceptions import abort
from ao3opds.app.db import get_db
from ao3opds.app.auth import login_required
from ao3opds.render import (
    bookmarks_opds, marked_for_later_opds, subscriptions_opds, history_opds)
import AO3

# Feeds are stale after 5 minutes:
REFRESH_FREQUENCY = datetime.timedelta(minutes=5)
FEED_TYPE_MARKED_FOR_LATER = "Marked for Later"
FEED_TYPE_BOOKMARKS = "Bookmarks"
FEED_TYPE_SUBSCRIPTIONS = "Subscriptions"
FEED_TYPE_HISTORY = "History"
# NOTE: Update these if a new feed type is added:
# This is a mapping of feed types (as represented in the DB) to
# endpoints that are resolvable to urls via `url_for()`:
FEED_TYPES = {
    FEED_TYPE_MARKED_FOR_LATER: 'feed.marked_for_later',
    FEED_TYPE_BOOKMARKS: 'feed.bookmarks',
    FEED_TYPE_SUBSCRIPTIONS: 'feed.subscriptions',
    FEED_TYPE_HISTORY: 'feed.history'}
FEED_FETCH_METHODS = {
    FEED_TYPE_MARKED_FOR_LATER: marked_for_later_opds,
    FEED_TYPE_BOOKMARKS: bookmarks_opds,
    FEED_TYPE_SUBSCRIPTIONS: subscriptions_opds,
    FEED_TYPE_HISTORY: history_opds}
FEED_MIME_TYPE = 'text/xml'

blueprint = Blueprint('feed', __name__, url_prefix='/feed')

def feed_view(feed:str) -> Response:
    """ Call this when returning from a view that displays a feed. """
    response = Response(feed, mimetype=FEED_MIME_TYPE)
    return response

def refresh_feed(
        feed, session:AO3.Session=None, force:bool=False, threaded=True) -> str:
    """ Refreshes a cached OPDS feed. Returns the content of the feed. """
    # If the feed is not stale, return its content without refreshing:
    if (
            not force and
            feed['updated'] > datetime.datetime.now() - REFRESH_FREQUENCY and
            feed['content'] is not None
        ):
        return feed['content']
    # Otherwise, for a stale feed, update it:
    db = get_db()
    # First authenticate with AO3:
    if session is None:
        ao3 = db.execute(
            'SELECT username, password FROM ao3 WHERE id = ?',
            (feed['ao3_id'],)).fetchone()
        try:
            session = AO3.Session(ao3['username'], ao3['password'])
        except AO3.utils.LoginError as err:
            abort(401, "Could not authenticate with AO3: " + str(err))

    # Fetch the updated feed:
    feed_type = feed['feed_type']
    fetch_feed = FEED_FETCH_METHODS[feed_type]
    new_feed = fetch_feed(session, threaded=True)
    # Store the updated feed in the database:
    db.execute(
        'UPDATE feed SET content = ?, updated = CURRENT_TIMESTAMP'
        ' WHERE id = ?', (new_feed, feed['id']))
    db.commit()  # Save changes to database
    return new_feed

def prepopulate_feeds(user_id):
    """ Generates entries in `feeds` for `user_id`. """
    db = get_db()
    ao3_id = db.execute(
        'SELECT id FROM ao3 WHERE user_id = ?', (user_id,)).fetchone()['id']
    if ao3_id is None:
        flash(f"User has no AO3 credentials on record.")
        return
    # Create each dummy feed with a stale `updated` attribute:
    updated = datetime.datetime.now() - 2 * REFRESH_FREQUENCY
    for feed_type in FEED_TYPES:
        record = db.execute(
            'SELECT * FROM feed'
            ' WHERE (feed_type = ? AND user_id = ? AND ao3_id = ?)',
            (feed_type, user_id, ao3_id)).fetchone()
        # If we found a record, move on to the next feed type:
        if record is not None:
            continue
        # Add a dummy entry for this user (NULL content):
        db.execute(
            'INSERT INTO feed (user_id, ao3_id, feed_type, updated, content)'
            ' VALUES (?, ?, ?, ?, ?)',
            (user_id, ao3_id, feed_type, updated, None))
    db.commit()  # Save changes to database

def render_feed(feed_type):
    """ Renders a feed of type `feed_type` based on `fetch_feed`. """
    # We support a few modes here; a user can be logged in, or they can
    # provide their AO3 credentials (as `u` and `p` GET parameters)
    # without having an account:

    fetch_feed = FEED_FETCH_METHODS[feed_type]

    # Support anonymous mode:
    if (
            g.ao3_session is None and  # User not logged in
            request.args.get('u') and request.args.get('p') # Credentials provided
        ):
        # Spin up an anonymous session:
        ao3_username = request.args.get['u']
        ao3_password = request.args.get['p']
        try:
            session = AO3.Session(ao3_username, ao3_password)
        except AO3.utils.LoginError as err:
            abort(401, "Could not authenticate with AO3: " + str(err))
        return feed_view(fetch_feed(session, threaded=True))
    # Check to see whether there is an active AO3 session:
    elif g.ao3_session is None:  # no logged in user, no credentials:
        abort(401, "Must authenticate with AO3 to view feeds.")

    # Ok, if we get here then we must be logged in.
    # Acquire user credentials and other useful data:
    user_id = g.user['id']
    ao3_id = g.ao3['id']
    session = g.ao3_session
    db = get_db()

    # Get the cached feed, if it exists:
    feed = db.execute(
        'SELECT * FROM feed WHERE (user_id = ? AND feed_type = ?)',
        (user_id, feed_type)
    ).fetchone()

    # Generate a new feed if there's no cached feed (or if it's old)
    if feed is None:
        feed = fetch_feed(session, threaded=True)
        # Store the feed:
        db.execute(
            'INSERT INTO feed (user_id, ao3_id, feed_type, content)'
            ' VALUES (?, ?, ?, ?)',
            (user_id, ao3_id, feed_type, feed))
        db.commit()
    else:  # update existing feed if it exists
        # This converts the Row object to a str of the feed's contents:
        feed = refresh_feed(feed, session, threaded=True)

    # No need to render; `feed` is already a rendered template:
    return feed_view(feed)

@blueprint.route('/marked_for_later', methods=['GET'])
def marked_for_later():
    """ An OPDS v. 1.2 feed of a user's AO3 Marked for Later works. """
    return render_feed(FEED_TYPE_MARKED_FOR_LATER)

@blueprint.route('/bookmarks', methods=['GET'])
def bookmarks():
    """ An OPDS v. 1.2 feed of a user's AO3 bookmarked works. """
    return render_feed(FEED_TYPE_BOOKMARKS)

@blueprint.route('/subscriptions', methods=['GET'])
def subscriptions():
    """ An OPDS v. 1.2 feed of works in a user's AO3 subscriptions. """
    return render_feed(FEED_TYPE_SUBSCRIPTIONS)

@blueprint.route('/history', methods=['GET'])
def history():
    """ An OPDS v. 1.2 feed of a user's AO3 history. """
    return render_feed(FEED_TYPE_HISTORY)

@blueprint.route('/share/<share_key>')
def share(share_key):
    """ Returns an OPDS feed with sharing enabled """
    db = get_db()
    # Look up the feed with `share_key`:
    feed = db.execute(
        'SELECT * from feed WHERE (share_key = ? AND share_enabled = 1)',
        (share_key,)).fetchone()
    # If there's no shareable feed with that key, return an error:
    if feed is None:
        abort(404, "Feed not found")
    # Refresh the feed if it is old.
    feed = refresh_feed(feed)
    # Otherwise, return the feed's contents:
    return feed_view(feed)

@blueprint.route('/manage', methods=['GET', 'POST'])
@login_required
def manage():
    """ Allows a user to choose to share links and acquire their urls. """
    user_id = g.user['id']
    db = get_db()
    # Add a feed record for each type of feed so that the user can
    # configure them:
    prepopulate_feeds(user_id)
    # User has submitted a form with updated sharing permissions:
    if request.method == 'POST':
        g.feeds = db.execute(
            'SELECT * FROM feed WHERE user_id = ?', (user_id,)).fetchall()
        # For each feed, set the `share_enabled` property based on
        # whether the checkbox in the form was checked:
        for feed in g.feeds:
            share_enabled = 1 if request.form.get(feed['share_key']) else 0
            db.execute(
                'UPDATE feed SET share_enabled = ? WHERE share_key = ?',
                (share_enabled, feed['share_key']))
        db.commit()
    # Get the list of feeds (as updated, if applicable) and render:
    g.feeds = db.execute(
        'SELECT * FROM feed WHERE user_id = ?', (user_id,)).fetchall()
    return render_template('feed/manage.html')
