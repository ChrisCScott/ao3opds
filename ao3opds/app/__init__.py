""" Package file for webapp, plus Flask application factory. """

import os
from flask import Flask
from celery import Celery

# Create a global Celery object for background tasks. This will be
# configured on app creation. For more on this approach, see:
# https://blog.miguelgrinberg.com/post/celery-and-the-flask-application-factory-pattern
# NOTE: Different apps cannot safely provide different Celery
# configuration values using this approach.
CELERY_BROKER_URL = 'redis://localhost:6379'
celery = Celery(__name__, broker=CELERY_BROKER_URL)

def create_app(test_config=None):
    # Create and configure the app:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        # SECRET_KEY is overidden in production via `config.py`, below.
        SECRET_KEY='dev',
        # We use an SQLite database in the instance folder
        # (which can be located in various places; let Flask handle it)
        DATABASE=os.path.join(app.instance_path, 'app.sqlite'),
        # Configure Celery, which handles long-running background tasks:
        CELERY_BROKER_URL=CELERY_BROKER_URL,
        CELERY_RESULT_BACKEND=CELERY_BROKER_URL)

    if test_config is None:
        # Load the instance config, if it exists, when not testing:
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Load the test config if passed in:
        app.config.from_mapping(test_config)

    # Once the Flask app's config is finalized, we can configure use it
    # to configure the global celery object:
    celery.conf.update(app.config)

    # Ensure the instance folder exists:
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Configure app to initialize database:
    from . import db
    db.init_app(app)

    # Register authentication module:
    from . import auth
    app.register_blueprint(auth.blueprint)

    # Register ao3 module:
    from . import ao3
    app.register_blueprint(ao3.blueprint)

    # Register OPDS feed (and homepage) module:
    from . import feed
    app.register_blueprint(feed.blueprint)

    # Register naviation module:
    from . import nav
    app.register_blueprint(nav.blueprint)
    # Ensure views referring to `index` point to root:
    app.add_url_rule('/', endpoint='index')

    return app
