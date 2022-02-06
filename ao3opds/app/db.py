import sqlite3
import pickle
import click
from flask import current_app, g
from flask.cli import with_appcontext

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

def load_ao3_session(blob: bytes, update=True) -> AO3.Session:
    """ Converts a blob pulled from the database to an AO3.Session. """
    return pickle.loads(blob)

def dump_ao3_session(session: AO3.Session) -> bytes:
    """ Converts an AO3.Session to a blob for storage in the database. """
    return pickle.dumps(session, pickle.HIGHEST_PROTOCOL)
