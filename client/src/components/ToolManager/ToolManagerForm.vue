<script>
import { RouterLink } from "vue-router"; // Quickly redirect the user after a click on a button
import { GalaxyApi } from "@/api"; // Custom galaxy function to handle the API endpoints

// Reusable components
import Input from "./formTabsContent/input/Input.vue";
import Output from "./formTabsContent/output/Output.vue";

import vSelect from "vue-select";
import "vue-select/dist/vue-select.css";

import { loader, useMonaco, VueMonacoEditor } from "@guolao/vue-monaco-editor";
import * as monaco from "monaco-editor";


export default {
  components: { vSelect, VueMonacoEditor, Input, Output }, //Components used here
  props: { //URL params declared in router.js
    id: null, //To get the tool id if it's an edit
    duplicate_from: null, //Get the tool id if it's a duplicate
  },
  data() {
    return {
      /* Info on the current user */
      user_is_admin: false,
      user_is_owner: false, //Owner of the tool
      user_can_edit: false, //Has the permission ?
      user_groups: [],

      /* Info on the tool */

      //General
      is_edit: this.id != null, //Is a new version of the tool
      is_duplicate: this.duplicate_from != null, //Is a duplicate from another tool

      tool_id: this.id, //The ID will be generated from the the tool name and prefixed by the group owner name
      tool_name: null,
      tool_description: null,
      is_expression_tool: false,

      tool_version: "1.0", //1.0 unless it's an edit
      previous_version: null, //Store the tool version on page loading before it's updated, if it's an edit
      new_minor_version: null, //Store the new minor version (x.x+1)
      new_major_version: null, //Store the new major version (x+1.x)
    
      all_available_groups: [],
      tool_group_owner_id: null,
      tool_group_owner_name: null,
      guest_groups: [],

      //Inputs
      tool_inputs: [],
      tool_inputs_containers: { //List of inputs containers (section/repeat)
        "repeats": [{"label": "None", "value": null}],
        "sections": [{"label": "None", "value": null}]
      },

      //Outputs
      tool_outputs: [],

      //Script
      selected_method_script: "scriptPath", //The user can directly paste its bash command or it can specify a path to a script with additional info
      tool_command: null, //Either way, the command is editable
      tool_expression_script: '{}', //If the tool is an expression tool, the user can put its javascript inside {} here

      tool_path_exec: null, //Path to the executable
      tool_exec_interpreter: null, //Interpreter to launch the script
      tool_url_git_repo: null,
      tool_git_commit_ID: null,
      tool_git_tag: null,

      tool_command_templating_errors: [],

      //XML editor
      tool_custom_XML: null, //Content
      tool_custom_XML_modal: false, //Display the modal ?
      tool_custom_XML_validation_loading: false, //To display a spinner while loading
      tool_custom_XML_validation_errors: null, //Store the errors
      xml_editor_options : {
        tabSize: 4,
        theme: "default",
        viewportMargin: Infinity,
        mode: "application/xml",
        lineNumbers: true,
        indentWithTabs: true,
        autoCloseTags: true,
      },

      //Alerts
      alert_status: null, //Success or error ?
      alert_msg: null, //Content of the error
      alert_redirection_url: null, //Redirect to the tool execution page

      //Form validation errors
      nb_errors: 0,
      save_button_activation: true,

      //What's the current active navigation tab ?
      active_tab: "general",

      //Display a spinner while the page is loading
      page_loading: true,
    };
  },
  methods: {
    /*                                            */
    /* Get some general info about the user       */
    /* (and every groups if the user is an admin) */
    /*                                            */

    /* Is the current user admin ? */
    async is_user_admin() {
      const { data: userData, error: userError } = await GalaxyApi().GET("/api/whoami"); //To get the user ID

      if(userError) {
        this.alert_msg = userError.err_msg;
        this.alert_status = "error";
      }else {
        const user_id = userData.id;

        const { data: userDetailData, error: userDetailError } = await GalaxyApi().GET(`/api/users/${user_id}`);

        if(userDetailError) {
          this.alert_msg = userDetailError.err_msg;
          this.alert_status = "error";
        }else {
          this.user_is_admin = userDetailData.is_admin; //Is admin ?
        }
      }
    },

    /* Get the user groups */
    async get_user_groups() {
      const { data, error } = await GalaxyApi().GET("/api/osug_groups"); //Custom endpoint because /groups is only for admins. Here we only get the current user groups
      if(error) {
        this.alert_msg = error.err_msg;
        this.alert_status = "error";
      }else {
        data.sort((a, b) => { // Sort by name
          if (a.name < b.name) return -1;
          if (a.name > b.name) return 1;
          return 0;
        });
        return data;
      }
    },

    /* Get all the groups (instead of getting the user groups, if the user is an admin) */
    async get_all_groups() {
      const { data, error } = await GalaxyApi().GET("/api/groups");
      if(error) {
        this.alert_msg = error.err_msg;
        this.alert_status = "error";
      }else {
        return data;
      }
    },

    /*                                                        */
    /* Get the tool data (tool edition) and populate the form */
    /*                                                        */

    //Get most of the data we need
    async get_tool_data(tool_id) {
      const { data, error } = await GalaxyApi().GET(`/api/tools/${tool_id}?io_details=true`); //Base endpoint
      if(error) {
        this.alert_msg = `An error occurred while retrieving the tool: ${error.err_msg}`;
        this.alert_status = "error";
      }else {
        return data;
      }
    },

    /* We still need to get the content of the tool XML file. 
    Put in in the editor but it's also used to extract the command and pattern validations from it 
    (Avoid having special <param> to be able to retrieve the information from the base endpoint) */
    async get_xml_content_from_tool_file(tool_id, is_duplicate=False) {
      let { data, error } = await GalaxyApi().GET(`/api/osug_tool_manager/get_tool_xml/${tool_id}`); //Custom endpoint, get the XML
      if(error) {
        this.alert_msg = `An error occurred while retrieving the tool XML: ${error.err_msg}`;
        this.alert_status = "error";
      }else {
        if(is_duplicate) { //It's a new duplicate from another tool
          data = data.replace(/id=".+" /g, 'id="" '); //Empty the ID
          data = data.replace(/version="[0-9]+\.[0-9]+"/g, 'version="1.0"'); //Reset the version
        }
        return data;
      }
    },

    /* Fill the form inputs from the tool data */
    async updt_form_frm_tool_data(tool_data) {            
      this.tool_custom_XML = await this.get_xml_content_from_tool_file(tool_data.id, this.is_duplicate); // Fill the XML editor with the XML content

      this.tool_name = tool_data.name;
      this.tool_description = tool_data.description;

      this.is_expression_tool = tool_data.model_class	=== "ExpressionTool";

      // Extract some data from the XML file (can't get it directly from the /tools/{tool_id} endpoint)

      // Parse XML tool
      const parser = new DOMParser();
      const tool_XML = parser.parseFromString(this.tool_custom_XML, "text/xml");

      // Extract command or expression
      if(this.is_expression_tool) {
        const expr_tag = tool_XML.querySelector("expression[type='ecma5.1']");
        this.tool_expression_script = expr_tag?.textContent?.trim() ?? null;
      }else {
        const cmd_tag = tool_XML.querySelector("command");
        this.tool_command = cmd_tag?.textContent?.trim() ?? null;
      }

      // Extract guest groups
      const orga_tags = tool_XML.querySelectorAll("organization");
      orga_tags.forEach(orga => {
        const identifier = orga.getAttribute("identifier");
        const name = orga.getAttribute("name");

        const altName = orga.getAttribute("alternateName");

        if(altName != "owner" && identifier && name) {
          this.guest_groups.push({ id: identifier, name: name });
        }
      });

      // Extract validators
      let validators = {};
      const validator_tags = tool_XML.querySelectorAll("validator");

      validator_tags.forEach(validator => {
        const input_name = validator.parentElement.getAttribute("name");
        const validator_type = validator.getAttribute("type");

        if(!validators[input_name]) {
          validators[input_name] = {};
        }

        if(["length", "in_range"].includes(validator_type)) {
          const list_validation_attributes = ["min", "max"];
          list_validation_attributes.forEach(attr_name => {
            if (validator.hasAttribute(attr_name)) {
              validators[input_name][attr_name] = validator.getAttribute(attr_name);
            }
          });

        }else if (validator_type === "regex") {
          validators[input_name]["regex"] = validator.textContent?.trim();
        }
      });


      tool_data.inputs.forEach((input) => {
        //There are some special inputs. For things we can't store in a tool XML or can't get from the base endpoint /tools/{tool_id}
        if(input.name === "osugTM_interpreter") { //The interpreter used for the user's script
          this.tool_exec_interpreter = input.value;

        }else if(input.name === "osugTM_url_git_repo") {
          this.tool_url_git_repo = input.value;

        }else if(input.name === "osugTM_git_commit_ID") {
          this.tool_git_commit_ID = input.value;

        }else if(input.name === "osugTM_git_tag") {
          this.tool_git_tag = input.value;

        }else if(input.name === "osugTM_path_script") { //The path to the user's script
          this.tool_path_exec = input.value;

        }else if(!input.name.endsWith("__path") && input.name != "__job_resource") { //Inputs __job_resource and the ones that ends by __path are not user defined and we don't need them in the form
          let input_params = {};
          let inputs_in_container = input.inputs;

          //If we have inputs inside a container (repeat/section).
          if(["repeat", "section"].includes(input.type)) {

            inputs_in_container.forEach((input_in_container) => {
              input_params = this.create_input_params(input_in_container, input.type, input.name); //Return a dict used by add_input
              this.add_input(input_params); //We add the input in the form, with the right container
            });

          }else{ //Input not in a container
            if(input.type == "conditional") { //But inside a conditional (we don't handle the conditionals in the form, we just extract the inputs in them)

              // The input(s) inside the condition
              input.cases.forEach(when => {
                when.inputs.forEach(input => {
                  //Container inside the conditional
                  if(["repeat", "section"].includes(input.type)) {

                    input.inputs.forEach(input_inside_container => {
                      input_params = this.create_input_params(input_inside_container, input.type, input.name);
                      this.add_input(input_params);

                    });
                  }else {
                    //Directly the input inside the conditional
                    input_params = this.create_input_params(input);
                    this.add_input(input_params);
                  }
                });
              });
              // The tested input (its value is used for the conditional)
              input_params = this.create_input_params(input.test_param);
              this.add_input(input_params);

            }else { //Standard input
              input_params = this.create_input_params(input);
              this.add_input(input_params); //We add the input in the form
            }
          }
        }
      });

      //By default, if there is no interpreter and script path saved, the user is invited to paste its bash command in the tool command text area
      if(this.tool_exec_interpreter == null && this.tool_path_exec == null) {
        this.selected_method_script = "typeCmd";
      }

      tool_data.outputs.forEach((output) => { //Retrieve the outputs attributes        
        if(!["std_err", "std_out"].includes(output.name)) { // No need to get these special outputs
          const output_params = this.create_output_params(output, tool_data.inputs); //sec arg temp ? TODO
          this.add_output(output_params); //Add them to the form
        }
      });

      Object.keys(validators).forEach((input_validator_name) => { //Add each validator to the form in the corresponding inputs
        const input = this.tool_inputs.find((input) => input.name == input_validator_name); //Get the corresponding input...
        if(input) {
          input.validation_params = validators[input_validator_name];
          input.validation = true;
        }
      });

      this.tool_group_owner_id = tool_data.panel_section_id; //The section's id is the group's id
      this.tool_group_owner_name = tool_data.panel_section_name; //The section's name is the group's name

      this.tool_version = tool_data.version;
    },

    /* From the data received from the endpoint, create a dict usable by the add_input() function */
    create_input_params(input, type_container=null, name_container=null) {
      //Retrieve the default inputs attributes
      let input_params = {
        _name: input.name,
        _label: input.label,
        _help: input.help,
        _type: input.type,
        _validation: input.validation,
        _type_container: type_container,
        _name_container: name_container,
      };  
  
      if(["data", "data_collection"].includes(input.type)) { //If input type is data, we also have a file format to get
        input_params._format = input.extensions[0];
      }else{
        input_params._value = input.value;
      }

      if(input.type === "select") { //If input type is select, we also have its options
        input_params._select_options = []
        input.options.forEach(function(option) {
          input_params._select_options.push({"name": option[0], "value": option[1]});
        })
      }

      if(!["hidden", "hidden_data"].includes(input.type)) { //A non-hidden input can be mandatory
        input_params._mandatory = !input.optional;
      }

      return input_params;
    },

    /* From the data received from the endpoint, create an object usable by the add_output() function */
    create_output_params(output, inputs) {
      const output_params = {
        _name: output.name,
      }

      //Check if it's a collection
      const is_collection = output.model_class==="ToolOutputCollection"
      if(is_collection) {
        const dataset = output.structure.discover_datasets[0];
        output_params._pattern = dataset.pattern?dataset.pattern:"__designation_and_ext__";
        output_params._path = dataset.directory;
        //ONLY IN LOCAL
        if(dataset.directory[0] === '/') {
          dataset.directory[0].split(1);
        }
        output_params._format = dataset.format;

      }else if(!this.is_expression_tool) { //If it's a regular output and not a collection/expression tool
        //Retrieve the output path (saved in a special input param) NOTE: Collection has also a special input param but there is no need to use it here)
        const corresponding_input_path_name = output.name+"__path"; 
        const corresponding_input_path = inputs.find((input) => input.name===corresponding_input_path_name);
        output_params._path = corresponding_input_path.value;
        output_params._format = output.format;
      }
      output_params._is_collection = is_collection;

      return output_params;
    },

    /* Add an input in the form from params */
    add_input(params) {
      let is_defined = params!=null; //There is no params if it's a new input (created by the user with the form)
      if(is_defined) {
        if(params._type_container != null && params._name_container != null) { //If the input is in a container (repeat or section)
          const key_container = params._type_container === "repeat"?"repeats":"sections";
          const value_exists = this.tool_inputs_containers[key_container].some( //Is the value already in the list ? 
            (option) => option.value == params._name_container
          );
          if(!value_exists) {
            this.tool_inputs_containers[key_container].push({"label": params._name_container, "value": params._name_container}); //TODO : capitalize + lowercase
          }
        }
      }

      this.tool_inputs.push({ 
        name:               is_defined ? params._name:              null, 
        label:              is_defined ? params._label:             null, 
        help:               is_defined ? params._help:              null,
        default_value:      is_defined ? params._value:             null, 
        select_options:     is_defined ? params._select_options:    [],
        type:               is_defined ? params._type:              "text", 
        format:             is_defined ? params._format:            null,
        mandatory:          is_defined ? params._mandatory:         false,
        validation:         is_defined ? params._validation:        false,
        validation_params:  is_defined && params._validation ? params._validation_params: {"regex": '', "min_length": 0, "min": 0, "max": null},
        type_container:     is_defined ? params._type_container:    null,
        name_container:     is_defined ? params._name_container:    null,
      });
    },

    /* Add an output in the form from params */
    add_output(params) {
      let is_defined = params!=null; //There is no params if it's a new output (created by the user with the form)

      this.tool_outputs.push({
        name:             is_defined ? params._name:            null,
        path:             is_defined ? params._path:            null,
        format:           is_defined ? params._format:          (!this.is_expression_tool?"txt":"text"),
        pattern:          is_defined ? params._pattern:         null,
        is_collection:    is_defined ? params._is_collection:   false, //Output IS a collection
        collection_name:  is_defined ? params._collection_name: null, //Output IS IN a collection
      });
    },

    /*                                                                       */
    /* Saving tool                                                           */
    /* Extract the data from the inputs or use the content of the XML editor */
    /* Send it to one of our custom endpoints                                */
    /*                                                                       */

    /* Create the payload from the form inputs */
    /* The result dict will be send to one of our custom endpoints */
    create_payload_from_form() {
      //Check if all inputs are valids
      const nb_errors = $(".tool_manager input:invalid").length; 
      let errors = [];
      ($(".tool_manager input:invalid+p")).each(function(_, test) {
        errors.push(test.innerText);
      });

      if(nb_errors > 0) {
        this.alert_msg = `Please, correct the issues before validating the form: ${errors.join(' ')}`;
        this.alert_status = "error";
        this.save_button_activation = true;
        return;
      }

      let payload = { /* Format the payload - See the dict inside data() to have more info about the content */
        name: this.tool_name,
        is_expression_tool: this.is_expression_tool,
        description: this.tool_description,
        version: this.tool_version,
        group_owner: {
          id: this.tool_group_owner_id,
          name: this.tool_group_owner_name,
        },
        guest_groups: this.guest_groups,
        inputs: this.tool_inputs,
        outputs: this.tool_outputs,

        method_script: this.selected_method_script,
        path_script: this.tool_path_exec,
        interpreter: this.tool_exec_interpreter,
        url_git_repo: this.tool_url_git_repo,
        git_commit_ID: this.tool_git_commit_ID,
        git_tag: this.tool_git_tag,
        command: this.tool_command,
        expression: this.tool_expression_script,
      };

      if(this.is_edit) {
          payload.tool_id = this.tool_id; //Keep only this one
      }
      return payload;
    },

    /* Create the payload from the custom XML textarea */
    create_payload_from_custom_XML() {
      let payload = {
        is_custom_XML: true,
        custom_XML: this.tool_custom_XML,
        tool_id: this.is_edit?this.tool_id:null,
      };
      return payload;
    },

    /* Fill the custom xml text area with the values from the form inputs*/
    async updt_tool_custom_xml(confirmBox=true) {
      if((!confirmBox || this.tool_custom_XML == null || this.tool_custom_XML.trim() == '') || (confirmBox && window.confirm("You will lose any changes you may have made in the below text area. Are you sure ?"))) {
        const payload = this.create_payload_from_form();

        if(payload != null) { //Null if there is atleast one validation error
          const { data, error} = await GalaxyApi().POST("/api/osug_tool_manager/generate_xml", {
            body: payload,
          });
          if(error) {
            this.alert_msg = error.err_msg;
            this.alert_status = "error";
            this.save_button_activation = true;
          }else {
            this.tool_custom_XML = data;
          }
        }
      }
    },

    /* Save (create or edit) a tool from the form's data OR the custom XML textarea */
    async save_tool(from_custom_XML=false) {
      //Deactivate the save button (outside the modal)
      this.save_button_activation = false;

      let payload = null;
      if(!from_custom_XML) {
        payload = this.create_payload_from_form();
      }else {
        this.tool_custom_XML_validation_errors = null; //Empty the previous messages in the modal if needed
        this.tool_custom_XML_validation_loading = true; //Display the loading animation + disable the save button
        payload = this.create_payload_from_custom_XML();
      }

      if(payload == null) { //Null if there is atleast one validation error
        return;
      }

      const { data, error } = this.is_edit?
        await GalaxyApi().PUT("/api/osug_tool_manager/{tool_id}", { body: payload, params: { path: { tool_id: this.tool_id },}}): //Edit (even it's in the payload, we still need to have a param...)
        await GalaxyApi().POST("/api/osug_tool_manager", { body: payload }); //Create
      //Data is tool ID
      if(error) {
        if(from_custom_XML) {
          this.tool_custom_XML_validation_errors = error.err_msg;
        }else {
          this.alert_msg = error.err_msg;
          this.alert_status = "error";
          this.save_button_activation = true;
        }
      }else{ //No error, redirect the user to the tool execution page
        this.tool_custom_XML_modal = false;
        const state = this.is_edit?"updated":"added"
        this.alert_msg = `Tool ${state} successfully.`;
        this.alert_redirection_url = `/?tool_id=${data}` //Display a link to redirect the user to tool execution page
        this.alert_status = "success";
        this.redirect_to_tool_exec(data);
      }

      if(from_custom_XML) {
        this.tool_custom_XML_validation_loading = false; //Stop the loading animation in the modal
      }
      
      this.save_button_activation = true; //Reactivate the save button (outside the modal)
    },

    /* Redirect to the tool execution page */
    redirect_to_tool_exec(id) {
      setTimeout(function() {
        window.location=`/?tool_id=${id}`;
        }, 
        2000
      )
    },

    /*                           */
    /* Manage the inputs/outputs */
    /*                           */

    /* Delete an input/output */
    delete_io(io_type, index) {
      const io_list = io_type === "input"?this.tool_inputs:this.tool_outputs;
      io_list.splice(index, 1);
    },

    /* Update the inputs/outputs order */
    update_io_order(io_type, direction, index) {
      const io_list = io_type === "input"?this.tool_inputs:this.tool_outputs;

      //limits
      if((direction === "up" && index === 0) || (direction === "down" && index+1 === io_list.length)) {
        return; 
      }
      
      const io_element = io_type=="input"?this.tool_inputs[index]:this.tool_outputs[index];
      let new_index = direction=="up"?index-1:index+1;

      //Update the order
      io_list.splice(index, 1)
      io_list.splice(new_index, 0, io_element);
    },

    /*         */
    /* Command */
    /*         */

    /* Insert input/output in the command textarea */
    insert_in_cmd(var_name, type=null) {
      let insertion_value = null;
      if(!this.is_expression_tool) { //Regular tool
        var txt_area_cmd = this.$refs.tool_command_txt;
        if(type == "data_collection") {
          insertion_value = `#for $input in --${var_name} \$${var_name}# $input #end for#`;
        }else{
          insertion_value = `\${${var_name}}`;
        }
      }else { //Expression tool
        var txt_area_cmd = this.$refs.tool_expression_script_txt;

        if(var_name === "allOutputs") {
          insertion_value = "return {";
          this.tool_outputs.forEach(function(output) {
            insertion_value += '\n\t"'+output.name+'": null,';
          });
          insertion_value += "\n}; //Replace null by your value"
        }else {
          insertion_value = `$job.${var_name}`;
        }
      }
    
      // Get cursor's position:
      let start_pos = txt_area_cmd.selectionStart,
      end_pos = txt_area_cmd.selectionEnd,
      cursor_pos = start_pos,
      tmp_str = txt_area_cmd.value;

      // Define new value
      let new_value = tmp_str.substring(0, start_pos) + insertion_value + tmp_str.substring(end_pos, tmp_str.length);

      // Insert the IO in the textarea
      if(!this.is_expression_tool) {
        this.tool_command = new_value;
      }else{
        this.tool_expression_script = new_value;
      }

      // Move cursor:
      setTimeout(() => {
        cursor_pos += insertion_value.length;
        txt_area_cmd.selectionStart = txt_area_cmd.selectionEnd = cursor_pos;
      }, 10);
    },

    /* Update the generated command */ 
    update_command() {
      if(this.tool_exec_interpreter != null && this.tool_path_exec!= null) {
        let command = `${this.tool_exec_interpreter} ${this.tool_path_exec}`;
        this.tool_inputs.forEach(function(input) {
          if(input.name != null) {
            if(input.type == "data_collection") {
              if(input.name.length == 1) { // convention : - for one letter arg, -- for more
                command += ` #for $input in -${input.name}=\$${input.name}# $input #end for#`;
              }else{
                command += ` #for $input in --${input.name} \$${input.name}# $input #end for#`;
              }
            }else{
              if(input.name.length == 1) { // convention : - for one letter arg, -- for more
                command += ` -${input.name}="\${${input.name}}"`;
              }else {
                command += ` --${input.name} "\${${input.name}}"`;
              }
            }
            
          }
        });
        this.tool_command = command;
      }
    },

    /* Check the cmd value to validate the templating names variables */
    check_cmd_templating() {
      this.tool_command_templating_errors = [];
      const regex_template = /\${(\w+)}/g; //Get what's inside ${}
      const inputs_outputs = new Set((this.tool_inputs.concat(this.tool_outputs)).map(item => item.name)); //Create a set (better than a simple list)
      const matches = [...this.tool_command.matchAll(regex_template)]; //Get all matches

      if(matches.length > 0) { 
        matches.forEach((match) => {
          const var_name = match[1]; 
          if(!inputs_outputs.has(var_name)) { //Is an existing variable name ?
            this.tool_command_templating_errors.push(`${var_name} doesn't exist.`);
          }
        });
      }
    },

    /*               */
    /* Miscellaneous */
    /*               */

    /* When the user un/checked the is expression tool checkbox */
    change_type_tool(event) {
      if(event.target.value) {
        this.tool_outputs = []; //Reset outputs
      }
    },

  },
  watch: { //Trigger the functions whenever the element associated (with v-model=function_name()) is updated
    /* Set the name of the selected group */
    tool_group_owner_id(new_group_id) {
      const selected_group = this.user_groups.find(group => group.id === new_group_id);
      this.tool_group_owner_name = selected_group ? selected_group.name : '';
    }
  },
  async mounted() { //When the page is loaded
    //Retrieve here the user/tool data...
    this.is_user_admin = await this.is_user_admin();

    this.user_groups = await this.get_user_groups(); //Retrieve the user groups
    if(this.user_is_admin) {
      this.all_available_groups = await this.get_all_groups(); //Retrieve all groups if user is admin
    }else{
      this.all_available_groups = this.user_groups; //Else, only the current user ones
    }

    if(!this.is_edit) { //Tool creation (duplicate or "empty" new)
      this.tool_group_owner_id = this.user_groups[0]?.id; //If it's a new tool, the first group is selected by default.

      if(this.is_duplicate) {
        const tool_id = this.duplicate_from;
        this.tool_data = await this.get_tool_data(tool_id); //Get the data from the tool
        await this.updt_form_frm_tool_data(this.tool_data); //Set the form inputs values

        //Reset some inputs
        this.tool_version = "1.0";
        this.tool_id = null;
        this.tool_name = "copy_from_"+this.tool_name;
      }
    }else {
      const tool_id = this.id
      this.tool_data = await this.get_tool_data(tool_id);
      await this.updt_form_frm_tool_data(this.tool_data); 

      this.previous_version = this.tool_version;

      /* Calculate the new possible versions */

      const parts = this.tool_version.split('.'); // We split the numver in two (int and decimal parts)
  
      let major = parseInt(parts[0], 10); //Major version (int part)
      let minor = parseInt(parts[1], 10); //Minor version (decimal part)
      
  
      this.new_minor_version = `${major}.${minor+1}`; //We increment the decimal part
      this.new_major_version = `${major+1}.0`; //We increment the int part and reset the decimal part
      this.tool_version = this.new_minor_version; //To select the minor option
    }

    // Does the user has the right to edit this tool ?
    const user_groups_id = this.user_groups.map(({id}) => id);
    this.user_can_edit = user_groups_id.includes(this.tool_group_owner_id)

    this.page_loading = false; //Stop the loading spinner 
  }
};
</script>

