import pickle
import datetime
import functools
from plistlib import load
from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for,
    abort, session)
from werkzeug.exceptions import HTTPException
from ao3opds.app.db import get_db
from ao3opds.app.auth import login_required
from ao3opds.app.feed import prepopulate_feeds
import AO3

# The frequency with which the user's AO3 session is refreshed:
REFRESH_FREQUENCY = datetime.timedelta(days=14)

# No url_prefix; these pages load at root (e.g. '/', '/login')
blueprint = Blueprint('ao3', __name__, url_prefix='/ao3')

@blueprint.before_app_request  # Run before view function
def load_ao3_credentials():
    user_id = session.get('user_id')

    # Store the active user's ao3 credentials in global var `g`
    # at start of each request:
    if user_id is None:
        g.ao3 = None
        g.ao3_session = None
    else:
        g.ao3 = get_db().execute(
            'SELECT * FROM ao3 WHERE user_id = ?', (user_id,)
        ).fetchone()
        if g.ao3 is not None:
            # Convert session blob to an AO3.Session:
            g.ao3_session = load_ao3_session(g.ao3['session'])
        else:
            g.ao3_session = None

# Create a decorator for other views that require authentication:
def ao3_session_required(view):
    # Wrap the decorated function so that it refreshes the session if
    # it is stale:
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.ao3 is None:
            return redirect(url_for('ao3.manage'))
        # Ensure that the session is not stale:
        refresh_session()
        # Store new session in g.ao3 and g.ao3_session
        load_ao3_credentials()
        return view(**kwargs)

    # If a session is required, a login is also required. Wrap that
    # last so that it is checked first:
    wrapped_view = login_required(wrapped_view)

    return wrapped_view

def load_ao3_session(blob: bytes, update=True) -> AO3.Session:
    """ Converts a blob pulled from the database to an AO3.Session. """
    return pickle.loads(blob)

def dump_ao3_session(session: AO3.Session) -> bytes:
    """ Converts an AO3.Session to a blob for storage in the database. """
    return pickle.dumps(session, pickle.HIGHEST_PROTOCOL)

def refresh_session(force=False):
    """ Refreshes the AO3.Session for the current user. """
    # Nothing to do if there's no active AO3 record:
    if g.ao3 is None:
        return
    # If the current session is stale, or if demanded via `force`,
    # load a new session and store it to the db:
    if force or g.ao3['updated'] < datetime.datetime.now() - REFRESH_FREQUENCY:
        # Setting credentials will force the creation of a new session:
        set_credentials(g.ao3['username'], g.ao3['password'])
        # Refresh `g.ao3` with the new values:
        load_ao3_credentials()

def set_credentials(username, password):
    """ Sets AO3 credentials for the current user. """
    # Must be logged in:
    if g.user is None:
        abort(403, "Cannot access AO3 credentials if not logged in.")

    user_id = g.user['id']
    db = get_db()

    # Attempt to authenticate with AO3:
    # raises `AO3.utils.LoginError`
    session = AO3.Session(username, password)


    # If switching to another AO3 user account, drop the existing
    # records (which will cause following code to create new ones):
    if g.ao3 is not None and g.ao3['username'] != username:
        delete_credentials()

    # Check for existing AO3 credentials:
    if g.ao3 is None:
        # Add new record for this user:
        db.execute(
            "INSERT INTO ao3 (user_id, username, password, session)"
            " VALUES (?, ?, ?, ?)",
            (user_id, username, password, dump_ao3_session(session)))
        db.commit()  # Save changes to db file
        # Prepopulate `feed` table with no-content feeds so that the
        # user can manage their sharing permissions:
        prepopulate_feeds(user_id)
        return
    # If credentials for the same AO3 user account are already present,
    # just update them - we're just updating the password.
    db.execute(
        "UPDATE ao3 SET username = ?, password = ?, session = ?,"
        " updated = CURRENT_TIMESTAMP WHERE user_id = ?",
        (username, password, dump_ao3_session(session), user_id))
    db.commit() # Save changes to file
    # Update `g` attributes with new AO3 record and session:
    load_ao3_credentials()

def delete_credentials():
    """ Delete AO3 credentials for the current user. """
    # Must be logged in:
    if g.user is None:
        abort(403, "Cannot access AO3 credentials if not logged in.")

    user_id = g.user['id']
    db = get_db()
    # Delete all records of AO3 credentials for this user:
    db.execute('DELETE FROM ao3 WHERE user_id = ?', (user_id,))
    # Also delete all records of AO3 feeds:
    db.execute('DELETE FROM feed WHERE user_id = ?', (user_id,))
    db.commit()  # Save changes to file
    g.ao3 = None
    g.ao3_session = None

@blueprint.route('/manage', methods=('GET', 'POST'))
@login_required
def manage():
    """ Allow user to manage AO3 credentials. """
    if request.method == 'POST':
        # Delete credentials if the user selected the option:
        if request.form['submit_button'] == "Delete":
            delete_credentials()
            # Redirect to home page with confirmation:
            flash('AO3 credentials deleted!')
            return redirect(url_for("index"))
        # Otherwise, update credentials:
        username = request.form['username']
        password = request.form['password']
        error = None

        # Return an error if input is not provided:
        if not username and not password:
            error = 'All fields are required'

        # Add user to database:
        if error is None:
            try:
                set_credentials(username, password)
            except HTTPException as err:
                error = "Error setting AO3 credentials: " + str(err)
            except AO3.utils.LoginError as err:
                error = "Error authenticating with AO3: " + str(err)
            else:
                # If no errors, redirect to home page with confirmation:
                flash('AO3 credentials updated!')
                return redirect(url_for("index"))

        # If there was an error, store it (so it can be rendered later)
        flash(error)

    # Show user registration page on first load (or after an error):
    return render_template('ao3/manage.html')
