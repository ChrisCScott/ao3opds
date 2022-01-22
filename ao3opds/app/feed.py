import datetime
from flask import (
    Blueprint, g, request, url_for, render_template, Response, flash)
from werkzeug.exceptions import abort
from ao3opds.app.db import get_db
from ao3opds.app.auth import login_required
from ao3opds.render import fetch_marked_for_later, FEED_AUTHOR
import AO3

# Feeds are stale after 5 minutes:
REFRESH_FREQUENCY = datetime.timedelta(minutes=5)
FEED_TYPE_MARKED_FOR_LATER = "Marked for Later"
# NOTE: Update these if a new feed type is added:
# This is a mapping of feed types (as represented in the DB) to
# endpoints that are resolvable to urls via `url_for()`:
FEED_TYPES = {FEED_TYPE_MARKED_FOR_LATER: 'feed.marked_for_later'}
FEED_MIME_TYPE = 'text/xml'

blueprint = Blueprint('feed', __name__, url_prefix='/feed')

def render_feed(feed:str) -> Response:
    """ Call this when returning from a view that displays a feed. """
    response = Response(feed, mimetype=FEED_MIME_TYPE)
    return response

def render_marked_for_later_feed(session: AO3.Session) -> str:
    """ Generates an OPDS feed for a user's Marked for Later list """
    feed_id = url_for('feed.marked_for_later')
    feed_title = f"{session.username}'s Marked for Later list"
    feed = fetch_marked_for_later(
        session, feed_id, feed_title, [FEED_AUTHOR], threaded=True)
    return feed

def refresh_marked_for_later_feed(
        feed, session:AO3.Session=None, force:bool=False) -> str:
    """ Refreshes a cached Marked for Later OPDS feed.
    
    Returns the contents of the feed.
    """
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
    new_feed = render_marked_for_later_feed(session)
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

# We support a few modes here; a user can be logged in, or they can
# provide their AO3 credentials (as `u` and `p` GET parameters) without
# having an account:
@blueprint.route('/', methods=['GET'])
def marked_for_later():
    """ An OPDS v. 1.2 feed of a user's AO3 Marked for Later works. """
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
        return render_feed(render_marked_for_later_feed(session))
    # Check to see whether there is an active AO3 session:
    elif g.ao3_session is None:  # no logged in user, no credentials:
        abort(401, "Must authenticate with AO3 to see Marked for Later feed.")

    # Ok, if we get here then we must be logged in.
    # Acquire user credentials and other useful data:
    user_id = g.user['id']
    ao3_id = g.ao3['id']
    session = g.ao3_session
    db = get_db()

    # Get the cached feed, if it exists:
    feed = db.execute(
        'SELECT * FROM feed WHERE (user_id = ? AND feed_type = ?)',
        (user_id, FEED_TYPE_MARKED_FOR_LATER)
    ).fetchone()

    # Generate a new feed if there's no cached feed (or if it's old)
    if feed is None:
        feed = render_marked_for_later_feed(session)
        # Store the feed:
        db.execute(
            'INSERT INTO feed (user_id, ao3_id, feed_type, content)'
            ' VALUES (?, ?, ?, ?)',
            (user_id, ao3_id, FEED_TYPE_MARKED_FOR_LATER, feed))
        db.commit()
    else:  # update existing feed if it exists
        # This converts the Row object to a str of the feed's contents:
        feed = refresh_marked_for_later_feed(feed, session)

    # No need to render; `feed` is already a rendered template:
    return render_feed(feed)

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
    feed = refresh_marked_for_later_feed(feed)
    # Otherwise, return the feed's contents:
    return render_feed(feed)

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
