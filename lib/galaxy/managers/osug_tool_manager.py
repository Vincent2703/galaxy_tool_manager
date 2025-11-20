from os import path, makedirs
import os
from shutil import rmtree
import shutil
from galaxy import exceptions
import lxml.etree as ET
from pathlib import Path

import logging

from slugify import slugify

logging.basicConfig()
log = logging.getLogger()

class OsugToolManager:
    """Manager responsible of CRUD operations + generate xml code on custom tools"""

    """
        Return the XML of a tool from its path
    """
    def get_tool_XML(self, tool_path):
        try: 
            tool_file = open(tool_path, 'r')
            return tool_file.read()
        except OSError as error:
            raise exceptions.RequestParameterInvalidException(f"An error occurred while retrieving the tool XML ({error}). Please contact an administrator.")

    """
        From the payload (ElementTree XML object), generate the XML and return the code
    """
    def generate_XML_code(self, elementTreeXML):
        return ET.tostring(self._generate_XML(elementTreeXML), pretty_print=True, xml_declaration=True, encoding="utf-8").decode("utf-8") 

    """
        From the payload (dict with formatted inputs from the tool manager form), generate a XML object
    """
    def _generate_XML(self, payload):
        tool_params = {
            "name": payload.name, 
            "id": payload.id, 
            "version": payload.version,
        }
        if payload.is_expression_tool: #TODO: adaptation auto au tool-type?
            tool_params["tool_type"] = "expression"

        root = ET.Element("tool", tool_params)

        # Creator(s) section
        creator = ET.SubElement(root, "creator")
        for person in payload.creators_persons: # All the "editors"
            ET.SubElement(creator, "person", {
                "identifier": person.id,
                "email": person.email,
                "name": person.username,
            })

        group_owner = payload.group_owner # Group owner
        ET.SubElement(creator, "organization", {
            "identifier": group_owner.id,
            "name": group_owner.name,
            "alternateName": "owner",
        })

        guest_groups = payload.guest_groups
        for guest_group in guest_groups:
            ET.SubElement(creator, "organization", {
                "identifier": guest_group.id,
                "name": guest_group.name,
            })

        # Description
        ET.SubElement(root, "description").text = payload.description

        # Inputs
        inputs = ET.SubElement(root, "inputs")
        for input in payload.inputs:
            param_attrs = {
                "name": input.name,
                "type": input.type,
            }
            # Optional attributes
            if input.label:
                param_attrs["label"] = input.label
            if input.help:
                param_attrs["help"] = input.help
            if input.default_value:
                param_attrs["value"] = input.default_value
            if input.format:
                param_attrs["format"] = input.format
            if input.mandatory:
                param_attrs["optional"] = "false"

            #Add the param directly in inputs or in a section/repeat container
            if input.type_container == None:
                param = ET.SubElement(inputs, "param", param_attrs)
            else:
                container_name = input.name_container.lower()
                container_title = input.name_container.capitalize()
                #Find if there is already one with this name and add it to it
                container = None
                containers = inputs.find(input.type_container)
                if containers is not None:
                    container = inputs.find(f"{input.type_container}[@name='{container_name}']")
                if container is None:  #Create a new container if needed
                    container = ET.SubElement(inputs, input.type_container, {"name": container_name, "title": container_title})
            
                param = ET.SubElement(container, "param", param_attrs)


            if input.select_options:
                for option in input.select_options:
                    ET.SubElement(param, "option", {"value": option.value}).text = option.name

            # Validation
            if input.validation and hasattr(input, "validation_params"):
                if input.type == "text":
                    if input.validation_params.regex:
                        ET.SubElement(param, "validator", {"type":"regex"}).text = input.validation_params.regex
                    if input.validation_params.min > 0:
                        ET.SubElement(param, "validator", {"type":"length", "min":str(input.validation_params.min)})
                elif (input.type == "integer" or input.type == "float") and (input.validation_params.min or input.validation_params.max):
                    validation_params = {"type": "in_range"}
                    if input.validation_params.min:
                        validation_params["min"] = str(input.validation_params.min)
                    if input.validation_params.max:
                        validation_params["max"] = str(input.validation_params.max)
                    ET.SubElement(param, "validator", validation_params)
            

        # Outputs
        outputs = ET.SubElement(root, "outputs")
        for output in payload.outputs:
            if payload.is_expression_tool: # Tool is an expression tool
                output_params = {
                    "name": output.name,
                    "type": output.format,
                    "from": output.name,
                }
                ET.SubElement(outputs, "output", output_params)

            elif not output.is_collection: # Regular output
                output_params = {
                    "name": output.name,
                    "format": output.format,
                    "label": f"{output.name} ({tool_params['name']})",
                }
                ET.SubElement(outputs, "data", output_params)    
                  
            else: # Output is a discover_datasets collection
                collection = ET.SubElement(outputs, "collection", {
                    "name": output.name,
                    "type": "list",
                })

                discover_datasets_params = {
                    "directory": output.path,
                    "format": output.format,
                    "recurse": "true",
                    "visible": "true",
                    "pattern": output.pattern if output.pattern else '',
                }
                ET.SubElement(collection, "discover_datasets", discover_datasets_params)          

            # For each output, a path as an input
            if not payload.is_expression_tool:
                ET.SubElement(inputs, "param", {
                    "name": output.name+"__path",
                    "type": "text",
                    "value": output.path,
                    "optional": "false",
                    "label": f"{output.name} path",
                    "help": "What's the path of this output?"
                })    

        # Add 2 params : std_err & std_out
        for std_name in ["std_err", "std_out"]:
            ET.SubElement(outputs, "data", {
                "name": std_name,
                "label": std_name,
                "auto_format": "true",
                "hidden": "true",
            })

        # Command or expression script
        if not payload.is_expression_tool:
            command = ET.SubElement(root, "command")
            command.text = ET.CDATA(payload.command)
        else:
            expression = ET.SubElement(root, "expression", {"type":"ecma5.1"})
            expression.text = ET.CDATA(payload.expression)

        # Indent
        tree = ET.ElementTree(root)
        ET.indent(tree, space="\t", level=0)

        return tree

    """
        Create the XML file from a formatted payload and the path to the new tool
        return void
    """
    def _create_XML_tool_file(self, payload, tool_path, payload_is_XML):
        # Get the XML
        tree = payload.getroottree() if payload_is_XML else self._generate_XML(payload)
        
        # Save the XML file
        tree.write(tool_path, encoding="utf-8", xml_declaration=True)

    """
    Update the tool conf file. Needs the trans variable, the the path to the new tool and the group (id+name) associated with the tool
    """
    def _update_tool_conf(self, trans, tool_path, group_id, group_name):
        tool_conf_path = trans.app.config.tool_manager_tool_conf

        #Update the tool_conf file
        tree = ET.parse(tool_conf_path)
        root = tree.getroot()

        #Find or create a section
        section = root.find(f"section[@id='{group_id}']")
        if section is None:
            section = ET.SubElement(root, "section", {"id": group_id, "name": group_name})

        #Find or create the tool
        tool_path = Path(tool_path)
        num_parts_path = len(tool_path.parts)
        tool_path_from_tools_dir = str(Path(*tool_path.parts[-min(num_parts_path, 3):])) # Get the last two parents + filename OR less if parts < 3
        if not any(tool.get("file") == tool_path_from_tools_dir for tool in section.findall("tool")):
            ET.SubElement(section, "tool", {"file": tool_path_from_tools_dir})

        #Save the file
        ET.indent(tree, space="\t", level=0)
        tree.write(tool_conf_path, encoding="utf-8", xml_declaration=True)
    

    """
    Get the tool's filename from it's version and ID
    """
    def _get_tool_filename(self, tool_name, tool_version):
        return f"v_{tool_version}_{slugify(tool_name)}.xml"

    """
    Get the tool path from it's version and id
    Create the dirs if needed
    """
    def _get_tool_path(self, trans, tool_name, tool_version, tool_group_name):
        tools_path = trans.app.config.tool_manager_tools_dir
        if tools_path is None:
            log.debug("You must add the tool_manager_tools_dir option in the galaxy.yml")
            raise exceptions.RequestParameterInvalidException("An error occurred. Please contact the administrator.")
        #Generate filename
        filename = self._get_tool_filename(tool_name, tool_version)

        #Create path to the tool dir
        tool_dir_path = path.join(tools_path, tool_group_name, slugify(tool_name))

        #If directory doesn't exist, create it
        if not path.exists(tool_dir_path):
            makedirs(tool_dir_path)

        return path.join(tool_dir_path, filename)
    
    """
    Extract tool ID, version and group (name and ID) from a tool XML
    Used to create the right file while creating/updating a tool made from an user custom XML (not generated by the Tool Manager)
    """
    def _get_essentials_data_from_tool(self, tool):
        if tool is None:
            raise exceptions.RequestParameterInvalidException("An error occurred. Please contact the administrator. (Can't extract data from custom XML - tool is None)")

        is_elementTree = isinstance(tool, ET._Element)
        if is_elementTree: 
            if tool.find("creator") is not None and tool.find("creator").find("organization") is not None:
                group_owner = tool.find("creator").find("organization")
        elif hasattr(tool, "group_owner"): 
            group_owner = tool.group_owner
        else:
            raise exceptions.RequestParameterInvalidException("An error occurred. Please contact the administrator. (Can't extract data from custom XML - group is incorrect)")

        return {
            "id": tool.get("id") if is_elementTree else tool.id,
            "name": tool.get("name") if is_elementTree else tool.name,
            "version": tool.get("version") if is_elementTree else tool.version,
            "group_owner": {
                "id": group_owner.get("identifier") if is_elementTree else group_owner.id,
                "name": group_owner.get("name") if is_elementTree else group_owner.name,
            },
        }
    
    """
    Main function to add a new custom tool. Call _create_XML_tool_file to create the new XML file and _update_tool_conf to update the tool conf file.
    Needs the formatted payload with the tool data.
    return (str) tool id
    """
    def create_custom_tool(self, trans, payload, is_custom_XML=False):
        if not is_custom_XML: #Payload from tool manager form inputs
            tool_path = self._get_tool_path(trans, payload.name, payload.version, payload.group_owner.name)
            payload_group_owner_id = payload.group_owner.id
            payload_group_owner_name = payload.group_owner.name
        else: #Payload is custom XML (from the custom XML editor in the Tool Manager)
            tool_data = self._get_essentials_data_from_tool(payload)
            tool_path = self._get_tool_path(trans, tool_data["name"], tool_data["version"], tool_data["group_owner"]["name"])
            payload_group_owner_id = payload.find("creator").find("organization").get("identifier")
            payload_group_owner_name = payload.find("creator").find("organization").get("name")

        self._create_XML_tool_file(payload, tool_path, is_custom_XML)
        self._update_tool_conf(trans, tool_path, payload_group_owner_id, payload_group_owner_name)

        return tool_data["id"] if is_custom_XML else payload.id



    """
    Main function to update a custom tool. Use the same functions as create_custom_tool.
    return (str) tool id
    """
    def update_custom_tool(self, trans, payload, is_custom_XML=False):
        tool_data = self._get_essentials_data_from_tool(payload)
        
        tool = trans.app.toolbox.get_tool(tool_data["id"], exact=True)

        user_is_in_tool_groups = False #Check user has the permission to edit the tool
        user_groups = [trans.security.encode_id(group.group_id) for group in trans.user.groups]

        old_tool_group_owner_id = None
        old_tool_group_owner_name = None
        if tool is not None: #Check tool existance
            for creator in tool.creator: #creatorS
                if creator["identifier"] in user_groups:
                    user_is_in_tool_groups = True

                if "alternateName" in creator:
                    old_tool_group_owner_id = creator["identifier"]
                    old_tool_group_owner_name = creator["name"]
            
            if not user_is_in_tool_groups:
                raise exceptions.InsufficientPermissionsException("You can't update this tool because you are not in one of its groups.")

            if old_tool_group_owner_id == None or old_tool_group_owner_name == None:
                raise exceptions.ObjectAttributeInvalidException("Can't find the tool's owner group.")

            tool_path = self._get_tool_path(trans, tool_data["name"], tool_data["version"], old_tool_group_owner_name) # Get the tool dir
            if old_tool_group_owner_id != tool_data["group_owner"]["id"]: #If not the same group as before
                #We move all the tool versions in the new directory
                self._move_tools_group(
                    trans, 
                    current_tools_dir=tool.tool_dir, 
                    current_group_name=old_tool_group_owner_name, 
                    new_group_name=tool_data["group_owner"]["name"], 
                    new_group_id=tool_data["group_owner"]["id"]
                )

                tool_path = self._get_tool_path(trans, tool_data["name"], tool_data["version"], tool_data["group_owner"]["name"]) #new tool path

            self._create_XML_tool_file(payload, tool_path, is_custom_XML)
            self._update_tool_conf(trans, tool_path, tool_data["group_owner"]["id"], tool_data["group_owner"]["name"])
            return tool_data["id"]
        else:
            message = f"The tool '{tool_data['id']}' was not found. The ID must be the same than previously."
            raise exceptions.ObjectAttributeInvalidException(message)
    
    """
    Move the tools from a group to another
    """
    def _move_tools_group(self, trans, current_tools_dir, current_group_name, new_group_name, new_group_id):
        tool_conf_path = trans.app.config.tool_manager_tool_conf
        
        #Tool conf file
        tree = ET.parse(tool_conf_path)
        root = tree.getroot()

        new_tools_dir = current_tools_dir.replace(current_group_name, new_group_name)

        #Move the files
        if not os.path.exists(new_tools_dir):
            os.makedirs(new_tools_dir)

        for filename in os.listdir(current_tools_dir):
            src_file = path.join(current_tools_dir, filename)
            dest_file = path.join(new_tools_dir, filename)

            if os.path.isfile(src_file):
                shutil.move(src_file, dest_file) #Move the file
            
            #"Move" it in the tool conf

            relative_tool_path = Path(*Path(src_file).parts[-3:]) #Get the last 3 parts of the tool path (group/toolName/v_x.x_toolID)
            sections = root.findall("section")
            for section in sections: #reprendre ici. Pourquoi ça ne supprime pas les tools du tool conf ?
                tools = section.findall("tool")
                for tool in tools:
                    if tool.get("file") == str(relative_tool_path):
                        tool.getparent().remove(tool)

            #Find or create a section
            section = root.find(f"section[@id='{new_group_id}']")
            if section is None:
                section = ET.SubElement(root, "section", {"id": new_group_id, "name": new_group_name})

            #Create the tool
            new_relative_tool_path = str(relative_tool_path).replace(current_group_name, new_group_name) #We just have to replace the old group name in the path by the new one
            ET.SubElement(section, "tool", {"file": new_relative_tool_path})
            
        #Remove the tool dir
        os.rmdir(current_tools_dir)
        
        #Save the tool conf
        ET.indent(tree, space="\t", level=0)
        tree.write(tool_conf_path, encoding="utf-8", xml_declaration=True)

    """
    Function to delete a tool from its path.
    return true on success
    """
    def delete_custom_tool(self, trans, tool_path):
        tool_conf_path = trans.app.config.tool_manager_tool_conf
        if tool_conf_path is None:
            raise exceptions.RequestParameterInvalidException("An error occurred. Please contact the administrator.")
        try:
            #Check file exists
            if path.exists(tool_path):
                #Delete the folder and its content
                parent_dir = path.dirname(tool_path)
                tool_dir_name = path.basename(parent_dir).rpartition('/')[-1]

                rmtree(parent_dir)

                #Update tool conf file
                tree = ET.parse(tool_conf_path)
                root = tree.getroot()

                #Delete the corresponding item
                for section in root.findall(".//section"):
                    for tool in section.findall("tool"):
                        if tool_dir_name in tool.get("file"):
                            section.remove(tool)
                            #Save the XML file
                            ET.indent(tree, space="\t", level=0)
                            tree.write(tool_conf_path)
                return True
            else:
                message = f"File '{tool_path}' not found."
                raise exceptions.RequestParameterInvalidException(message)
        
        #return errors
        except ET.ParseError as e:
            message = f"Parsing error: {str(e)}"
            raise exceptions.RequestParameterInvalidException(message)
        
        except Exception as e:
            message = f"An error occurred: {str(e)}"
            raise exceptions.RequestParameterInvalidException(message)