<style>
  /* Navigation tabs and action buttons */
  div.tab_btn { 
    display: flex;
  }

  ul.tab_btn-left { 
    width: 60%;
  }

  ul.tab_btn-right {
    width: 40%;
    justify-content: right;
  }

  /* Deletion buttons */
  .delete_output, .delete_input {
    color: red;
    cursor: pointer;
    font-size: 1.4em;
  }

  /* Fake links (trigger a function) */
  .var_link {
    color: #0a5cdd;
    cursor: pointer;
  }

  .var_link:hover {
    text-decoration: underline;
  }

  /* Validation style */
  .tool_manager input:invalid {
    color: red;
  }

  .header_row { /* For inputs and outputs */
    display: flex;
  }

  .mandatory_cbx, .is_collection_cbx {
      display: flex;
      align-items: center;
      align-content: end;
      margin-left: 10px;
  }

  .required_input_star {
    margin-left: 2px;
    color: red;
  }

  /* Command */

  #cmd_generate_btn, #regenerate_xml_from_inputs_btn {
    font-size: 0.7em;
    color: #0a5cdd;
    cursor: pointer;
  }

  #tool_command_templating_errors {
    font-style: italic;
    color: #ff6000;
  }

  /* XML editing modal */

  .modal-dialog {
    width: 100%;
  }

  .modal-content {
    height: 90vh;
  }
  #monaco-editor {
    height: 80% !important;
  }


  #XMLEditingModal #XMLEditingValidationErrors {
    white-space: pre;
    color: red;
    font-weight: bold;
  }
