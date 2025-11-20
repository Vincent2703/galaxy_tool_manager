<template>
    <div class="output_fields" :id="`output_${index}`">
        <span class="header_row">
            <b>
                <span v-if="index>0" class="arrow_order" @click="update_outputs_order('up');">↑</span>&nbsp;
                <span v-if="index+1<nb_inputs" class="arrow_order" @click="update_outputs_order('down')">↓</span>&nbsp;
                Output n°{{index+1}} <span @click="delete_output" class="delete_output">&times;</span>
            </b>
            <span v-if="!is_expression_tool" class="is_collection_cbx">
                <input v-model="value.is_collection" @change="set_values_is_collection" type="checkbox" :id="`output_is_collection_${index}`">
                <label :for="`output_is_collection_${index}`">Is a collection</label>
            </span>
        </span>
        <div class="form_input mt-2 mb-3 w-50">
            <label :for="`output_name_${index}`">Output name<span class="required_input_star">*</span></label>
            <input 
                v-model="value.name" 
                type="text" 
                title="It's the output's name you can use in your script or command input" 
                class="form-control" 
                :id="`output_name_${index}`" 
                min_length="3" 
                pattern="\w+"
            />
            <p class="pattern_msg">The name must be at least 3 characters long and not contain any special characters.</p>
        </div>

        <div v-if="!value.is_collection && !is_expression_tool" class="form_input mb-3">
            <label :for="`output_path_${index}`">Output path<span class="required_input_star">*</span></label>
            <input 
                v-model="value.path" 
                type="text" 
                title="It's the path to the output file that will be created with the tool's execution" 
                class="form-control" 
                :id="`output_name_${index}`" 
                pattern="^[\w\$\{\}\/\.\-]+" 
                @input="get_extension_from_path"
            />
            <p class="pattern_msg">Path to a file. Templating is authorized (${varName}).</p>
        </div>
        <div v-else-if="value.is_collection && !is_expression_tool" class="form_input mb-3">
            <label :for="`output_path_${index}`">Output path<span class="required_input_star">*</span></label>
            <input 
                v-model="value.path" 
                type="text" 
                title="It's the path to the directory used to form a collection" 
                class="form-control" 
                :id="`output_name_${index}`" 
                pattern="^\/[\w\-\/]*\w*\/*$"
            />
            <p class="pattern_msg">Path to a directory. Templating is authorized (${varName}).</p>
        </div>

        <div v-if="!is_expression_tool" class="form_input mb-3">
            <label :for="`output_format_${index}`">Output extension</label>
            <input 
                v-model="value.format" 
                title="The extension of the file (eg: txt)"
                type="text" 
                class="form-control" 
                :id="`output_format_${index}`"
            />
        </div>
        <div v-else class="form_input mb-3">
            <label :for="`output_format_${index}`">Output format</label>
            <select :id="`input_format_${index}`" class="custom-select" v-model="value.format">
                <option value="text">Text</option>
                <option value="integer">Integer</option>
                <option value="float">Float</option>
                <option value="boolean">Boolean</option>
            </select>
        </div>

        <div v-if="value.is_collection" class="form_input mb-3 pattern">
            <label :for="`output_pattern_${index}`">Output pattern</label>
            <input 
                v-model="value.pattern" 
                type="text" 
                title="You can use a pattern to filter the files before making a collection"
                class="form-control pattern" 
                :id="`output_pattern_${index}`"
            />
            <p>See examples <a target="_blank" href="https://planemo.readthedocs.io/en/latest/writing_advanced.html#examples">here</a>.</p>
        </div>
    </div>
</template>

<style>
    .form_input.pattern p {
        color: grey;
    }
</style>

<script>
    import vSelect from "vue-select";
    import "vue-select/dist/vue-select.css";

    export default {
        components: { vSelect },

        props: {
            value: Object,
            index: Number,
            nb_inputs: Number,
            is_expression_tool: Boolean,
            tool_outputs_collections: Array,
        },
        methods: {
            /* Emit a custom event, handle by the parent component to change the order of the outputs */
            update_outputs_order(direction) {
                this.$emit("update_outputs_order", "output", direction, this.index);
            },

            // We don't want to handle the collection of output yet (but output collection yes)
            /*add_collection(new_collection) {
                const new_collection_id = new_collection.value;
                const new_collection_name = new_collection.label;
                const value_exists = this.tool_outputs_collections.some(
                    (option) => option.value == new_collection_id
                );
                if(!value_exists) {
                    this.tool_outputs_collections.push({
                        value: new_collection_id,
                        label: new_collection_name
                    });
                }
            },*/

            /* Emit a custom event, handle by the parent component to delete this component from its list */
            delete_output() {
                this.$emit("delete_output", "output", this.index);
            },

            /* Extract the file extension from the path */
            get_extension_from_path(event) {
                const path = event.target.value;
                const regex = /\.(\w+)$/g
                const results = regex.exec(path);
                if(results && results[1]) {
                    this.value.format = results[1];
                }else{
                    this.value.format = null;
                }
            },

            /* Function executed if the output becomes a collection : change the default pattern (accept every filenames with an extension)*/
            set_values_is_collection() {
                this.value.collection_name = null;
                if(!this.value.pattern) {
                    this.value.pattern = "__designation_and_ext__";
                }
            }
        }
    }
</script>