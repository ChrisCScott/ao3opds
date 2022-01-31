""" A module for basic navigation. """

from flask import Blueprint, render_template
from ao3opds.app.feed import FEED_TYPES

# No url_prefix; these pages load at root (e.g. '/', '/login')
blueprint = Blueprint('nav', __name__)

@blueprint.route('/')
def index():
    """ Renders homepage (index) view. """
    return render_template('nav/index.html', feed_types=FEED_TYPES)