</style>

<template>
  <div class="tool_manager container mt-4">
    <h1 class="mb-4">Tool Manager</h1>

    <!-- Tabs -->
    <div v-if="!page_loading && user_can_edit && user_groups.length>0" class="tab_btn">
      <ul class="nav nav-tabs tab_btn-left">
        <li class="nav-item">
          <button class="nav-link" :class="{ active: active_tab === 'general' }" @click="active_tab = 'general'">
            General
          </button>
        </li>
        <li class="nav-item">
          <button class="nav-link" :class="{ active: active_tab === 'inputs' }" @click="active_tab = 'inputs'">
            Inputs
          </button>
        </li>
        <li class="nav-item">
          <button class="nav-link" :class="{ active: active_tab === 'outputs' }" @click="active_tab = 'outputs'">
            Outputs
          </button>
        </li>
        <li class="nav-item">
          <button class="nav-link" :class="{ active: active_tab === 'script' }" @click="active_tab = 'script'">
            Script
          </button>
        </li>
      </ul>
      <ul class="nav nav-tabs tab_btn-right">
        <li class="ms-auto">
          <button class="nav-link" @click="tool_custom_XML_modal=true">
            Edit XML
          </button>
        </li>
        <li class="ms-auto">
          <button id="save_btn" class="btn btn-primary" @click="save_tool(from_custom_XML=false);" :disabled="!save_button_activation">Save Tool</button>
        </li>
      </ul>
    </div>
    <div v-else-if="page_loading">
      <b-spinner small></b-spinner>&nbsp;Loading...
    </div>
    <div v-else-if="user_groups.length==0">
      <b><span style="color: red;">/!\</span>You must be in a group to be able to create a tool.</b>
    </div>
    <div v-else-if="!user_can_edit">
      <b><span style="color: red;">/!\</span>You don't have the right to edit this tool.</b>
    </div>

    <!-- Tabs content -->
    <div v-if="!page_loading && user_can_edit && user_groups.length>0" class="tab-content mt-2">
      <!-- General TAB -->
      <div id="general" class="tab-pane" :class="{ 'show active': active_tab === 'general' }">
        <div class="mb-3">
          <label class="form-label" for="tool_name">Tool Name<span class="required_input_star">*</span></label>
          <input v-model="tool_name" class="form-control" type="text" id="tool_name" minlength="4" />
          <p class="pattern_msg">The tool's name must be at least 4 characters in length.</p>
        </div>
        <div class="mb-4">
          <label class="form-label" for="tool_description">Tool Description<span class="required_input_star">*</span></label>
          <textarea v-model="tool_description" class="form-control" id="tool_description"></textarea>
        </div>
        <div class="mb-4 d-flex">
          <label class="form-label" for="is_expression_tool">Is an expression tool:</label>
          <input v-model="is_expression_tool" type="checkbox" id="is_expression_tool" @change="change_type_tool">
        </div>

        <div class="row">
          <div v-if="all_available_groups.some((group) => group.id == tool_group_owner_id)" class="mb-3 col-4">
            <label class="form-label" for="user_groups">Group owner<span class="required_input_star">*</span></label>
            <select id="user_groups" class="custom-select" v-model="tool_group_owner_id">
              <option v-for="group in user_groups" :value="group.id">{{ group.name }}</option>
            </select>
            <label class="form-label" for="guest_groups">Share with groups</label>
            <v-select
              id="guest_groups"
              :options="all_available_groups"
              :selectable="(option) => option.id!=tool_group_owner_id"
              v-model="guest_groups"
              label="name"
              multiple
            />
          </div>
          <div v-if="this.is_edit" class="mb-4 col-4">
            <label class="form-label" for="tool_new_version">Tool new version<span class="required_input_star">*</span></label>
            <select class="custom-select" v-model="tool_version">
              <option :value="new_minor_version">
                {{ previous_version }} → {{ new_minor_version }} (minor update)
              </option>
              <option :value="new_major_version">
                {{ previous_version }} → {{ new_major_version }} (major update)
              </option>
            </select>
          </div>
        </div>

      </div>

      <!-- Inputs TAB -->
      <div id="inputs" class="tab-pane" :class="{ 'show active': active_tab === 'inputs' }">
        <div v-for="(_, index) in tool_inputs" :key="index" class="mb-3">
          <Input :index="index" :nb_inputs="tool_inputs.length" v-model="tool_inputs[index]" @delete_input="delete_io" @update_inputs_order="update_io_order" :tool_inputs_containers="tool_inputs_containers" />
        </div>
        <button class="btn btn-dark" @click="add_input(null)">Add an Input</button>
      </div>

      <!-- Outputs TAB -->
      <div id="outputs" class="tab-pane" :class="{ 'show active': active_tab === 'outputs' }">
        <div v-for="(_, index) in tool_outputs" :key="index" class="mb-3">
          <Output :index="index" :nb_inputs="tool_outputs.length" v-model="tool_outputs[index]" @delete_output="delete_io" @update_outputs_order="update_io_order" :is_expression_tool="is_expression_tool" />
        </div>
        <button class="btn btn-dark" @click="add_output(null)">Add an Output</button>
      </div>

      <!-- Script TAB -->
      <div id="script" class="tab-pane" :class="{ 'show active': active_tab === 'script' }">

        <!-- Regular tool -->
        <div v-if="!is_expression_tool" class="regular_tool_script">
          <label>Script to execute<span class="required_input_star">*</span></label>
          <div class="form-check form-check-inline">
            <input class="form-check-input" name="methodScript" type="radio" id="scriptPath" value="scriptPath" v-model="selected_method_script" :checked="true">
            <label class="form-check-label" for="scriptPath">Script path</label>
          </div>
          <div class="form-check form-check-inline">
            <input class="form-check-input" name="methodScript" type="radio" id="typeCmd" v-model="selected_method_script" value="typeCmd">
            <label class="form-check-label" for="typeCmd">Type command (bash)</label>
          </div>
          <!-- External script -->
          <div v-if="selected_method_script === 'scriptPath'">
            <div class="mb-3">
              <label class="form-label" for="tool_path_exec">Script path<span class="required_input_star">*</span></label>
              <input v-model="tool_path_exec" class="form-control" type="text" id="tool_path_exec" pattern="^\/[\w\/\-]+\w\.\w+" />
              <p class="pattern_msg">The path must be absolute (starts with a /), valid and point to a file.</p>
            </div>
            <div class="mb-3">
              <label class="form-label" for="tool_exec_interpreter">Interpreter<span class="required_input_star">*</span></label>
              <input v-model="tool_exec_interpreter" class="form-control" type="text" id="tool_exec_interpreter" />
            </div>
            <div class="d-flex justify-content-between">
              <div class="mb-3">
                <label class="form-label" for="url_git_repo">URL git repository</label>
                <input v-model="tool_url_git_repo" class="form-control" type="text" id="url_git_repo" />
              </div>
              <div class="mb-3">
                <label class="form-label" for="git_commit_id">Commit ID</label>
                <input v-model="tool_git_commit_ID" class="form-control" type="text" id="git_commit_id" />
              </div>
              <div class="mb-3">
                <label class="form-label" for="git_tag">Tag</label>
                <input v-model="tool_git_tag" class="form-control" type="text" id="git_tag" />
              </div>
            </div>
          </div>
          <!-- Command TAB -->
          <div>
            <label class="form-label" for="tool_command">Command<span class="required_input_star">* </span><span v-if="selected_method_script==='scriptPath'" id="cmd_generate_btn" @click="update_command">Auto generate</span></label>
            <textarea @input="check_cmd_templating" ref="tool_command_txt" v-model="tool_command" class="form-control" id="tool_command" rows="5"></textarea>
            <span id="tool_command_templating_errors" v-if="tool_command_templating_errors.length>0">{{ tool_command_templating_errors.join("\n") }}</span>
          </div>
        </div>

      <!-- Expression tool -->

        <div v-else class="expression_tool_script">
          <div class="mb-3">
            <label class="form-label" for="expression_script">Expression script<span class="required_input_star">*</span></label>
            <textarea ref="tool_expression_script_txt" v-model="tool_expression_script" class="form-control" id="expression_script" rows="10"></textarea>
          </div>
        </div>

        <div v-if="(this.tool_inputs.length > 0 || this.tool_outputs.length > 0) && selected_method_script === 'typeCmd' || is_expression_tool" class="mt-3">
          <p><i>Click on a variable to add it to the command:</i></p>
          <div class="add_IO_in_cmd">
            <p v-if="tool_inputs.length>0" class="inputs_links"><b>Inputs:</b>
              <span class="var_link mr-2" v-for="input in tool_inputs" :key="input.name" @click="insert_in_cmd(input.name, input.type);">{{ input.name }}</span>
            </p>
            <p v-if="tool_outputs.length>0" class="outputs_links"><b>Outputs:</b>
              <span v-if="!is_expression_tool" class="var_link mr-2" v-for="output in tool_outputs" :key="output.name" @click="insert_in_cmd(output.name);">{{ output.name }}</span>
              <span v-if="is_expression_tool" class="var_link" @click="insert_in_cmd('allOutputs');">return everything</span>
            </p>
            <p class="user_links"><b>User:</b>
              <span class="var_link mr-2" @click="insert_in_cmd('__user__.name');">Name</span>
              <span class="var_link mr-2" @click="insert_in_cmd('__user__.email');">Email</span>
            </p>
          </div>
        </div>
        
      </div>

    </div>

    <!-- XML editing modal -->
    <b-modal v-model="tool_custom_XML_modal" title="XML editing" hide-footer id="XMLEditingModal">
      <div class="mb-3">
        <p>
          <b style="color:red;">/!\</b> Please carefully read the 
          <a href="#" target="_blank">documentation</a> before using this functionality.
        </p>
      </div>

      <span id="regenerate_xml_from_inputs_btn" @click="updt_tool_custom_xml" style="float:right;">Regenerate from the form inputs</span>
      <VueMonacoEditor
            id="monaco-editor"
            v-model="tool_custom_XML"
            ref="monaco"
            language="xml"
            :options="{
                quickSuggestions: {
                    other: true,
                    comments: false,
                    strings: true,
                },
                minimap: { enabled: false },
                lineHeight: 19, 
                scrollBeyondLastLine: false,
                automaticLayout: true,
            }">
        </VueMonacoEditor>

      <div id="XMLEditingModalFooter" class="d-flex justify-content-between mt-3">
        <div>
          <p v-if="tool_custom_XML_validation_errors" id="XMLEditingValidationErrors" class="mb-0">{{ tool_custom_XML_validation_errors }}</p>
        </div>

        <div>
          <b-button variant="secondary" @click="tool_custom_XML_modal = false" :disabled="tool_custom_XML_validation_loading">Abort</b-button>
          <b-button variant="primary" @click="save_tool(from_custom_XML=true);" :disabled="tool_custom_XML_validation_loading">
            <span v-if="tool_custom_XML_validation_loading">
              <b-spinner small></b-spinner>&nbsp;Loading...
            </span>
            <span v-else>Save</span>
          </b-button>
        </div>
      </div>
    </b-modal>
    
    <!-- Alert -->
    <b-alert v-if="alert_msg" :variant="alert_status === 'success' ? 'success' : (alert_status === 'error' ? 'danger' : '')" dismissible show class="mt-5" @dismissed="alert_msg=null">
      {{ alert_msg }}
      <span v-if="alert_status === 'success'">
        <RouterLink :to=alert_redirection_url>Redirect in two seconds.</RouterLink>
      </span>
    </b-alert>
  </div>
</template>
