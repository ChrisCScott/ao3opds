""" Package file for webapp, plus Flask application factory. """

import os
from flask import Flask

def create_app(test_config=None):
    # Create and configure the app:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',  # TODO: Override with secret key (not in Git!)
        DATABASE=os.path.join(app.instance_path, 'app.sqlite'))

    if test_config is None:
        # Load the instance config, if it exists, when not testing:
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Load the test config if passed in:
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists:
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return 'Hello, World!'

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
