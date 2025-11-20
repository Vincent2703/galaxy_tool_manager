from galaxy import exceptions
from galaxy.schema.schema import UserModel
from galaxy.webapps.galaxy.services.base import ServiceBase
from galaxy.model.db.user import get_user_by_email
from lib.galaxy.schema.custom_tool import ToolCreateSchema, ToolGroup, ToolInput, ToolOutput
from slugify import slugify
from galaxy.schema.fields import Security

import logging
log = logging.getLogger(__name__)


class OsugCustomTools(ServiceBase):
    def format_payload(self, trans, payload):
        """Format the tool payload before sending it to the manager"""
        is_edit = not payload.get("version") == "1.0" # If version == 1 -> new tool
    
        payload_inputs = payload.get("inputs", [])
        payload_outputs = payload.get("outputs", [])

        is_expression_tool = payload.get("is_expression_tool")

        # First validations...

        # Check mandatory inputs not empty
        # Can't use a schema ? Conditions to manage so no. Better messages too
        if not payload.get("name") or payload.get("name").strip() == '':
            message = "The name should not be empty."
            raise exceptions.ObjectAttributeMissingException(message)
        if not payload.get("description") or payload.get("description").strip() == '' :
            message = "The description should not be empty."
            raise exceptions.ObjectAttributeMissingException(message)
        if not payload.get("group_owner") or (payload.get("group_owner")["id"].strip() == '' or payload.get("group_owner")["name"].strip() == ''):
            message = "The tool must be owned by a group."
            raise exceptions.ObjectAttributeMissingException(message)
        if not is_expression_tool:
            if payload.get("method_script") == "scriptPath":
                if not payload.get("interpreter") or not payload.get("path_script") or payload.get("interpreter").strip() == '' or payload.get("path_script").strip() == '':
                    message = "The path to the script and/or the interpreter parameters are empty."
                    raise exceptions.ObjectAttributeMissingException(message)
            if not payload.get("command") or payload.get("command").strip() == '':
                message = "The command parameter is empty."
                raise exceptions.ObjectAttributeMissingException(message)
        else:
            if not payload.get("expression") or payload.get("expression").strip() == '':
                message = "The expression script is empty."
                raise exceptions.ObjectAttributeMissingException(message)

        # Tool ID
        if not is_edit: #It's a tool creation
            slugified_name = slugify(f"{payload.get('group_owner')['name']}_{payload.get('name')}") #Use the group name as a prefix and sanitize the all
            tool_id = slugified_name
            if trans.app.toolbox.has_tool(tool_id): # If the tool id already exists
                message = "A tool has already the same name."
                raise exceptions.RequestParameterInvalidException(message)
        else: #It's an edit
            if payload.get("tool_id") and payload.get("tool_id").strip() != '':
                tool_id = payload.get("tool_id")
            else:
                message = "Incorrect parameter (tool_id). Please, contact the administrator."
                raise exceptions.RequestParameterInvalidException(message)
        
        # Each output need a path if it's not in a expression tool
        if not is_expression_tool:
            for output in payload_outputs:
                if output["path"] == None or output["path"].strip() == '':
                    message = f"The output {output['name']} must be associated with a path."
                    raise exceptions.ObjectAttributeMissingException(message)

        group_owner = ToolGroup(**payload.get("group_owner")) # ** means dict --> args
        if not group_owner:
            message = "The selected group doesn't exist."
            raise exceptions.RequestParameterInvalidException(message)

        guest_groups = []
        for group in payload.get("guest_groups"):
            try:
                tool_group = ToolGroup(**group)
                guest_groups.append(tool_group)
            except Exception as e:
                message = f"The tool is shared with a group that doesn't exist ({group.name})."
                raise exceptions.RequestParameterInvalidException(message)

        creators_persons = []
        current_user = UserModel(**trans.user.to_dict())
        if is_edit: # If it's an edit, it could have several creators (persons)
            all_creators = trans.app.toolbox.get_tool(tool_id, exact=True).creator
            for creator in all_creators:
                if creator["class"] == "Person": # We don't want the groups
                    user = get_user_by_email(trans.sa_session, creator["email"]).to_dict()
                    creators_persons.append(UserModel(**user))
        if current_user not in creators_persons:
            creators_persons.append(current_user)

        # The tool manager saves a few hidden inputs to allow the api/tools endpoint 
        # to retrieve values such as user script, interpreter, command and validators.
        # We need to check if the user doesn't want to add inputs with the same ids.

        if any(input["name"].startswith("osugTM_") for input in payload_inputs):   
            message = "You cannot use a name starting by 'osugTM_' for your inputs."
            raise exceptions.RequestParameterInvalidException(message)

        try: 
            tool_inputs = [ToolInput(**input) for input in payload_inputs] # Create a list of ToolInput (schema Pydantic) from inputs dicts
        except Exception as e:
            message = f"Error in the tool's structure: {e}"
            raise exceptions.InternalServerError(message)

        try:
            tool_outputs = [ToolOutput(**output) for output in payload_outputs] # Create a list of ToolOutput (schema Pydantic) from inputs dicts
        except Exception as e:
            message = f"Error in the tool's structure: {e}"
            raise exceptions.InternalServerError(message)

        tool_cmd = ''
        expression_cmd = ''
        if not payload.get("is_expression_tool"): # Regular tool
            tool_cmd = payload.get("command")
            if payload.get("method_script") == "scriptPath": # If the user wants to use an externals script
                interpreter     = payload.get("interpreter")
                path_script     = payload.get("path_script")
                url_git_repo    = payload.get("url_git_repo")
                git_commit_ID   = payload.get("git_commit_ID")
                git_tag         = payload.get("git_tag")

                if interpreter is not None:
                    # Add tool manager hidden inputs to be able to use the api/tools endpoint to get these values (and edit them in the Tool Manager)
                    tool_cmd.replace(interpreter, "$osugTM_interpreter")
                    tool_inputs.append(ToolInput(name="osugTM_interpreter",     type="hidden", default_value=interpreter))
                if path_script is not None:
                    # Same here
                    tool_cmd.replace(path_script, "$osugTM_path_script")
                    tool_inputs.append(ToolInput(name="osugTM_path_script",     type="hidden", default_value=path_script))
                if url_git_repo is not None:
                    tool_inputs.append(ToolInput(name="osugTM_url_git_repo",    type="hidden", default_value=url_git_repo))
                if git_commit_ID is not None:
                    tool_inputs.append(ToolInput(name="osugTM_git_commit_ID",   type="hidden", default_value=git_commit_ID))
                if git_tag is not None:
                    tool_inputs.append(ToolInput(name="osugTM_git_tag",         type="hidden", default_value=git_tag))

            else:
                # Expression script
                expression_cmd = payload.get("expression")

        try:
            tool_data = ToolCreateSchema( # Validate the structure of the tool
                name=payload.get("name"),
                id=tool_id,
                is_expression_tool=payload.get("is_expression_tool"),
                group_owner=group_owner,
                guest_groups=guest_groups,
                creators_persons=creators_persons,
                version=payload.get("version"),
                description=payload.get("description"),
                inputs=tool_inputs,
                outputs=tool_outputs,
                command=tool_cmd,
                expression=expression_cmd,
            )

            return tool_data
        except Exception as e:
            message = f"Uncatched error, please contact an administrator: {e}"
            raise exceptions.InternalServerError(message)
        
    def get_tool_path_from_tool_ID(self, trans, tool_ID):
        tool = trans.app.toolbox.get_tool(tool_ID)
        if not tool:
            raise exceptions.ObjectNotFound(f"Could not find tool with id '{id}'.")
        return tool.config_file
    

    def get_tools_shared_with_user(self, trans):
        # Get all tools
        all_tools = trans.app.toolbox.tools()

        user_group_ids = {Security.security.encode_id(group.group_id) for group in trans.user.groups}

        # Use set to avoid handling the duplicates (duplicates if the tool is shared between several groups)
        tools_filtered = set()

        for tool in all_tools:
            tool_instance = tool[1] # Because it's a tuple
            if tool_instance.creator:  # If tool has creator(s)
                # Check if any of these creators (orga = group) is one of the user group
                if any(creator["class"] == "Organization" and creator["identifier"] in user_group_ids for creator in tool_instance.creator):
                    tools_filtered.add(tool_instance)

        # We sort by tool dir (= by group but also by id, which is in the filename)
        tools_filtered_sorted = sorted(tools_filtered, key=lambda tool: tool.tool_dir)

        # We convert the tools in dicts to be able to return them
        tool_filtered_sorted_jsonable = [tool.to_dict(trans, io_details=True, tool_help=True) for tool in tools_filtered_sorted]

        return tool_filtered_sorted_jsonable
