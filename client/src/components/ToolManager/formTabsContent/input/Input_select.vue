<template>
    <div class="form_input_select">
        <span class="delete_option" @click="delete_option">&times;</span>
        <label :for="`input_select_name_${index}`">Name</label>
        <input v-model="value.name" type="text" class="form-control" :id="`input_name_${index}`">
        <label :for="`input_select_value_${index}`">Value</label>
        <input v-model="value.value" type="text" class="form-control" :id="`input_value_${index}`">
    </div>
</template>

<style>
    .form_input_select {
        padding: 10px 30px 20px 20px;
    }

    .delete_option {
        position: absolute;
        right: 20px;
        color: red;
        cursor: pointer;
        font-size: 1.4em;
    }
</style>

<script>
    export default {
        props: {
            value: Object,
            index: Number
        },
        methods: {
            delete_option() {
                this.$emit("delete_option", this.index);
            }
        }
    }
</script>