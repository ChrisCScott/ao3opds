from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, abort)
from werkzeug.exceptions import HTTPException
from ao3opds.app.db import get_db
from ao3opds.app.auth import login_required

# No url_prefix; these pages load at root (e.g. '/', '/login')
blueprint = Blueprint('ao3', __name__, url_prefix='/ao3')

def get_credentials():
    """ Gets AO3 credentials for current user. """
    # Must be logged in:
    if g.user is None:
        abort(403, "Cannot access AO3 credentials if not logged in.")

    # Get credentials for current user:
    user_id = g.user['id']
    ao3_credentials = get_db().execute(
        'SELECT id, user_id, username, password, session, updated'
        ' FROM ao3 WHERE user_id = ?',
        (user_id,)
    ).fetchone()

    # Check for errors (raises HTTPException):
    if ao3_credentials is None:
        abort(
            404, # No such resource
            f"AO3 credentials for {g.user['username']} could not be found.")

    if ao3_credentials['user_id'] != g.user['id']:
        abort(
            403, # Access to another user's AO3 credentials is forbidden.
            f"User {g.user['username']} cannot access requested AO3 credentials")

    return ao3_credentials

def set_credentials(username, password, session=None):
    """ Sets AO3 credentials for the current user. """
    # Must be logged in:
    if g.user is None:
        abort(403, "Cannot access AO3 credentials if not logged in.")

    user_id = g.user['id']
    db = get_db()
    # Check for existing AO3 credentials:
    try:
        ao3_credentials = get_credentials()
    except HTTPException as error:
        if error.code == 404: # No such resource
            # Add new record for this user:
            db.execute(
                "INSERT INTO ao3 (user_id, username, password, session)"
                " VALUES (?, ?, ?, ?)",
                (user_id, username, password, session))
            db.commit()  # Save changes to db file
            return
        # If an unexpected error, re-raise:
        raise error
    # If AO3 credentials were found, we need to update, not insert:
    db.execute(
        "UPDATE ao3 SET username = ?, password = ?, session = ?"
        " WHERE user_id = ?",
        (username, password, user_id, session))
    db.commit() # Save changes to file

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
        user_id = g.user['id']
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        # Return an error if input is not provided:
        if not username and not password:
            error = 'All fields are required'

        # TODO: Validate that the user can authenticate with AO3,
        # return an error if not. If successful, pickle the session and
        # store it to the db for later use.
        session = None

        # Add user to database:
        if error is None:
            try:
                set_credentials(username, password, session)
            except HTTPException as err:
                error = "Error setting AO3 credentials: " + str(err)
            else:
                # If no errors, redirect to home page with confirmation:
                flash('AO3 credentials updated!')
                return redirect(url_for("index"))

        # If there was an error, store it (so it can be rendered later)
        flash(error)

    # Show user registration page on first load (or after an error):
    return render_template('ao3/manage.html')
