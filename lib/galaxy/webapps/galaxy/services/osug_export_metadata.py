from galaxy.webapps.galaxy.services.base import ServiceBase

import logging

import re

from lib.galaxy.model import Job

log = logging.getLogger(__name__)



class OsugExportMetadataService(ServiceBase):
	def __init__(self, trans):
		self.trans = trans

	"""
		Get invocation from a job ID associated with.

		Note:
			Because of a galaxy back end limitation in the case of a "map over" invocation (tool executed on a collection),
			we can't get the invocation with the "invocationByJob" endpoint. Instead we need to browse the last user invocations and
			check if it contains a job with the same ID that the one in argument.

		Argument:
			- jobID

		Returns the invocation
	"""
	def _get_invocation_by_job_id(self, job_id): #TODO : directly detect if it's map over ?
		sa_session = self.trans.app.model.session

		job = sa_session.query(self.trans.app.model.Job).get(job_id)

		user_id = job.user_id

		invocation_step = job.workflow_invocation_step
		invocation = None
		if invocation_step is None: # In case of a mapover job (we can't get the workflow_invocation_step from a job)
			# TODO : replace for loops with a query with inner join and where job_id ?
			invocations = sa_session.query(self.trans.app.model.WorkflowInvocation).order_by(self.trans.app.model.WorkflowInvocation.update_time.desc()).limit(10) # We get the last 10 workflow invocations
			for invoc in invocations:
				for step in invoc.steps:
					for _job in step.jobs:
						if str(_job.id) == job_id: # We found the invocation with our job id in it
							invocation = invoc
		else:
			invocation = invocation_step.workflow_invocation
		
		return invocation, user_id
		

	"""
		Get invocation details

		Arguments :
			- invocation
			- user_id

		Returns a dict with invocation details
	"""
	def _get_invocation_details(self, invocation, user_id):
		invocation_details = {
			"ID": self.trans.app.security.encode_id(invocation.id), 
			"datetime": invocation.create_time.isoformat(), 
			"userID": user_id
		}
		return invocation_details


	"""
		Get workflow details
		
		Argument :
			- workflow

		Returns a dict with workflow details
	"""
	def _get_workflow_details(self, workflow):
		workflow_details = {
			"ID": self.trans.app.security.encode_id(workflow.id), 
			"version": workflow.version,
			"name": workflow.name,
			"description": ' '.join(workflow.comments),
		}
		return workflow_details


	"""
		Get the jobs from an invocation

		Argument :
			- invocation

		Returns a list with the jobs
	"""
	def _get_jobs_from_invocation(self, invocation):
		jobs = []
		
		sa_session = self.trans.app.model.session
		
		steps = invocation.steps

		for step in steps:
			if step.job_id is not None: # Just in case if there is no job
				job = sa_session.query(self.trans.app.model.Job).get(step.job_id) # Can't use step.job because it's a JobToInputDatasetAssociation object
				jobs.append(job)

		return jobs


	"""
		Get the tool details from a job

		Argument :
			- job
		
		Returns a dict with tool details
	"""
	def _get_tool_details_from_job(self, job):
		tool = self.trans.app.toolbox.get_tool(job.tool_id, job.tool_version) #todo : redondance (avec fonction suivante) -> mettre ça dans une fonction
		tool_dict = tool.to_dict(self.trans, io_details=True, link_details=False)
		tool_description = tool_dict["description"]
		tool_inputs = tool_dict["inputs"]

		tool_details = {
			"name": job.tool_id, 
			"version": job.tool_version, 
			"description": tool_description
		}

		for input in tool_inputs:
			if "value" in input and input["value"] != None:
				if input["name"] 	== "osugTM_url_git_repo":
					tool_details["tool_url_git_repository"] = input["value"]
				elif input["name"] 	== "osugTM_git_commit_ID":
					tool_details["tool_git_commit_ID"] = input["value"]
				elif input["name"] 	== "osugTM_git_tag":
					tool_details["tool_git_tag"] = input["value"]

		return tool_details

	
	"""
		Get inputs details from a job

		Argument :
			- job

		Returns a dict with inputs details
	"""
	def _get_inputs_details_from_job(self, job):
		tool = self.trans.app.toolbox.get_tool(job.tool_id, job.tool_version)

		tool_inputs = tool.to_dict(self.trans, io_details=True, link_details=False)["inputs"] # To be able to directly get the param/input type. We still need .input_datasets to get the path to the file if needed
		job_inputs = job.to_dict("element")["params"] # We need to get the value here because a value is job's specific. But we still need tool_inputs to get the type.


		inputs_details = {}

		special_inputs = ["chromInfo", "dbkey"]

		for input in tool_inputs:
			if input["name"] not in special_inputs and not input["name"].startswith("__") and not input["name"].startswith("osugTM") and not input["name"].endswith("__") and not input["name"].endswith("_path"):
				input_value = ''
				if job_inputs.get(input["name"]):
					input_value = job_inputs[input["name"]] # If available, get the input's value from directly from the job
				elif input["value"] == None: # If no value for tool input, try to get it from job.params (in the case of an expression tool for example, we can't get the value from the tool dict for example)
					for parameter in job.parameters:
						if parameter.name == input["name"]:
							input_value = parameter.value # Has double quotes...
							break
				else:
					input_value = input["value"]
				inputs_details[input["name"]] = {"type": input["type"], "value": str(input_value).replace('"', '')} # Value can be a dict (with one element)/has double quotes


		for input in job.input_datasets: #For data input
			if input.name in inputs_details:
				dataset = input.dataset
				inputs_details[input.name]["value"] = dataset.get_file_name()

		return inputs_details


	"""
		Get outputs details from a job

		Argument :
			- job

		Returns a dict with outputs details
	"""
	def _get_outputs_details_from_job(self, job): 
		outputs_details = {}

		for output in job.output_datasets: # We get the path + the ID
			dataset = output.dataset
			outputName = output.name
			datasetPath = dataset.get_file_name()
			datasetName = dataset.name

			if(outputName.startswith("__") and outputName.endswith("__")): # If it's a collection, the name is different
				originalDatasetNameSearch = re.search("(.+)_[0-9]{3}", datasetName)
				if originalDatasetNameSearch:
					originalDatasetName = originalDatasetNameSearch.group(1)
				else:
					originalDatasetName = datasetName

				outputs_details[originalDatasetName] = datasetPath
			else:
				outputs_details[outputName] = datasetPath
			
		return outputs_details



	"""
		Main function, called by the endpoint.
		From a job_id, get in a dict all the needed traceability metadata about a workflow

		Argument :
			- job_id

		Returns a dict with the traceability metadata
	"""
	def get_data_to_export(self, job_id):
		invocation, user_id = self._get_invocation_by_job_id(job_id)

		jobs = self._get_jobs_from_invocation(invocation)

		tools = []
		for job in jobs:
			if job.tool_id != "osug-metadata-extraction-tool":
				tool = {}

				job_tool_details = self._get_tool_details_from_job(job)

				job_inputs_details = self._get_inputs_details_from_job(job)

				job_outputs_details = self._get_outputs_details_from_job(job)

				tool = job_tool_details
				tool["inputs"] = job_inputs_details
				tool["outputs"] = job_outputs_details


				tools.append(tool)

		invocation_details = self._get_invocation_details(invocation, user_id)

		workflow = invocation.workflow # type: ignore
		workflow_details = self._get_workflow_details(workflow)
		
		data = {
			"workflow": workflow_details,
			"invocation": invocation_details,
			"tools": tools
		}

		#TODO : create a model for data ?

		return data