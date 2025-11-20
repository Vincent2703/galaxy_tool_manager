
import logging
import subprocess

import xml.etree.ElementTree as ET

import tempfile

import re

from lib.galaxy.util.template import fill_template

logging.basicConfig()
log = logging.getLogger()

class OsugLintingService:
    """Service responsible of linting (tool XML validation)"""
    
    def linting(self, trans, XML_content, tool_id=None, osug_rules=True, check_templating=True):    
        """Main function for tool validation.
        1) Check XML structure
        2) Check custom rules (like permissions, mandatory tags...)
        3) Planemo checking (official Galaxy validation lib)
        4) Check templating typo (eg: ${var_naame} instead of ${var_name})

        Args:
            trans: Info about the context
            XML_content (string): 
            tool_id (string, optional). Defaults to None.
            osug_rules (bool, optional): Check against our custom rules? Defaults to True.
            check_templating (bool, optional): Check templating? Defaults to True.

        Returns:
            boolean or string list : True or list of errors
        """
        errors = []

        is_edit = tool_id!=None #If there is already a tool ID, that means a tool is already created

        try: #We must parse the XML before the linting (Planemo doesn't return any message if the XML is malformed)
            elementTreeXML = ET.ElementTree(ET.fromstring(XML_content))
        except ET.ParseError as error:
            return [f"Parsing error : {error}"]
        
        #TODO: check if user has the right to edit the tool (is in one of the orga)
                
        if osug_rules:
            #If the tool already exists, we need some info from the current tool instance to use our custom rules
            previous_tool_data = None
            if is_edit:
                current_tool_instance = trans.app.toolbox.get_tool(tool_id, exact=True)
                if current_tool_instance is None:
                    return [f"There is no tool '{tool_id}' created."]
                else:
                    previous_tool_data = {
                        "version": current_tool_instance.version, 
                        "group_owner": None, 
                        "guest_groups": [],
                    }
                    log.debug(previous_tool_data)
                    for group in current_tool_instance.creator:
                        if "alternateName" in group and group["alternateName"] == "owner":
                            previous_tool_data["group_owner"] = group["identifier"]
                        else:
                            previous_tool_data["guest_groups"].append(group["identifier"])

            osug_rules_errors = self._check_osug_rules(trans, elementTreeXML, tool_id, previous_tool_data) #Check custom rules (defined in _check_osug_rules)
            if len(osug_rules_errors) > 0:
                errors += osug_rules_errors
            
        if check_templating:
            templating_errors = self._check_templating(trans.user, elementTreeXML, stringXML=XML_content) #If templating used, is it correct ?
            if len(templating_errors) > 0:
                errors += templating_errors
        
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".xml") as temp_tool: #We need to put the xml in a temp file for Planemo (deleted after the with block)
            temp_tool.write(XML_content)
            temp_tool.close() #Need to close it to be able to read it

            planemod_cmd = f"planemo lint {temp_tool.name} --report_level error --fail_level error"

            try:
                result = subprocess.run(
                    planemod_cmd, 
                    shell=True, 
                    stdout=subprocess.PIPE,
                    #stderr useless : Contains just "linting failed"
                )
            except subprocess.CalledProcessError as error:
                return [f"An error occurred while validating the tool ({error}). Please contact an administrator."]

        stdout_output = result.stdout.decode() #Contains the errors

        exit_code = result.returncode

        if exit_code != 0:
            planemo_errors = stdout_output.split('\n')[1:-1] #It's a list separated by \n and we need to remove the first one and the last one which are useless
            planemo_errors_cleaned = [re.sub(r"^\.{2}.+\): ", '', error) for error in planemo_errors] #It's better to remove some useless info 
            errors += planemo_errors_cleaned
        
        return len(errors) == 0 or errors
    
    
    def _check_templating(self, user, elementTreeXML, stringXML): #Can only return the first error encountered
        """Check templating is correct.
        Get the templating from the inputs and outputs

        Args:
            user: Current user instance
            elementTreeXML (etreeLxml): Tool XML etreeLxml instance
            stringXML (string): Tool XML as a string

        Returns:
            string list: errors
        """
        errors = []
        templating_dict = {"__user__": user}

        inputs = elementTreeXML.find("inputs")
        outputs = elementTreeXML.find("outputs")
        if inputs is not None:
            for input in inputs.findall(".//param") + inputs.findall("section"): #.// for recursivity
                if input.get("name") is not None:
                    templating_dict[input.get("name")] = input.get("value", None)
            for output in outputs.findall(".//data") + outputs.findall("collection"):
                if output.get("name") is not None:
                    templating_dict[output.get("name")] = None

        
        if len(templating_dict) > 0:
            try:
                fill_template(stringXML, templating_dict)
            except Exception as error:
                extract_error_match_regex = re.match('^\w+\("(.+)"\)$', repr(error))
                if extract_error_match_regex is not None:
                    cleaned_error = extract_error_match_regex.group(1)

                errors = [f"Templating error : {repr(cleaned_error) or error}."]

        return errors

        
    def _check_osug_rules(self, trans, etreeXML, tool_id, previous_tool_data):
        """Check our custom rules as permissions, mandatory tags for us and so on.

        Args:
            trans: Info about the context
            etreeXML (etreeXML): Tool XML instance
            tool_id (string)
            previous_tool_data (dict): Some info about the tool before the current update

        Returns:
            string list: List of errors
        """
        errors = []
        is_edit = tool_id!=None #If there is already a tool ID, that means a tool is already created
        tool = etreeXML.getroot()

        #Checking mandatory tags and attributes (command is already checked by Planemo)
        creator = etreeXML.find("creator")
        if creator is None:
            errors.append("Creator tag is missing.")
        else:
            if creator.find("person") is None:
                errors.append("Person tag is missing in <creator>.")
            else:
                person = creator.find("person")
                if person.get("identifier") is None:
                    errors.append("Identifier attribute is missing for <person>.")
                if person.get("email") is None:
                    errors.append("Email attribute is missing for <person>.")
                if person.get("name") is None:
                    errors.append("Name attribute is missing for <person>.")

            if creator.find("organization") is None:
                errors.append("Organization tag is missing in <creator>.")
            else:
                organization = creator.find("organization")
                if organization.get("identifier") is None:
                    errors.append("Identifier attribute is missing for <organization>.")
                if organization.get("name") is None:
                    errors.append("Name attribute is missing for <organization>.")
        
        if etreeXML.find("description") is None:
            errors.append("Description tag is missing.")

        if etreeXML.find("command") is None:
            errors.append("Command tag is missing.")

        #Config files forbidden
        if etreeXML.find("configfiles") or etreeXML.find("configfile"):
            errors.append("Configfile(s) are forbidden.")


        if len(errors) > 0: #We can stop right here if we already have errors because of missing tags
            return errors
        
        #Version must be numeric (x.x)
        version_is_numeric = True
        if re.fullmatch(r'^[0-9]+\.[0-9]+$', tool.get("version")) is None:
            version_is_numeric = False
            errors.append(f"The version must be writed in the form 'x.x'")

        elif is_edit: #If it's an edit...
                #ID must be the same if it's an edit
                if tool.get("id") != tool_id:
                    errors.append(f"Can't change the tool's ID ({tool_id}).")

                #Version must be superior
                new_version = tool.get("version").split('.') #[0] is major part and [1] minor (or decimal) part
                old_version = previous_tool_data["version"].split('.')


                new_version_is_superior = True
                if int(new_version[0]) < int(old_version[0]): # The int part mustn't be less than before
                    new_version_is_superior = False

                if int(new_version[0]) == int(old_version[0]) and int(new_version[1]) <= int(old_version[1]): # The decimal part mustn't be equal or less than before
                        new_version_is_superior = False

                if version_is_numeric and not new_version_is_superior:
                    errors.append(f"The version ({tool.get('version')}) must be superior to the previous one ({previous_tool_data['version']}).")
                    
        # If the user is in the owner group, he has all rights
        # If it's not in it (and that we checked before if it's in one of the groups)
        # Then we don't give it the authorizaton to update the groups

        XML_groups = etreeXML.find("creator").findall("organization") # All groups

        # Group owner
        XML_group_owner_id = None 
        XML_group_owner_name = None

        XML_shared_with_groups = [] # Tool is shared with these groups

        groups_are_updated = False

        # Get them
        for XML_group in XML_groups:
            is_owner = XML_group.get("alternateName") == "owner"
            
            if is_owner:
                XML_group_owner_id = XML_group.get("identifier")
                XML_group_owner_name = XML_group.get("name")
            else:
                XML_shared_with_groups.append(XML_group.get("identifier"))

        if is_edit:
            # Is groups updated ?
            if XML_group_owner_id != previous_tool_data["group_owner"]:
                groups_are_updated = True

            if sorted(XML_shared_with_groups) != sorted(previous_tool_data["guest_groups"]):
                groups_are_updated = True

            # If update, check that the user has the permission to do so
            if groups_are_updated:
                user_has_permission = False

                current_user_groups_id = [trans.security.encode_id(group.group_id) for group in trans.user.groups]

                if XML_group_owner_id in current_user_groups_id: # If user is in owner group, it has the permission
                    user_has_permission = True

                if not user_has_permission:
                    errors.append(f"You don't have the right to change the tool groups. You are not in the '{XML_group_owner_name}' group owner.")

        #Has mandatory custom params ? Just {output}_path now
        inputs = etreeXML.find("inputs").findall("param")
        if not inputs is None:
            outputs = etreeXML.find("outputs").findall("data")

            outputs_to_ignore = ["std_err", "std_out"] # Special outputs
            for data in outputs:
                if not data.get("name") in outputs_to_ignore:
                    if not any(param.get("name") == data.get("name")+"__path" for param in inputs):
                        errors.append(f"Each output must have a corresponding input __path. Please add a {data.get('name')}_path input.")
        
        return errors