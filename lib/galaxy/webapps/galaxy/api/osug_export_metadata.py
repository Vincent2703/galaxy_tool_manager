import logging

from galaxy import exceptions, web
from galaxy.web import (
    expose_api_anonymous_and_sessionless,
    expose_api_anonymous,
)
from galaxy.webapps.base.controller import BaseAPIController

from galaxy.webapps.galaxy.api import (
    depends,
    Router,
)
from fastapi import (
    Response,
    status,
)

from galaxy.webapps.galaxy.services.osug_export_metadata import (
    OsugExportMetadataService
)

log = logging.getLogger(__name__)

router = Router(tags=["osug_export_metadata"])


class OsugExportMetadataAPIController(BaseAPIController):

    @web.expose
    @expose_api_anonymous
    def show(self, trans, id):
        service = OsugExportMetadataService(trans)
        return service.get_data_to_export(id)