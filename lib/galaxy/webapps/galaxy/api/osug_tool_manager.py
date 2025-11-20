import logging

from galaxy import exceptions, web
from galaxy.web import (
    expose_api_anonymous,
)
from galaxy.webapps.base.controller import BaseAPIController
from galaxy.managers.osug_tool_manager import OsugToolManager

from galaxy.webapps.galaxy.services.osug_groups import OsugGroupsService
from galaxy.webapps.galaxy.services.osug_custom_tools import OsugCustomTools
from galaxy.webapps.galaxy.services.osug_linting import OsugLintingService

import lxml.etree as ET

from galaxy.webapps.galaxy.api import (
    Router,
)


log = logging.getLogger(__name__)

router = Router(tags=["osug_tool_manager"])


class OsugToolManagerAPIController(BaseAPIController):
    #service: OsugGroupsService = depends(OsugGroupsService)
    #manager: OsugToolManager = depends(OsugToolManager)
    """
    API controller in charge of client requests and sending formatted form values to the manager or the client
    """

    def __init__(self, app):
        super().__init__(app)
        self.service_groups = OsugGroupsService()
        self.service_custom_tools = OsugCustomTools()
        self.service_linting = OsugLintingService()
        self.manager = OsugToolManager()

    @web.expose
    @expose_api_anonymous
    def index(self, trans):
        """
        * GET /api/osug_tool_manager
            Get all tools shared with one of the groups of the current user

        :rtype:     list
        :returns:   list tools (similar to /api/tools).
                
        ..note:
            Custom API (OSUG).
        """
        
        return self.service_custom_tools.get_tools_shared_with_user(trans)
        

    @web.expose
    @expose_api_anonymous
    def generate_xml(self, trans, **kwd):
        """
        * POST /api/osug_tool_manager/generate_xml
            Format form values and return the xml code
            
        :type   payload:    dict
        :param  payload:    dictionary structure containing::
            'name'          = Tool name
            'id'            = Tool id
            'group'         = Dict with group id and group name to associate with the tool
            'version'       = Tool version
            'description'   = Tool description
            'inputs'        = Tool inputs
            'outputs'       = Tool outputs
            'method_script' = Which method used to add a command script (typeCmd : user defined command script / scriptPath : generate command script from interpreter, path to script and inputs/outputs values)
            'command'       = User defined command script
            'interpreter'   = Interpreter used by the user's script
            'path_script'   = Path to the user script
            'url_git_repo'  = URL to the script git repository
            'git_commit_ID' = Script commit ID
            'git_tag'       = Script tag

        ..note:
            Custom API (OSUG).

        :rtype:     dict
        :returns:   Status message (ok/not ok) TODO
        """

        payload = kwd.get("payload")
        if payload is None:
            raise exceptions.RequestParameterInvalidException("Invalid request.")

        service_response = self.service_custom_tools.format_payload(trans, payload)
        if not isinstance(service_response, str):
            response = self.manager.generate_XML_code(service_response) 
            return response
        
    
    @web.expose
    @expose_api_anonymous
    def get_tool_xml(self, trans, id):
        """
            * GET /api/osug_tool_manager/get_tool_xml
                Get the XML code of a tool, from its ID

                :type   tool_path:    string
                :param  tool_path:    Tool path

            ..note:
            Custom API (OSUG).

            :rtype:     string
            :returns:   String version of the tool XML

        """

        if id is None:
            raise exceptions.RequestParameterInvalidException("The tool path is incorrect. Please contact an administrator.")
        
        # We could use tool.tool_source.to_string() to get the XML but we loose CDATA and XML declaration... We want the raw file
        
        tool_path = self.service_custom_tools.get_tool_path_from_tool_ID(trans, id)
        response = self.manager.get_tool_XML(tool_path)
        return response


    @web.expose
    @expose_api_anonymous
    def create(self, trans, **kwd):
        """
        * POST /api/osug_tool_manager/create
            Format form values and send them to the manager
            to create a new tool.

        :type   payload:    dict
        :param  payload:    dictionary structure containing (depending on is_custom_XML)::
            'name'          = Tool name
            'id'            = Tool id
            'group'         = Dict with group id and group name to associate with the tool
            'version'       = Tool version
            'description'   = Tool description
            'inputs'        = Tool inputs
            'outputs'       = Tool outputs
            'method_script' = Which method used to add a command script (typeCmd : user defined command script / scriptPath : generate command script from interpreter, path to script and inputs/outputs values)
            'command'       = User defined command script
            'interpreter'   = Interpreter used by the user's script
            'path_script'   = Path to the user script
            'url_git_repo'  = URL to the script git repository
            'git_commit_ID' = Script commit ID
            'git_tag'       = Script tag
            'is_custom_XML' = Is a custom XML made by the user ?
            'custom_XML'    = Custom XML made by the user

        ..note:
            Custom API (OSUG).

        :rtype:     string or exception
        :returns:   error or tool_id
        """

        payload = kwd.get("payload")
        if payload is None or (payload.get("is_custom_XML") and not payload.get("custom_XML")): #Error if payload empty or if it's a custom XML, XML empty
            raise exceptions.RequestParameterInvalidException("Invalid request.")
        else:
            if not payload.get("is_custom_XML"): #From inputs
                formatted_payload = self.service_custom_tools.format_payload(trans, payload)
                if not isinstance(formatted_payload, str):
                    response = self.manager.create_custom_tool(trans, formatted_payload) 
                    return response
            else: #From custom XML text area
                custom_XML_str = payload.get("custom_XML")
                linting_response = self.service_linting.linting(trans, custom_XML_str)
                if type(linting_response)==bool and linting_response:
                    parser = ET.XMLParser(strip_cdata=False)
                    custom_XML = ET.fromstring(bytes(custom_XML_str, encoding="utf-8"), parser)
                    response = self.manager.create_custom_tool(trans, custom_XML, is_custom_XML=True)
                    return response
                elif isinstance(linting_response, list):
                    raise exceptions.RequestParameterInvalidException("\n".join(linting_response))
                else:
                    raise exceptions.InternalServerError("An unknown error occurred. Please contact an administrator.")

    
    @web.expose
    @expose_api_anonymous
    def update(self, trans, id, **kwd): #We can't just remove the id even if its useless here... The put endpoint only works with it.
        """
        * PUT /api/osug_tool_manager/update
            Format form values and send them to the manager
            to update a existing tool.

        :type   payload:    dict
        :param  payload:    dictionary structure containing (depending on is_custom_XML)::
            'id'            = Tool id
            'name'          = Tool name
            'group'         = Dict with group id and group name to associate with the tool
            'version'       = Tool version
            'description'   = Tool description
            'inputs'        = Tool inputs
            'outputs'       = Tool outputs
            'method_script' = Which method used to add a command script (typeCmd : user defined command script / scriptPath : generate command script from interpreter, path to script and inputs/outputs values)
            'command'       = User defined command script
            'interpreter'   = Interpreter used by the user's script
            'path_script'   = Path to the user script
            'url_git_repo'  = URL to the script git repository
            'git_commit_ID' = Script commit ID
            'git_tag'       = Script tag
            'is_custom_XML' = Is a custom XML made by the user ?
            'custom_XML'    = Custom XML made by the user

        ..note:
            Custom API (OSUG).

        :rtype:     string or exception
        :returns:   error or tool_id
        """
        payload = kwd.get("payload")
        if payload is None or (payload.get("is_custom_XML") and not payload.get("custom_XML")) or not payload.get("tool_id"): #Error if payload empty or if it's a custom XML, XML & tool id empty
            raise exceptions.RequestParameterInvalidException("Invalid request.")
        else:
            if not payload.get("is_custom_XML"): #From inputs
                formatted_payload = self.service_custom_tools.format_payload(trans, payload)
                if not isinstance(formatted_payload, str):
                    response = self.manager.update_custom_tool(trans, formatted_payload) 
                    return response
            else: #From custom XML editor
                custom_XML_str = payload.get("custom_XML")
                linting_response = self.service_linting.linting(trans, custom_XML_str, tool_id=payload.get("tool_id"))
                if type(linting_response)==bool and linting_response:
                    parser = ET.XMLParser(strip_cdata=False)
                    custom_XML = ET.fromstring(bytes(custom_XML_str, encoding="utf-8"), parser)
                    response = self.manager.update_custom_tool(trans, custom_XML, is_custom_XML=True)
                    return response
                elif isinstance(linting_response, list):
                    #return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": 400, "result": linting_response}) #Doesn't work... Why ? Not the last "layer"
                    raise exceptions.RequestParameterInvalidException("\n".join(linting_response))
                else:
                    raise exceptions.InternalServerError("An unknown error occurred. Please contact an administrator.")
    
    @web.expose
    @expose_api_anonymous
    def delete(self, trans, id):
        """
        * DELETE /api/osug_tool_manager/{tool_id}/delete
            Delete a tool associated with a group of the current user.

        :type   tool_id:    integer
        :param  tool_id:    Tool ID

        ..note:
            Custom API (OSUG).

        :rtype:     boolean or exception
        :returns:   Status message (ok/not ok)
        """

        #Get the tool
        toolbox = trans.app.toolbox
        tool = toolbox.get_tool(id)
        if tool is None:
            raise exceptions.ObjectNotFound(f"Tool id: '{id}' doesn't exist.")
        else:
            section_id = tool.get_panel_section()[0] #0 is ID, 1 is name

            #Check if one of the user groups has the ownership of the tool
            groups = self.service_groups.get_current_user_groups(trans)
            groups_id = [group["id"] for group in groups]

            if section_id in groups_id:
                tool_path = tool.tool_source.source_path
                delete_response = self.manager.delete_custom_tool(trans, tool_path)
                if type(delete_response) is str:
                    raise exceptions.InternalServerError(delete_response)
                else:
                    return True
            else:
                raise exceptions.RequestParameterInvalidException(f"The user doesn't have the ownership of the Tool id: '{id}'.")


