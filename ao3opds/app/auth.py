""" A module for user authentication. """

import functools
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from ao3opds.app.db import get_db

# No url_prefix; these pages load at root (e.g. '/', '/login')
blueprint = Blueprint('auth', __name__)

@blueprint.route('/')
def index():
    """ Renders homepage (index) view. """
    return render_template('auth/index.html')

@blueprint.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        # User has submitted the form.
        # Validate input:
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        # Return an error if not provided:
        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'

        # Add user to database:
        if error is None:
            try:
                db.execute(
                    "INSERT INTO user (username, password) VALUES (?, ?)",
                    (username, generate_password_hash(password)))
                db.commit()  # Save changes to db file
            except db.IntegrityError:
                error = f"User {username} is already registered."
            else:
                # If no errors, redirect to login page:
                return redirect(url_for("auth.login"))

        # If there was an error, store it (so it can be rendered later)
        flash(error)

    # Show user registration page on first load (or after an error):
    return render_template('auth/register.html')

@blueprint.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        # User has submitted the form.
        # Look up user in database:
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute(
            'SELECT * FROM user WHERE username = ?', (username,)
        ).fetchone()

        # See if a registered user with correct password was provided:
        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        # Log the user in if everything looks good:
        if error is None:
            session.clear()
            session['user_id'] = user['id']
            # Send the user to the main page:
            return redirect(url_for('index'))

        # Store error to render later:
        flash(error)

    return render_template('auth/login.html')

@blueprint.before_app_request  # Run before view function
def load_logged_in_user():
    user_id = session.get('user_id')

    # Store the active user in global var `g` at start of each request:
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM user WHERE id = ?', (user_id,)
        ).fetchone()

@blueprint.route('/logout')
def logout():
    # Remove user from session:
    session.clear()
    return redirect(url_for('index'))

# Create a decorator for other views that require authentication:
def login_required(view):
    # Wrap the decorated function so that it redirects to the login
    # view if a user is not logged in:
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        return view(**kwargs)

    return wrapped_view
