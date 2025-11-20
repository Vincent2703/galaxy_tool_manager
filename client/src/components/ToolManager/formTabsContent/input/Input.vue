<template>
    <!-- Default form inputs -->
    <div class="input_fields" :id="`input_${index}`">
        <div class="header_row row" style="display: flex; align-items: center;">
            <div class="col-8" style="display: flex;">
                <b>
                    <span v-if="index>0" class="arrow_order" @click="update_inputs_order('up');">↑</span>&nbsp;
                    <span v-if="index+1<nb_inputs" class="arrow_order" @click="update_inputs_order('down')">↓</span>&nbsp;
                    Input n°{{index+1}} <span @click="delete_input" class="delete_input">&times;</span>
                </b>
                <span class="mandatory_cbx" v-if="!['hidden', 'hidden_data', 'select'].includes(value.type)">
                    <input v-model="value.mandatory" type="checkbox"  :id="`mandatory_input_${index}`"> <!--TODO: should be is_mandatory-->
                    <label :for="`mandatory_input_${index}`">Mandatory input</label>
                </span>
            </div>
            <div class="col-4" style="display: flex;">
                <span class="w-50" id="includeTypeSelect">
                    Include in&nbsp;
                    <v-select
                        :id="`input_type_container_${index}`"
                        :options='[{"label": "None", "value": null}, {"label": "Repeat", "value": "repeat"}, {"label": "Section", "value": "section"}]' 
                        v-model="value.type_container"
                        :reduce="option => option.value"
                        :clearable="false"
                    />
                </span>
                <span class="w-50" id="containerSelect" v-if="value.type_container != null">
                    container name&nbsp;
                    <v-select 
                        :id="`input_name_container_${index}`"
                        taggable
                        :options="tool_inputs_containers[value.type_container+'s']" 
                        v-model="value.name_container"
                        :reduce="option => option.label"
                        :clearable="false"
                        :create-option="newTag => ({ value: newTag.toLowerCase(), label: newTag.charAt(0).toUpperCase()+newTag.slice(1) })"                
                        @option:created="add_container"
                    />
                </span>
            </div>
        </div>

        <div class="form_input mb-3 w-50">
            <label :for="`input_name_${index}`">Input name<span class="required_input_star">*</span></label>
            <input 
                v-model="value.name" 
                type="text" 
                title="It's the input's name you can use in your script or command input" 
                class="form-control" 
                :id="`input_name_${index}`" 
                minlength="1" 
                pattern="\w+"
            />
            <p class="pattern_msg">The name must be at least 1 character long and not contain any special characters.</p>
        </div>

        <div class="mb-4 row">
            <div class="form_input col">
                <label :for="`input_label_${index}`">Input label</label>
                <input 
                    v-model="value.label"
                    type="text" 
                    title="This name will be displayed to the tool's user" 
                    class="form-control" 
                    :id="`input_label_${index}`"
                />
            </div>

            <div class="form_input col">
                <label :for="`input_help_${index}`">Input help</label>
                <input 
                    v-model="value.help" 
                    type="text" 
                    title="This text will be displayed under the input on the tool's page"
                    class="form-control" 
                    :id="`input_help_${index}`"
                />
            </div>
        </div>

        <div class="row mb-3">
            <div class="col">
                <label class="form-label" :for="`input_type_${index}`">Input type<span class="required_input_star">*</span></label>
                <select :id="`input_type_${index}`" class="custom-select" v-model="value.type" @change="reset_default_value()">
                    <option value="text">Text</option>
                    <option value="integer">Integer</option>
                    <option value="float">Float</option>
                    <option value="boolean">Boolean</option>
                    <option value="select">Select</option>
                    <option value="hidden">Hidden</option>
                    <!--<option value="hidden_data">Hidden data</option>-->
                    <option value="data">Data (file)</option>
                    <option value="data_collection">Data collection (files)</option>
                    <!--<option value="file">File</option>
                    <option value="directory_uri">Directory URI</option>-->
                </select>
                <button v-if="value.type === 'select'" class="btn btn-secondary" @click="add_option">Add an option</button>
            </div>

            <!-- Depending on the user defined input's type, not the same form inputs -->

            <div v-if="['data', 'data_collection'].includes(value.type)" class="form_input col">
                <label :for="`input_format_${index}`">File extension(s)</label>
                <input v-model="value.format" type="text" class="form-control" :id="`input_format_${index}`" pattern="^[a-z]+(,[a-z]+)*$">
                <p class="pattern_msg">Must contains one extension or a comma-separated list of extensions.</p>
            </div>

            <!-- When the input can have a default value -->
            <div v-if="['text', 'integer', 'float', 'boolean', 'hidden', 'directory_uri'].includes(value.type)" class="form_input col">
                
                <label :for="`input_default_value_${index}`">Input default value</label>
                <input 
                    v-if="['text', 'hidden', 'integer', 'float', 'directory_uri'].includes(value.type)" 
                    title="This value will be used if the tool's user doesn't change it before the tool's execution"
                    v-model="value.default_value" :type="['text', 'hidden', 'directory_uri'].includes(value.type) ? 'text' : 'number'" 
                    class="form-control" :id="`input_default_value_${index}`"
                />
                
                <input v-if="value.type === 'boolean'" v-model="value.default_value" type="checkbox" class="form-check-input"> 
            </div>

            <div v-if="value.type === 'select'" class="select_options col">
                <Input_select 
                v-for="(_, index) in value.select_options" 
                :index="index" 
                v-model="value.select_options[index]" 
                @delete_option="delete_option"/>
            </div>
        </div>

        <!-- Validators -->
        <div v-if="['integer', 'float', 'text'].includes(value.type)" class="input_validation_params text-center mt-4 mb-5">
            <button class="btn btn-link" type="button" @click="update_validation">
                <span>{{ value.validation?"Remove validation":"Add validation" }}</span>
            </button>
            <div v-if="value.validation" class="validators">
                <div v-if="value.type === 'text'" class="text_validation row">
                    <div class="form_input col-6 pr-5 pl-5">
                        <label :for="`input_validator_regex_${index}`">Pattern</label>
                        <input        
                            v-model="value.validation_params.regex" 
                            type="text" 
                            title="Use a regex to validate the input's value before allowing the tool's execution"
                            class="form-control" 
                            :id="`input_validator_regex_${index}`"
                        />
                    </div>

                    <div class="form_input col-6 pr-5 pl-5">
                        <label :for="`input_validator_min_length_${index}`">Minimum length</label>
                        <input  
                            v-model="value.validation_params.min" 
                            type="number" 
                            min="0" 
                            class="form-control" 
                            :id="`input_validator_min_length_${index}`"
                        />
                    </div>
                </div>

                <div v-if="['integer', 'float'].includes(value.type)" class="in_range row">
                    <div class="form_input col-6 pr-5 pl-5">
                        <label :for="`input_validator_min_${index}`">Minimum</label>
                        <input  
                        v-model="value.validation_params.min" type="text" 
                        class="form-control" :id="`input_validator_min_${index}`">
                    </div>
                    <div class="form_input col-6 pr-5 pl-5">
                        <label :for="`input_validator_max_${index}`">Maximum</label>
                        <input  
                        v-model="value.validation_params.max" type="text" 
                        class="form-control" :id="`input_validator_max_${index}`">
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style>
    .arrow_order {
        font-size: 1.6em;
    }

    .arrow_order:hover {
        cursor: pointer;
        color: red;
    }
