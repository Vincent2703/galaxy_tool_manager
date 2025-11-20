import logging

logging.basicConfig()
log = logging.getLogger()

from galaxy.schema.fields import Security


def restrict_tools_groups(context, tool):
    """
        This tool filter will disable all custom tools linked to 
        a role that the user does not have except those with no creator
    """
    user = context.trans.user

    if tool.creator is None: # If tool has no creator, display it to everyone
        return True  
    
    if user is not None: # If user logged
        user_group_ids = {Security.security.encode_id(group.group_id) for group in user.groups}

        tool_groups = [creator for creator in tool.creator if creator["class"] == "Organization"]

        # Is one of the tool groups one of the user groups ?
        for tool_group in tool_groups:
            if tool_group["identifier"] in user_group_ids:
                return True

        return False # Do not display it otherwise
