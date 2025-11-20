import logging

from galaxy import exceptions
from galaxy.web import (
    expose_api_anonymous_and_sessionless,
)
from galaxy.webapps.base.controller import BaseAPIController

from galaxy.webapps.galaxy.api import (
    Router,
)


from galaxy.webapps.galaxy.services.osug_linting import OsugLintingService


log = logging.getLogger(__name__)

router = Router(tags=["osug_linting"])

#Check that a tool XML string is well formed and respects some mandatory rules
class OsugLintingAPIController(BaseAPIController):

    def __init__(self, app):
        super().__init__(app)
        self.service_linting = OsugLintingService()

    @expose_api_anonymous_and_sessionless
    def is_valid(self, trans, **kwd):
        payload = kwd.get("payload")
        if payload is None:
            raise exceptions.RequestParameterInvalidException("Payload is empty")
        XML_content = payload["XMLContent"]
        if not "XMLContent" in payload or payload["XMLContent"] is None or not "tool_id" in payload:
            raise exceptions.RequestParameterInvalidException("The XML content is missing")
        
        osug_rules = "osug_rules" in payload and payload["osug_rules"]
        linting_result = self.service_linting.linting(
            trans, 
            tool_id=payload.get("tool_id"),
            XML_content=XML_content, 
            osug_rules=osug_rules, #Boolean, True to check some custom rules
        )
        return linting_result