</style>

<script>
    import vSelect from "vue-select";
    import "vue-select/dist/vue-select.css";

    import Input_select from "./Input_select.vue";

    export default {
        components: { Input_select, vSelect },

        data() {
            return {} //Local variables (0 here)
        },
        props: {
            value: Object,
            index: Number,
            nb_inputs: Number,
            tool_inputs_containers: Object,
        },
        methods: {
            /* Emit a custom event, handle by the parent component to change the order of the inputs */
            update_inputs_order(direction) {
                this.$emit("update_inputs_order", "input", direction, this.index);
            },

            /* Allow the user to add a new repeat or section container for its inputs */
            add_container(new_container) {
                const key_container = this.value.type_container === "repeat"?"repeats":"sections"
                const new_container_id = new_container.value;
                const new_container_name = new_container.label;
                const value_exists = this.tool_inputs_containers[key_container].some(
                    (option) => option.value == new_container_id
                );
                if(!value_exists) {
                    this.tool_inputs_containers[key_container].push({
                        value: new_container_id,
                        label: new_container_name
                    });
                }
            },

            /* When the user update the input type, reset the default value */
            reset_default_value() {
                this.value.default_value = null;
            },
            
            /* When the user clicks on the validation button, change the validation boolean*/
            update_validation() {
                this.value.validation = !this.value.validation;
            },

            /* Emit a custom event, handle by the parent component to delete this component from its list */
            delete_input() { 
                this.$emit("delete_input", "input", this.index); //Use delete_io() from the parent
            },

            /* Add an option for the select input's type */
            add_option() {
                this.value.select_options.push({ 
                    name: null, 
                    value: null,
                });
            },
            /* Delete it */
            delete_option(index) {
                this.value.select_options.splice(index, 1);
            },
        }
    }

</script>