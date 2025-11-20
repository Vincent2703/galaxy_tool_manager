from galaxy.web import expose_api_anonymous_and_sessionless
from galaxy.webapps.base.controller import BaseAPIController

import logging

from lib.galaxy.webapps.galaxy.services.osug_groups import OsugGroupsService
logging.basicConfig()
log = logging.getLogger()


class OsugGroupsAPIController(BaseAPIController):

    def __init__(self, app):
        super().__init__(app)
        self.service = OsugGroupsService()

    """
    GET the groups (id and name) of the current user
    """
    @expose_api_anonymous_and_sessionless
    def index(self, trans): 
        return self.service.get_current_user_groups(trans)