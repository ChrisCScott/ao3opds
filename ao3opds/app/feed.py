from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for)
from werkzeug.exceptions import abort
from ao3opds.app.auth import login_required
from ao3opds.app.db import get_db
from ao3opds.marked_for_later_opds import get_marked_for_later_opds

blueprint = Blueprint('feed', __name__, url_prefix='/feed')

@blueprint.route('/')
# User must be logged in to do this
# TODO: Consider whether instead we should return HTTP status 401
# [Unauthorized] if accessing a feed endpoint rather than redirect to
# `login` (as `login_required` does), as the client is likely to be
# an ebook reader rather than a client. (Consider whether it is possible
# to issue a 401 error and also a redirect...)
@login_required
def marked_for_later():
    """ An OPDS v. 1.2 feed of a user's AO3 Marked for Later works. """
    # TODO: Acquire user credentials

    # TODO: Check user.updated, return cached feed if recent

    # TODO: Otherwise, get AO3 credentials.
    # NOTE: We'll need to store AO3 credentials in order to do this.
    # There is no truly safe way to do this, but look into mitigation
    # techniques to improve security.

    # TODO: Pass AO3 credentials to `get_marked_for_later_opds` to
    # attempt loading from AO3. Check for errors/None return value

    # TODO: Handle error case (`flash`+redirect, HTTP error code?)

    # TODO: Return OPDS feed
    pass
