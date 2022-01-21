import datetime
from flask import Blueprint, g, request, url_for
from werkzeug.exceptions import abort
from ao3opds.app.db import get_db
from ao3opds.app.ao3 import REFRESH_FREQUENCY, ao3_session_required
from ao3opds.marked_for_later_opds import get_marked_for_later_opds, FEED_AUTHOR
import AO3

# Feeds are stale after 5 minutes:
REFRESH_FREQUENCY = datetime.timedelta(minutes=5)
FEED_TYPE_MARKED_FOR_LATER = "marked_for_later"

blueprint = Blueprint('feed', __name__, url_prefix='/feed')

def render_marked_for_later_feed(session: AO3.Session):
    """ Generates an OPDS feed for a user's Marked for Later list """
    feed_id = url_for('feed.marked_for_later')
    feed_title = f"{session.username}'s Marked for Later list"
    feed = get_marked_for_later_opds(
        session, feed_id, feed_title, [FEED_AUTHOR])
    return feed

# We support a few modes here; a user can be logged in, or they can
# provide their AO3 credentials (as `u` and `p` GET parameters) without
# having an account:
@blueprint.route('/', methods=['GET'])
def marked_for_later():
    """ An OPDS v. 1.2 feed of a user's AO3 Marked for Later works. """
    # Support anonymous mode:
    if (
            g.ao3_session is None and  # User not logged in
            request.args.get['u'] and request.args.get['p'] # Credentials provided
        ):
        # Spin up an anonymous session:
        ao3_username = request.args.get['u']
        ao3_password = request.args.get['p']
        try:
            session = AO3.Session(ao3_username, ao3_password)
        except AO3.utils.LoginError as err:
            abort(401, "Could not authenticate with AO3: " + str(err))
        return render_marked_for_later_feed(session)
    # Check to see whether there is an active AO3 session:
    elif g.ao3_session is None:  # no logged in user, no credentials:
        abort(401, "Must be logged in to see Marked for Later feed.")

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

    # Generate a new feed if there's no cached feed (of if it's old)
    if (
            feed is None or
            feed['updated'] < datetime.datetime.now() - REFRESH_FREQUENCY
        ):
        # Refresh the feed:
        new_feed = render_marked_for_later_feed(session)
        # Store the feed:
        if feed is None:  # insert new feed if no existing feed
            db.execute(
                'INSERT INTO feed (user_id, ao3_id, feed_type, content)'
                ' VALUES (?, ?, ?, ?)',
                (user_id, ao3_id, FEED_TYPE_MARKED_FOR_LATER, new_feed))
        else:  # update existing feed if it exists
            db.execute(
                'UPDATE feed SET (content = ?, updated = CURRENT_TIMESTAMP)'
                ' WHERE id = ?', (new_feed, feed['id']))
        # Replace the old feed with the new feed, to show to the user:
        feed = new_feed

    # No need to render; `feed` is already a rendered template:
    return feed
