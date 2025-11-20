<script>
import { GalaxyApi } from "@/api";

export default {
  data() { //Global variables
    return {
      user_groups_tools: [],
      user_groups: [],

      search_value: '',
      selected_group: "All",

      sort_key: '', //Current sort key
      sort_order: 1, //1: asc, -1: desc

      per_page: 10,
      current_page: 1,
      nb_pages: 1,
    };
  },
  methods: {
    /* Get the tools owned by the user groups */
    async get_tools() {
      const { data, error } = await GalaxyApi().GET("/api/osug_tool_manager"); //Custom endpoint (like /api/tools but only get the tools shared with one of the current user groups)
      if(error) {
        this.alert_msg = `An error occurred: ${error.message}`;
        this.alert_status = "error";
        return [];
      }else {
        return data;
      }
    },

    /* Delete the tool with the custom endpoint and hide the row in the table */
    async delete_tool(tool_id, tool_name) {
      if(window.confirm(`Do you really want to delete the tool '${tool_name}'?`)) {
        const url = `/api/osug_tool_manager/${tool_id}`;
        
        const { error } = await GalaxyApi().DELETE(url);
        if(error) {
          this.alert_msg = `An error occurred: ${error.message}`;
          this.alert_status = "error";
        }else {
          this.alert_msg = "Tool deleted successfully";
          this.alert_status = "success";
         
          $(`#${tool_id}`).hide("slow"); //Remove the tool row from the table
        }
      }
    },

    /* Sort the rows by a column (asc/desc) */
    sort_by(key) {
      if(this.sort_key === key) {
        this.sort_order *= -1; //Inverse

      }else{
        this.sort_key = key;
        this.sort_order = 1;
      }

      this.user_groups_tools.sort((a, b) => { //Alphabetical order (all in lower case)
        let sorting = (a[key].toLowerCase() > b[key].toLowerCase()) ? 1 : ((b[key].toLowerCase() > a[key].toLowerCase()) ? -1 : 0);
        return sorting*this.sort_order;
      });
    }, 

  },
  mounted() { // Page loaded
    this.get_tools().then(tools => { //From the user tools, retrieve their groups
      if(tools) {
        this.user_groups_tools = tools;

        let groups = []
        this.user_groups_tools.forEach(function(tool) {
          if(!groups.includes(tool.panel_section_name)) {
            groups.push(tool.panel_section_name);
          }
        });  
        this.user_groups = groups;
      }
    });

  },
  computed: {
    /* Filter the tools by name and/or their group */
    filter_tools_by_params() {
      const tools = this.user_groups_tools;
      const search_value = this.search_value;
      const selected_group = this.selected_group;

      tools.forEach(function(tool) {
        tool.hidden = !tool.name.toLowerCase().includes(search_value); //Filter by tool name
      });

      if(selected_group !== "All") {
        tools.forEach(tool => {
          tool.hidden = tool.hidden || tool.panel_section_name !== selected_group; //The tool is already hidden or the tool is owned by a different group.
        });
      }

      this.current_page = 1; //Reset the current page
      
      return tools;
    },

    /* Get the tools to display */
    paginated_tools() {
      const start = (this.current_page - 1) * this.per_page;
      const end = start + this.per_page;
      const visible_tools = this.user_groups_tools.filter(function(tool) {
        return !tool.hidden;
      })

      this.nb_pages = Math.ceil(visible_tools.length/this.per_page);

      return visible_tools.slice(start, end);
    }
    
  },
  filters: {
    /* Troncate the description if too long */
    truncate: function(text, length, suffix) {
      if(text.length > length) {
        return text.substring(0, length) + suffix;
      }else {
        return text;
      }
    }
  }
};
</script>

<style>
  .table th, .table td {
    text-align: center;
    vertical-align: middle;
  }

  .table .colToolsList.name {
    width: 20%;
  }

  .table .colToolsList.description {
    width: 30%;
  }

  .table .colToolsList.ownership {
    width: 25%;
  }

  .table .colToolsList.version {
    width: 10%;
  }

  .table .colToolsList.edit, .table .colToolsList.duplicate, .table .colToolsList.delete {
    width: 5%;
  }

  .header_list {
    display: flex;
    justify-content: space-between;
  }

  .header_list a {
    height: 100%;
  }

  .sort_col {
    cursor: pointer;
  }

  .sort_col:hover {
    text-decoration: underline;
  }

  .sort_active {
    text-decoration: underline;
  }

  .arrow_sort {
    font-size: 1.3em;
  }

  .btn.new_tool {
    white-space: nowrap;
  }

</style>

<template>
  <div class="container mt-4">
    <span class="header_list">
      <h2 class="mb-4">Custom Tools List</h2>
    </span>
    <!-- Search input and add button -->
    <div class="row justify-content-between mb-3">
      <div class="filter_params row">
        <div class="form_input col-6">
          <label for="search_by_name">Search by name:</label>
          <input type="text" v-model="search_value" class="form-control">
        </div>
        <div class="form_input col-4">
          <label for="search_by_group">Search by group:</label>
          <select class="custom-select" v-model="selected_group">
            <option selected>All</option>
            <option v-for="group in this.user_groups">{{ group }}</option>
          </select>
        </div>
      </div>
      <div class="col-1 align-self-end">
        <RouterLink to="osug_tool_manager/create">
          <button class="btn btn-primary new_tool">New tool</button>
        </RouterLink>
      </div>
    </div>
    <!-- Tools list -->
    <div class="table-responsive">
      <table class="table table-striped table-bordered">
        <thead class="table-dark">
          <tr>
            <th class="colToolsList name" @click="sort_by('name')"><span :class="sort_key==='name'?'sort_col sort_active':'sort_col'">Name</span> <span class="arrow_sort">{{ sort_key==="name"&&sort_order===1?"&darr;":"&uarr;"}} </span></th>
            <th class="colToolsList description">Description</th>
            <th class="colToolsList ownership" @click="sort_by('panel_section_name')"><span :class="sort_key==='panel_section_name'?'sort_col sort_active':'sort_col'">Group owner</span> <span class="arrow_sort">{{ sort_key==="panel_section_name"&&sort_order===1?"&darr;":"&uarr;"}} </span></th>
            <th class="colToolsList version">Latest Version</th>
            <th class="colToolsList edit">Edit</th>
            <th class="colToolsList duplicate">Duplicate</th>
            <th class="colToolsList delete">Delete</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="tool in paginated_tools" :key="tool.id" v-if="!tool.hidden" :id="tool.id">
            <td>{{ tool.name }}</td>
            <td>{{ tool.description | truncate(45, '...') }}</td>
            <td>{{ tool.panel_section_name }}</td>
            <td>{{ tool.version }}</td>
            <td>
              <RouterLink :to="`osug_tool_manager/edit?id=${tool.id}`">
                <button class="btn btn-sm btn-info">
                  <i class="fa fa-pen"></i>
                </button>
              </RouterLink>
            </td>
            <td>
              <RouterLink :to="`osug_tool_manager/create?duplicate_from=${tool.id}`">
                <button class="btn btn-sm btn-info">
                  <i class="fa fa-copy"></i>
                </button>
              </RouterLink>
            </td>
            <td>
              <button @click="delete_tool(tool.id, tool.name)" class="btn btn-sm btn-danger">
                <i class="fa fa-trash"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <b-pagination
      v-if="filter_tools_by_params.length > per_page"
      v-model="current_page"
      :total-rows="nb_pages*per_page"
      :per-page="per_page"
      aria-controls="my-table"
      class="justify-content-end"
    ></b-pagination>
  </div>
</template>