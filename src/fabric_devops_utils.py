"""Fabric DevOps Utility Classes"""
# this version of fabric_devops specific for GitHub projects
# updated: 03/14/2026

import base64
import re
import os
import time
import json
from json.decoder import JSONDecodeError
from typing import List
import requests
from nacl import encoding, public

from azure.identity import DefaultAzureCredential
from microsoft_fabric_api import FabricClient

class EnvironmentSettings:
    """Environment Settings"""

    AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
    AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
    AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
    AUTHORITY = f'https://login.microsoftonline.com/{AZURE_TENANT_ID}'
    FABRIC_CAPACITY_ID = os.getenv("FABRIC_CAPACITY_ID")

    WORKSPACE_ID_DEV = os.getenv("WORKSPACE_ID_DEV")
    WORKSPACE_ID_TEST = os.getenv("WORKSPACE_ID_TEST")
    WORKSPACE_ID_PROD = os.getenv("WORKSPACE_ID_PROD")

    ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
    DEVELOPERS_GROUP_ID = os.getenv("DEVELOPERS_GROUP_ID")
    
    PERSONAL_ACCESS_TOKEN_GITHUB = os.getenv('PERSONAL_ACCESS_TOKEN_GITHUB')
    GITHUB_REPOSITORY_NAME = os.getenv('GITHUB_REPOSITORY_NAME')
    ORGANIZATION_GITHUB = os.getenv('ORGANIZATION_GITHUB')
    
    AZURE_STORAGE_SAS_TOKEN = os.getenv('AZURE_STORAGE_SAS_TOKEN')

    FABRIC_REST_API_RESOURCE_ID = 'https://api.fabric.microsoft.com'
    FABRIC_REST_API_BASE_URL = 'https://api.fabric.microsoft.com/v1/'
    POWER_BI_REST_API_BASE_URL = 'https://api.powerbi.com/v1.0/myorg/'
    
    DEPLOYMENT_JOBS = {
        'dev': {
            'name': 'dev',
            'parameters': {
                'web_datasource_path': 'https://github.com/FabricDevCamp/SampleData/raw/refs/heads/main/productsales/dev/',
                'adls_server': 'https://fabricdevcamp.dfs.core.windows.net/',
                'adls_container_name': 'sampledata', 
                'adls_container_path': '/productsales/dev'
            }            
        },
        'test': {
            'name': 'test',
            'parameters': {
                'web_datasource_path': 'https://github.com/FabricDevCamp/SampleData/raw/refs/heads/main/productsales/test/',
                'adls_server': 'https://fabricdevcamp.dfs.core.windows.net/',
                'adls_container_name': 'sampledata', 
                'adls_container_path': '/productsales/test'
            }
        },
        "prod": {
            'name': 'prod',
            'parameters': {
                'web_datasource_path': 'https://github.com/FabricDevCamp/SampleData/raw/refs/heads/main/productsales/prod/',
                'adls_server': 'https://fabricdevcamp.dfs.core.windows.net/',
                'adls_container_name': 'sampledata',
                'adls_container_path': '/productsales/prod'
            }
        }
    }
    
class AppLogger:
    """Logic to write log output to console and/or logs"""

    @classmethod
    def clear_console(cls):
        """Clear Console Window when running locally"""
        if os.name == 'nt':
            os.system('cls')

    @classmethod
    def log_job(cls, message):
        """start job"""
        print(' ', flush=True)
        print(' ', flush=True)
        print(('-' * (len(message) + 5)) , flush=True)
        print(f'|> {message} |', flush=True)
        print(('-' * (len(message) + 5)) , flush=True)

    @classmethod
    def log_job_ended(cls, message=''):
        """log that job has ended"""
        print(' ', flush=True)
        print(f'> {message}', flush=True)
        print(' ', flush=True)

    @classmethod
    def log_job_complete(cls, workspace_id=None):
        """log that job has ended"""
        cls.log_step("Deployment job completed")
        if workspace_id is not None:
            workspace_launch_url = (
                f'https://app.powerbi.com/groups/{workspace_id}/list?experience=fabric-developer'
            )
            cls.log_substep(f'Workspace launch URL: {workspace_launch_url}')
        print(' ', flush=True)

    @classmethod
    def log_step(cls, message):
        """log a step"""
        print(' ', flush=True)
        print('> ' + message, flush=True)

    @classmethod
    def log_substep(cls, message):
        """log a sub step"""
        print('  - ' + message, flush=True)

    @classmethod
    def log_step_complete(cls):
        """add linebreak to log"""
        print(' ', flush=True)

    TABLE_WIDTH = 120

    @classmethod
    def log_table_header(cls, table_title):
        """Log Table Header"""
        print(' ', flush=True)
        print(f'> {table_title}', flush=True)
        print('  ' + ('-' * (cls.TABLE_WIDTH)), flush=True)

    @classmethod
    def log_table_row(cls, column1_value, column2_value):
        """Log Table Row"""
        column1_width = 20
        column1_value_length = len(column1_value)
        column1_offset = column1_width - column1_value_length
        column2_width = cls.TABLE_WIDTH - column1_width
        column2_value_length = len(column2_value)
        column2_offset = column2_width - column2_value_length - 5
        row = f'  | {column1_value}{" " * column1_offset}| {column2_value}{" " * column2_offset}|'
        print(row, flush=True)
        print('  ' + ('-' * (cls.TABLE_WIDTH)), flush=True)

    @classmethod
    def log_raw_text(cls, text):
        """log raw text"""
        print(text, flush=True)
        print('', flush=True)

    @classmethod
    def log_error(cls, message):
        """log error"""
        error_message = "ERROR: " + message
        print('-' * len(error_message), flush=True)
        print(error_message, flush=True)
        print('-' * len(error_message), flush=True)

class GitHubRestApi:
    """Wrapper class for calling GitHub REST APIs"""

    ACCESS_TOKEN = EnvironmentSettings.PERSONAL_ACCESS_TOKEN_GITHUB

    ORGANIZATION_GITHUB = EnvironmentSettings.ORGANIZATION_GITHUB
    BASE_URL = 'https://api.github.com/'

#region Low-level details about authentication and HTTP requests and responses

    @classmethod
    def _execute_get_request(cls, endpoint):
        """Execute GET Request on Fabric REST API Endpoint"""
        rest_url = cls.BASE_URL + endpoint
        request_headers = {'Content-Type':'application/json',
                           'Authorization': f'token {cls.ACCESS_TOKEN}'}
        response = requests.get(url=rest_url, headers=request_headers, timeout=60)
        if response.status_code == 200:
            return response.json()
        else:
            AppLogger.log_error(
                f'Error executing GET request: {response.status_code} - {response.text}')
            return None

    @classmethod
    def _execute_post_request(cls, endpoint, post_body='', content_type = 'application/json'):

        """Execute POST request with support for Long-running Operations (LRO)"""
        rest_url = cls.BASE_URL + endpoint
        request_headers = {'Content-Type': content_type,
                           'Authorization': f'token {cls.ACCESS_TOKEN}'}           
        response = requests.post(url=rest_url, json=post_body, headers=request_headers, timeout=60)

        if response.status_code in { 200, 201 }:
            try:
                return response.json()
            except JSONDecodeError:
                return None

        if response.status_code == 202:
            AppLogger.log_step("Got back 202 ACCEPTED from POST Request")
            operation_state_url = response.headers.get('Location')
            wait_time = 10 # int(response.headers.get('Retry-After'))
            time.sleep(wait_time)
            response = requests.get(url=operation_state_url, headers=request_headers, timeout=60)
            operation_state = response.json()
            while operation_state['status'] != 'Succeeded' and \
                  operation_state['status'] != 'Failed':
                time.sleep(wait_time)
                response = requests.get(url=operation_state_url,
                                        headers=request_headers,
                                        timeout=60)
                operation_state = response.json()

            if operation_state['status'] == 'Succeeded':
                if 'Location' in response.headers:
                    operation_result_url = response.headers.get('Location')
                    response = requests.get(url=operation_result_url,
                                            headers=request_headers,
                                            timeout=60)
                    if response.status_code == 200:
                        return response.json()
                    else:
                        AppLogger.log_error(f"Error - {response.status_code}")
                        return None
                else:
                    return None
            else:
                AppLogger.log_error(f"Error - {operation_state}")

        elif response.status_code == 429: # handle TOO MANY REQUESTS error
            wait_time = int(response.headers.get('Retry-After'))
            time.sleep(wait_time)
            return cls._execute_post_request(endpoint, post_body)
        else:
            AppLogger.log_error(
                f'Error executing POST request: {response.status_code} - {response.text}')
            return None

    @classmethod
    def _execute_put_request(cls, endpoint, post_body='',  content_type = 'application/json'):
        """Execute PUT request """
        rest_url = cls.BASE_URL + endpoint
        request_headers = {
            'Content-Type': content_type,
            'Authorization': f'token {cls.ACCESS_TOKEN}'
        }           
        response = requests.put(url=rest_url, json=post_body, headers=request_headers, timeout=60)

        if response.status_code in { 200, 201 }:
            try:
                return response.json()
            except JSONDecodeError:
                return None

        if response.status_code == 202:
            AppLogger.log_step("Got back 202 ACCEPTED from PUT  Request")

        AppLogger.log_error(
            f'Error executing POST request: {response.status_code} - {response.text}')

    @classmethod
    def _execute_put_request_with_file(cls, endpoint, post_body=''):
        """Execute PUT request """
        rest_url = cls.BASE_URL + endpoint
        request_headers = {'Content-Type':'application/vnd.github+json',
                           'Authorization': f'token {cls.ACCESS_TOKEN}'}           
        response = requests.put(url=rest_url, json=post_body, headers=request_headers, timeout=60)

        if response.status_code in { 200, 201 }:
            try:
                return response.json()
            except JSONDecodeError:
                return None

        AppLogger.log_error(
            f'Error executing Put request: {response.status_code} - {response.text}')

    @classmethod
    def _execute_patch_request(cls, endpoint, post_body):
        """Execute GET Request on Fabric REST API Endpoint"""
        rest_url = cls.BASE_URL + endpoint
        request_headers = {'Content-Type':'application/json',
                           'Authorization': f'token {cls.ACCESS_TOKEN}'}
        response = requests.patch(url=rest_url, json=post_body, headers=request_headers, timeout=60)
        if response.status_code == 200:
            return response.json()

        if response.status_code == 429: # handle TOO MANY REQUESTS error
            wait_time = int(response.headers.get('Retry-After'))
            time.sleep(wait_time)
            return cls._execute_patch_request(endpoint, post_body)
        else:
            AppLogger.log_error(
                f'Error executing PATCH request: {response.status_code} - {response.text}')
            return None


    @classmethod
    def _execute_delete_request(cls, endpoint):
        """Execute DELETE Request on Fabric REST API Endpoint"""
        rest_url = cls.BASE_URL + endpoint
        request_headers = {'Content-Type':'application/json',
                           'Authorization': f'token {cls.ACCESS_TOKEN}'}

        response = requests.delete(url=rest_url, headers=request_headers, timeout=60)
        if response.status_code in { 200, 204 }:
            return None
        if response.status_code == 429: # handle TOO MANY REQUESTS error
            wait_time = int(response.headers.get('Retry-After'))
            time.sleep(wait_time)
            cls._execute_delete_request(endpoint)
            return None
        else:
            AppLogger.log_error(
                f'Error executing DELETE request: {response.status_code} - {response.text}')
            return None

#endregion

    @classmethod
    def get_github_user(cls):
        """Get GitHub User"""
        endpoint = "user"
        return cls._execute_get_request(endpoint)

    @classmethod
    def get_github_repositories(cls):
        """Get GitHub Repositories"""
        endpoint = f"orgs/{cls.ORGANIZATION_GITHUB}/repos"
        return cls._execute_get_request(endpoint)

    @classmethod
    def display_github_repos(cls):
        """Display GitHub Repositories"""
        AppLogger.log_step('Repos')
        repos = cls.get_github_repositories()
        for repo in repos:
            AppLogger.log_substep(f"{repo['name']} [{repo['id']}]")

    @classmethod
    def get_github_repository_by_name(cls, repo_name):
        """Get GitHub Repository by Name"""
        repos = cls.get_github_repositories()
        for repo in repos:
            if repo['name'] == repo_name:
                return repo
        return None

    @classmethod
    def create_repository(cls, repo_name, branches = None, private = False):
        """Create GitHub Repository"""
        AppLogger.log_step(f"Creating new GitHub repository [{repo_name}]")
        repo = cls.get_github_repository_by_name(repo_name)
        if repo is not None:
            AppLogger.log_substep("Deleting existing repo with same name")
            cls.delete_github_repository(repo_name)

        endpoint = f"/orgs/{cls.ORGANIZATION_GITHUB}/repos"
        body = {
            'name': repo_name,
            'private': private,
            'auto_init': True
        }
        repo = cls._execute_post_request(endpoint, body)
        AppLogger.log_substep("Repo created successfully")

        cls.create_workspace_readme(repo_name)

        if branches is not None:
            for branch in branches:
                cls.create_branch(repo_name, branch)

        return repo

    @classmethod
    def delete_github_repository(cls, repo_name):
        """Delete GitHub Repository"""
        endpoint = f"repos/{cls.ORGANIZATION_GITHUB}/{repo_name}"
        return cls._execute_delete_request(endpoint)

    @classmethod
    def list_branches(cls, repo_name):
        """Create GitHub Repository Branch"""
        endpoint = f"/repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/branches"
        repos = cls._execute_get_request(endpoint)
        return repos

    @classmethod
    def get_branch_by_name(cls, repo_name, branch_name):
        """Create GitHub Repository Branch"""
        endpoint = f"/repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/branches/{branch_name}"
        repos = cls._execute_get_request(endpoint)
        return repos

    @classmethod
    def get_sha_for_branch(cls, repo_name, branch_name):
        """Create GitHub Repository Branch"""
        branch = cls.get_branch_by_name(repo_name, branch_name)
        return branch['commit']['sha']

    @classmethod
    def compare_branches(cls, repo_name, source_branch, target_branch):
        """Create GitHub Repository Branch"""
        endpoint = f"repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/compare/{target_branch}...{source_branch}"
        result = cls._execute_get_request(endpoint)
        return result

    @classmethod
    def create_branch(cls, repo_name, branch_name, source_branch = 'main'):
        """Create GitHub Repository Branch"""
        AppLogger.log_substep(f"Creating branch [{branch_name}] from [{source_branch}]")
        
        sha = cls.get_sha_for_branch(repo_name, source_branch)

        endpoint_refs = f"repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/git/refs"

        body = {
            'ref': f'refs/heads/{branch_name}',
            "sha": sha
        }

        return cls._execute_post_request(endpoint_refs, body)

    @classmethod
    def create_pull_request(
        cls, 
        repo_name, 
        source_branch, 
        target_branch, 
        commit_title, 
        commit_comment):
        """Create GitHub Repository Branch"""
        AppLogger.log_substep(f"Creating pull request for branch [{source_branch}]")

        endpoint_pull_requests = f"repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/pulls"

        body = {
            'owner': cls.ORGANIZATION_GITHUB,
            'repo': repo_name,
            'title': commit_title,
            'body': commit_comment,
            'head': (cls.ORGANIZATION_GITHUB + ":" + source_branch),
            'base': target_branch
        }

        return cls._execute_post_request(
            endpoint_pull_requests,
            body,
            content_type='application/vnd.github.raw+json')

    @classmethod
    def merge_pull_request(cls, repo_name, pull_number, commit_title, commit_comment):
        """Create GitHub Repository Branch"""
        AppLogger.log_substep(f"Merge pull request [{commit_title}]")

        endpoint_pull_request = f"repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/pulls/{pull_number}"
        pull_request = cls._execute_get_request(endpoint_pull_request)

        pull_request_mergable = pull_request['mergeable']

        while pull_request_mergable is not True:
            time.sleep(2)
            pull_request = cls._execute_get_request(endpoint_pull_request)
            pull_request_mergable = pull_request['mergeable']

        endpoint_pull_request_merge = f"repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/pulls/{pull_number}/merge"

        body = {
            'owner': cls.ORGANIZATION_GITHUB,
            'repo': repo_name, 
            'pull_number': str(pull_number),
            'commit_title': commit_title,
            'commit_message': commit_comment,
        }

        return cls._execute_put_request(
            endpoint_pull_request_merge,
            body,
            content_type='application/vnd.github+json')

    @classmethod
    def create_and_merge_pull_request(
        cls,
        repo_name,
        source_branch,
        target_branch,
        commit_title,
        commit_comment):
        """Create and Merge Pull Request"""
        AppLogger.log_step(f"Merging changes from [{source_branch}] to [{target_branch}]")

        comparison = GitHubRestApi.compare_branches(repo_name, source_branch, target_branch)

        comparison_has_no_commits = len(comparison['commits']) == 0
        
        if comparison_has_no_commits:
            AppLogger.log_substep("No need to create pull request because the two branches are already in sync")
            return
              
        pull_request = cls.create_pull_request(
            repo_name,
            source_branch,
            target_branch,
            commit_title,
            commit_comment
        )
        
        pull_request_number = pull_request['number']
        cls.merge_pull_request(repo_name, pull_request_number, commit_title, commit_comment)

    @classmethod
    def create_workspace_readme(cls, repo_name):
        """Create Content"""
        content = f"## ReadMe file for {repo_name}"
        base64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')

        endpoint = f"repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/contents/workspace/readme.md"

        body = {
            "message":"Adding ReadMe.md file",
            "content": base64_content
        }
        
        cls._execute_put_request(endpoint, body)

    @classmethod
    def write_file_to_repo(cls, repo_name, branch, file_path, file_content, comment = None):
        """Create Content"""        
        if comment is None:
            comment = f'Writing file {file_path}'
        
        base64_content = base64.b64encode(file_content.encode('utf-8')).decode('utf-8')
        endpoint = f"repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/contents/{file_path}"
        body = {
            "message": comment,
            "content": base64_content,
            "branch": branch
        }
        
        cls._execute_put_request_with_file(endpoint, body)

    @classmethod
    def set_default_branch(cls, repo_name, default_branch_name):
        """Create GitHub Repository Branch"""
        AppLogger.log_substep(f"Setting [{default_branch_name}] branch as default branch")
        endpoint = f"repos/{cls.ORGANIZATION_GITHUB}/{repo_name}"
        body = {
            'name': repo_name,
            'default_branch': default_branch_name
        }
        cls._execute_patch_request(endpoint, body)

    @classmethod
    def _get_part_path(cls, item_folder_path, file_path):
        """get path for item definition part"""
        offset = file_path.find(item_folder_path) + len(item_folder_path)
        return file_path[offset:].replace('\\', '/')

    @classmethod
    def copy_files_from_folder_to_repo(cls, repo_name, branch, folder_path):
        """Copy files to repo"""
        folder_path = f".//templates//WorkflowActions//{folder_path}//"
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                file = open(file_path,'r', encoding="utf-8")
                file_content = file.read()
                relative_file_path = file_path.replace(folder_path, '')\
                                              .replace('\\', '/')
                cls.write_file_to_repo(repo_name, branch, relative_file_path, file_content)

    @classmethod
    def _get_org_public_key(cls):
        """Create GitHub Repository Branch"""
        endpoint = f"/orgs/{cls.ORGANIZATION_GITHUB}/actions/secrets/public-key"
        return cls._execute_get_request(endpoint)

    @classmethod
    def create_organization_secret(cls, repo_name, secret_name, secret_value):
        """Create repository secret"""

        public_key_result = cls._get_org_public_key()
        public_key_id = public_key_result['key_id']
        public_key_value = public_key_result['key']        
        public_key = public.PublicKey(public_key_value.encode("utf-8"), encoding.Base64Encoder())
        sealed_box = public.SealedBox(public_key)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        base64_encrypted = base64.b64encode(encrypted).decode("utf-8")

        endpoint = f"/orgs/{cls.ORGANIZATION_GITHUB}/actions/secrets/{secret_name}"
        body = {
            'owner': cls.ORGANIZATION_GITHUB,
            'repo': repo_name,
            'secret_name': secret_name,
            'encrypted_value': base64_encrypted,
            'key_id': public_key_id,
            'visibility': 'all'
        }

        cls._execute_put_request(endpoint, body, 'application/vnd.github+json')

    @classmethod
    def _get_repo_public_key(cls, repo_name):
        """Create GitHub Repository Branch"""
        endpoint = f"/repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/actions/secrets/public-key"
        return cls._execute_get_request(endpoint)

    @classmethod
    def create_repository_secret(cls, repo_name, secret_name, secret_value):
        """Create repository secret"""

        public_key_result = cls._get_repo_public_key(repo_name)
        public_key_id = public_key_result['key_id']
        public_key_value = public_key_result['key']        
        public_key = public.PublicKey(public_key_value.encode("utf-8"), encoding.Base64Encoder())
        sealed_box = public.SealedBox(public_key)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        base64_encrypted = base64.b64encode(encrypted).decode("utf-8")

        endpoint = f"/repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/actions/secrets/{secret_name}"
        body = {
            'owner': cls.ORGANIZATION_GITHUB,
            'repo': repo_name,
            'secret_name': secret_name,
            'encrypted_value': base64_encrypted,
            'key_id': public_key_id
        }

        cls._execute_put_request(endpoint, body, 'application/vnd.github+json')

    @classmethod
    def create_repository_variable(cls, repo_name, variable_name, variable_value):
        """Create repository variable"""

        endpoint = f"/repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/actions/variables"
        body = {
            'owner': cls.ORGANIZATION_GITHUB,
            'repo': repo_name,
            'name': variable_name,
            'value': variable_value,
        }

        cls._execute_post_request(endpoint, body, 'application/vnd.github+json')

    @classmethod
    def create_variables_for_github_project(
        cls, 
        repo_name, 
        dev_workspace_id, 
        test_workspace_id,
        prod_workspace_id):
        """Add Variables to GitHub repo"""

        AppLogger.log_step(f"Creating variables in repo [{repo_name}]")        
        
        cls.create_repository_secret(repo_name, 'AZURE_CLIENT_ID', EnvironmentSettings.AZURE_CLIENT_ID)
        cls.create_repository_secret(repo_name, 'AZURE_CLIENT_SECRET', EnvironmentSettings.AZURE_CLIENT_SECRET)
        cls.create_repository_secret(repo_name, 'AZURE_TENANT_ID', EnvironmentSettings.AZURE_TENANT_ID)
        cls.create_repository_secret(repo_name, 'PERSONAL_ACCESS_TOKEN_GITHUB', EnvironmentSettings.PERSONAL_ACCESS_TOKEN_GITHUB)
        cls.create_repository_variable(repo_name, 'ORGANIZATION_GITHUB', EnvironmentSettings.ORGANIZATION_GITHUB)
        cls.create_repository_variable(repo_name, 'ADMIN_USER_ID', EnvironmentSettings.ADMIN_USER_ID)
        cls.create_repository_variable(repo_name, 'FABRIC_CAPACITY_ID', EnvironmentSettings.FABRIC_CAPACITY_ID)
        cls.create_repository_variable(repo_name, 'WORKSPACE_ID_DEV', dev_workspace_id)
        cls.create_repository_variable(repo_name, 'WORKSPACE_ID_TEST', test_workspace_id)
        cls.create_repository_variable(repo_name, 'WORKSPACE_ID_PROD', prod_workspace_id)

    @classmethod
    def run_workflow(cls, repo_name, workflow_file_name, branch):
        """Run GitHub Workflow"""
        
        AppLogger.log_step(f"Running Workflow [{workflow_file_name}] on branch [{branch}]") 
        
        endpoint = f"/repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/actions/workflows/{workflow_file_name}/dispatches"
        body = { 
            "ref":branch,
            'return_run_details': True
        }
        
        reponse = cls._execute_post_request(endpoint, body)
        workflow_run_id = reponse['workflow_run_id']
        workflow_run = cls.get_workflow_run(repo_name, workflow_run_id)
        
        AppLogger.log_substep(f"Workflow run status: {workflow_run['status']}")
        
        while workflow_run['status'] != 'completed':
            time.sleep(20)         
            workflow_run = cls.get_workflow_run(repo_name, workflow_run_id)
            AppLogger.log_substep(f"Workflow run status: {workflow_run['status']}")

        AppLogger.log_substep(f"Workflow run conclusion: {workflow_run['conclusion']}")
        
    @classmethod
    def get_workflow_run(cls, repo_name, run_id):
        """Get GitHub Workflow Run Status"""
        endpoint = f"/repos/{cls.ORGANIZATION_GITHUB}/{repo_name}/actions/runs/{run_id}"
        response = cls._execute_get_request(endpoint)
        return response

class FabricRestApi:
    """Fabric REST API Wrapper Class"""
    
    #region class-level fields

    # used for creating DefaultAzureCredential connections with SPN creds
    AZURE_TENANT_ID = EnvironmentSettings.AZURE_TENANT_ID
    AZURE_CLIENT_ID = EnvironmentSettings.AZURE_CLIENT_ID
    AZURE_CLIENT_SECRET = EnvironmentSettings.AZURE_CLIENT_SECRET
    
    credential = DefaultAzureCredential()
    fabric_client = FabricClient(credential)

    ADMIN_USER_ID = EnvironmentSettings.ADMIN_USER_ID
    DEVELOPERS_GROUP_ID = EnvironmentSettings.DEVELOPERS_GROUP_ID
    FABRIC_CAPACITY_ID = EnvironmentSettings.FABRIC_CAPACITY_ID
    
    # used for creating ADLS connections using SAS token
    AZURE_STORAGE_SAS_TOKEN = EnvironmentSettings.AZURE_STORAGE_SAS_TOKEN

    #endregion
    
    #region capacity functions
    
    @classmethod
    def list_capacities(cls):
        """list capacities accessible to caller"""
        return cls.fabric_client.core.capacities.list_capacities()

    @classmethod
    def display_capacities(cls):
        """Display capacities in console"""
        capacities = cls.list_capacities()
        AppLogger.log_step("Capacities:")
        for capacity in capacities:
            AppLogger.log_substep(f"Capacity: {capacity.display_name}, ID: {capacity.id}")

    #endregion

    #region workspace functions

    @classmethod
    def list_workspaces(cls):
        """list workspaces accessible to caller"""
        return cls.fabric_client.core.workspaces.list_workspaces()

    @classmethod
    def display_workspaces(cls):
        """Display workspaces in console"""
        workspaces = cls.list_workspaces()
        AppLogger.log_step("Workspaces:")
        for workspace in workspaces:
            AppLogger.log_substep(f"Workspace: {workspace.display_name}, ID: {workspace.id}")        
        
    @classmethod
    def get_workspace_info(cls, workspace_id):
        """Get Workspace information by ID"""
        return cls.fabric_client.core.workspaces.get_workspace(workspace_id)

    @classmethod
    def get_workspace_by_name(cls, display_name):
        """Get Workspace item by display name"""
        workspaces = cls.list_workspaces()
        for workspace in workspaces:
            if workspace.display_name == display_name:
                return workspace
        return None
    
    @classmethod
    def get_workspace_info_by_name(cls, display_name):
        """Get Workspace information by ID"""
        workspace = cls.get_workspace_by_name(display_name)        
        return cls.fabric_client.core.workspaces.get_workspace(workspace.id)

    @classmethod
    def create_workspace(cls, display_name, capacity_id = None):
        """Create a new Fabric workspace"""
        AppLogger.log_step(f'Creating workspace [{display_name}]')

        if capacity_id is None:
            capacity_id = 'ccf863ed-7145-4789-811d-d9bcd4a8563f'

        existing_workspace = cls.get_workspace_by_name(display_name)
        if existing_workspace is not None:
            AppLogger.log_substep("Deleting existing workspace with the same name")
            cls.delete_workspace(existing_workspace.id)
        
        create_request = {
            "display_name": display_name,
            "capacity_id": capacity_id
        }

        workspace = cls.fabric_client.core.workspaces.create_workspace(
            create_workspace_request=create_request
        )
        
        workspace_id = workspace.id
        AppLogger.log_substep(f'Workspace created with Id of [{workspace_id}]')
        
        # add workspace role assignment for admin user
        AppLogger.log_substep('Adding workspace role assignment for admin user')
        cls.add_workspace_role_assignment_for_user(
            workspace_id=workspace_id,
            user_id=cls.ADMIN_USER_ID,
            role_name='Admin'
        )        

        return workspace

    @classmethod
    def get_or_create_workspace(cls, display_name, capacity_id = None):
        """Get or create workspace"""

        existing_workspace = cls.get_workspace_by_name(display_name)
        if existing_workspace is not None:
            AppLogger.log_step(f"Getting existing workspace {display_name}")
            return existing_workspace
                
        return cls.create_workspace(display_name, capacity_id)

    @classmethod
    def update_workspace_description(cls, workspace_id, description = None):
        """Update Workspace properties"""
        
        update_request = {
            'description': description
        }
                    
        cls.fabric_client.core.workspaces.update_workspace(
            workspace_id=workspace_id, 
            update_workspace_request=update_request
        )

    @classmethod
    def add_workspace_role_assignment_for_user(cls, workspace_id, user_id, role_name):
        """Add workspace user"""
   
        add_role_request = {
            "role": role_name,
            "principal": {
                'id': user_id,
                'type': 'User'                
            }            
        }

        cls.fabric_client.core.workspaces.add_workspace_role_assignment(        
            workspace_id=workspace_id,
            workspace_role_assignment_request=add_role_request
        )

    @classmethod
    def add_workspace_role_assignment_for_group(cls, workspace_id, group_id, role_name):
        """Add workspace group"""

        add_role_request = {
            "role": role_name,
            "principal": {
                'id': group_id,
                'type': 'Group'                
            }            
        }

        cls.fabric_client.core.workspaces.add_workspace_role_assignment(        
            workspace_id=workspace_id,
            workspace_role_assignment_request=add_role_request
        )

    @classmethod
    def add_workspace_role_assignment_for_spn(cls, workspace_id, spn_id, role_name):
        """Add workspace service principal"""

        add_role_request = {
            "role": role_name,
            "principal": {
                'id': spn_id,
                'type': 'ServicePrincipal'                
            }            
        }

        cls.fabric_client.core.workspaces.add_workspace_role_assignment(        
            workspace_id=workspace_id,
            workspace_role_assignment_request=add_role_request
        )

    @classmethod
    def provision_workspace_identity(cls, workspace_id, workspace_role = 'Admin'):
        """Provision Workspace Identity"""        
        workspace_identity = cls.fabric_client.core.workspaces.provision_identity(workspace_id=workspace_id)        
        service_principal_id = workspace_identity.service_principal_id
        cls.add_workspace_role_assignment_for_spn(workspace_id, service_principal_id, workspace_role)

    @classmethod
    def workspace_has_provisioned_identity(cls, workspace_id):
        """Check if Workspace has a provisioned identity"""
        workspace_info = cls.get_workspace_info(workspace_id)
        return (workspace_info.workspace_identity is not None)

    @classmethod
    def deprovision_workspace_identity(cls, workspace_id):
        """Deprovision Workspace Identity"""        
        cls.fabric_client.core.workspaces.deprovision_identity(workspace_id=workspace_id)        

    @classmethod
    def delete_workspace(cls, workspace_id):
        """Delete Workspace"""        
        cls.fabric_client.core.workspaces.delete_workspace(workspace_id=workspace_id)        

    #endregion
    
    #region connection functions

    @classmethod
    def list_connections(cls):
        """List all connections accessible to caller"""
        return cls.fabric_client.core.connections.list_connections()

    @classmethod
    def get_connection_by_name(cls, display_name):
        """Get Connection By Name"""
        connections = cls.list_connections()
        for connection in connections:
            if connection.display_name == display_name:
                return connection
        return None

    @classmethod
    def display_connections(cls):
        """Display all connections accessible to caller"""
        connections = cls.list_connections()
        AppLogger.log_step("Connections:")
        for conn in connections:
            AppLogger.log_substep(f" - {conn.display_name}, ID: {conn.id}")

    @classmethod
    def list_supported_connection_types(cls):
        """list all connection types supported by Fabric"""
        return cls.fabric_client.core.connections.list_supported_connection_types()

    @classmethod
    def get_connection_type_metadata(cls, type_name):
        """list all connection types supported by Fabric"""
        supported_types = cls.fabric_client.core.connections.list_supported_connection_types()
        for conn_type in supported_types:
            if conn_type.type == type_name:
                return conn_type
            
        return None

    @classmethod
    def display_supported_connection_types(cls):
        """Display all connection types supported by Fabric"""
        connection_types = cls.list_supported_connection_types()
        AppLogger.log_step("Supported Connection Types:")        
        for conn_type in connection_types:
            AppLogger.log_substep(f"{conn_type.type}")

    @classmethod
    def display_connection_type_metadata(cls, type_name):
        """list all connection types supported by Fabric"""
        target_type = cls.get_connection_type_metadata(type_name)
        AppLogger.log_step(json.dumps(target_type.as_dict(), indent=4))

    @classmethod
    def create_connection(cls, create_connection_request):
        """ Create new connection"""
        AppLogger.log_substep(f"Creating connection {create_connection_request['displayName']} ...")

        existing_connections = cls.list_connections()
        for connection in existing_connections:
            if connection.display_name is not None and connection.display_name  == create_connection_request['displayName']:
                AppLogger.log_substep(f"Using existing Connection with id [{connection.id}]")
                return connection

        connection = cls.fabric_client.core.connections.create_connection(
            create_connection_request=create_connection_request
        )

        AppLogger.log_substep(f"Connection created with id [{connection.id}]")

        # add admin user as co-owner of connection
        cls.add_connection_role_assignment_for_user(
            connection.id,
            cls.ADMIN_USER_ID,
            'Owner'
        )
     
        return connection

    @classmethod
    def add_connection_role_assignment_for_user(cls, connection_id, admin_user_id, connection_role):
        """Add connection role assignment for user"""
        
        assignment_request = {
            'principal': {
                'id': admin_user_id,
                'type': "User"
            },
            'role': connection_role
        }
        
        return cls.fabric_client.core.connections.add_connection_role_assignment(
            connection_id=connection_id,
            add_connection_role_assignment_request=assignment_request
        )

    @classmethod
    def create_anonymous_web_connection(cls, web_url):
        """Create new Web connection using Anonymous credentials"""
        display_name = f'Web-Anonymous-[{web_url}]'

        create_connection_request = {
            'displayName': display_name,
            'connectivityType': 'ShareableCloud',
            'privacyLevel': 'Organizational',
            'connectionDetails': {
                'type': 'Web',
                'creationMethod': 'Web',
                'parameters': [ 
                    {
                        'value': web_url,
                        'dataType': 'Text',
                        'name': 'url'
                    }
                ]
            },
            'credentialDetails': {
                'credentials': {
                    'credentialType': 'Anonymous' 
                },
                'singleSignOnType': 'None',
                'connectionEncryption': 'NotEncrypted',
                'skipTestConnection': 'false'
            }
        }

        return cls.create_connection(create_connection_request)

    @classmethod
    def create_azure_storage_connection_with_sas_token(cls, server, path):
        """Create Azure Storage connections"""
        display_name = ""
        
        display_name = f"ADLS-SAS-[{server}{path}]"
        
        create_connection_request = {
            'displayName': display_name,
            'connectivityType': 'ShareableCloud',
            'privacyLevel': 'Organizational',
            'connectionDetails': {
                'type': 'AzureDataLakeStorage',
                'creationMethod': 'AzureDataLakeStorage',
                'parameters': [ 
                    { 'value': server, 'dataType': 'Text', 'name': 'server' },
                    { 'value': path, 'dataType': 'Text', 'name': 'path' }
                ]
            },
            'credentialDetails': {
                'credentials': {
                    'token': cls.AZURE_STORAGE_SAS_TOKEN,
                    'credentialType': 'SharedAccessSignature'
                },
                'singleSignOnType': 'None',
                'connectionEncryption': 'NotEncrypted',
                'skipTestConnection': 'false'
            }
        }

        return cls.create_connection(create_connection_request)

    @classmethod
    def create_sql_connection_with_service_principal(cls, server, database,
                                                          workspace = None, lakehouse = None):
        """Create SQL Connection"""
        display_name = ''
        if workspace is not None:
            display_name = f"Workspace[{workspace.id}]-" + display_name
            if lakehouse is not None:
                display_name = display_name + f"Lakehouse[{lakehouse.display_name}]-SqlEndpoint"
            else:
                display_name = display_name + 'SQL'
        else:
            display_name = f'SQL-{server}:{database}'

        create_connection_request = {
            'displayName': display_name,
            'connectivityType': 'ShareableCloud',
            'privacyLevel': 'Organizational',
            'connectionDetails': {
                'type': 'SQL',
                'creationMethod': 'Sql',
                'parameters': [ 
                    { 'value': server, 'dataType': 'Text', 'name': 'server' },
                    { 'value': database, 'dataType': 'Text', 'name': 'database' }
                ]
            },
            'credentialDetails': {
                'credentials': {
                    'tenantId': cls.AZURE_TENANT_ID,
                    'servicePrincipalClientId': cls.AZURE_CLIENT_ID,
                    'servicePrincipalSecret': cls.AZURE_CLIENT_SECRET,
                    'credentialType': 'ServicePrincipal'
                },
                'singleSignOnType': 'None',
                'connectionEncryption': 'NotEncrypted',
                'skipTestConnection': 'false'
            }
        }

        return cls.create_connection(create_connection_request)

    @classmethod
    def create_azure_storage_connection_with_service_principal(cls, server, path,
                                                                workspace = None, lakehouse = None):
        """Create Azure Storage connections"""

        display_name = ''
        if workspace is not None:
            display_name = f"Workspace[{workspace.id}]-" + display_name
            if lakehouse is not None:
                display_name = display_name + f"Lakehouse[{lakehouse.display_name}]-Onelake"
        else:
            display_name = f'ADLS-SPN-{server}:{path}'

        create_connection_request = {
            'displayName': display_name,
            'connectivityType': 'ShareableCloud',
            'privacyLevel': 'Organizational',
            'connectionDetails': {
                'type': 'AzureDataLakeStorage',
                'creationMethod': 'AzureDataLakeStorage',
                'parameters': [ 
                    { 'value': server, 'dataType': 'Text', 'name': 'server' },
                    { 'value': path, 'dataType': 'Text', 'name': 'path' }
                ]
            },
            'credentialDetails': {
                'credentials': {
                    'tenantId': cls.AZURE_TENANT_ID,
                    'servicePrincipalClientId': cls.AZURE_CLIENT_ID,
                    'servicePrincipalSecret': cls.AZURE_CLIENT_SECRET,
                    'credentialType': 'ServicePrincipal'
                },
                'singleSignOnType': 'None',
                'connectionEncryption': 'NotEncrypted',
                'skipTestConnection': 'false'
            }
        }

        return cls.create_connection(create_connection_request)

    @classmethod
    def list_workspace_connections(cls, workspace_id):
        """Get connections associated with a specifc workspace"""
        workspace_connections = []
        connections = cls.list_connections()
        for connection in connections:
            if connection.displayName is not None and workspace_id in connection.displayName:
                workspace_connections.append(connection)
        return workspace_connections

    #endregion
    
    #region folder functions
    
    @classmethod
    def list_folders(cls, workspace_id):
        """List Folder"""
        return cls.fabric_client.core.folders.list_folders(workspace_id=workspace_id)

    @classmethod
    def create_folder(cls, workspace_id, folder_name, paremt_folder_id = None):
        """Create Folder"""

        AppLogger.log_step(f'Creating folder {folder_name}')
        
        create_request = {
            'displayName': folder_name,
            'parentFolderId': paremt_folder_id
         }

        folder = cls.fabric_client.core.folders.create_folder(workspace_id, create_request)
        AppLogger.log_substep(f"folder created with Id [{folder.id}]")
        
        return folder

    #endregion
    
    #region item functions

    @classmethod
    def list_workspace_items(cls, workspace_id, item_type = None):
        """Get items in workspace"""
        return cls.fabric_client.core.items.list_items(workspace_id, type=item_type)

    @classmethod
    def get_item_by_name(cls, workspace_id, display_name, item_type):
        """Get Item by Name"""
        items = cls.list_workspace_items(workspace_id, item_type)
        for item in items:
            if item.display_name == display_name:
                return item
        return None

    @classmethod
    def create_item(cls, workspace_id, create_item_request, folder_id = None):
        """Create Item"""

        AppLogger.log_step(
            f"Creating [{create_item_request['displayName']}.{create_item_request['type']}]...")
        
        if folder_id is not None:
            create_item_request['folderId'] = folder_id
        
        item = cls.fabric_client.core.items.create_item(workspace_id, create_item_request)
        AppLogger.log_substep(f"{item.type} created with id [{item.id}]")

        return item

    @classmethod
    def get_item_definition(cls, workspace_id, item, export_format = None):
        """Get Item Definition"""
        # no ability to pass format parameter
        return cls.fabric_client.core.items.get_item_definition(workspace_id, item.id)

    @classmethod
    def update_item_definition(cls, workspace_id, item, update_item_definition_request):
        """Update Item Definition using update-item--definition-request"""
        return cls.fabric_client.core.items.update_item_definition(
            workspace_id,
            item.id,
            update_item_definition_request
        )

    #endregion

    #region variable library functions

    @classmethod
    def set_active_valueset_for_variable_library(cls, workspace_id, library, valueset):
        """Set active valueset for variable library"""
        
        # leave default settings for dev environment
        if valueset == 'dev':
            return

        AppLogger.log_substep(
            "Setting active valueset for variable library " + \
            f"[{library.display_name}] to [{valueset}]...")

        update_request = {
            'displayName': library.display_name,
            'properties': {                
                'activeValueSetName': valueset
            }
        }
        
        cls.fabric_client.variablelibrary.items.update_variable_library(
            workspace_id=workspace_id,
            variable_library_id=library.id,
            update_variable_library_request=update_request
        )
 
    @classmethod
    def set_active_valueset_for_variable_library_no_sdk(cls, workspace_id, library, valueset):
        """Set active valueset for variable library"""
        if valueset == 'dev':
            valueset = None
            
        AppLogger.log_substep(
            "Setting active valueset for variable library " + \
            f"[{library.display_name}] to [{valueset}]...")

        rest_url = f"workspaces/{workspace_id}/VariableLibraries/{library.id}"
        post_body = {
            'properties': {                
                'activeValueSetName': valueset
            }
        }
        cls._execute_patch_request(rest_url, post_body)
        
 
    #endregion

    #region lakehouse and shortcut functions
 
    @classmethod
    def create_lakehouse(cls, workspace_id, display_name, folder_id = None, enable_schemas = False):
        """Create Lakehouse"""
        create_item_request = {
            'displayName': display_name, 
            'type': 'Lakehouse' 
        }

        if enable_schemas:
            create_item_request['creationPayload'] = { 'enableSchemas': True }
            
        return cls.create_item(workspace_id, create_item_request, folder_id)

    @classmethod
    def get_lakehouse(cls, workspace_id, lakehouse_id):
        """Get lakehouse properties"""
        rest_url = f'workspaces/{workspace_id}/lakehouses/{lakehouse_id}'
        return cls.fabric_client.lakehouse.items.get_lakehouse(
            workspace_id=workspace_id,
            lakehouse_id=lakehouse_id
        )

    @classmethod
    def get_sql_endpoint_for_lakehouse(cls, workspace_id, lakehouse):
        """Get SQL endpoint properties for lakehouse"""

        lakehouse = cls.get_lakehouse(workspace_id, lakehouse.id)
        while lakehouse.properties.sql_endpoint_properties.provisioning_status != 'Success':
            wait_time = 10
            time.sleep(wait_time)
            lakehouse = cls.get_lakehouse(workspace_id, lakehouse.id)

        server = lakehouse.properties.sql_endpoint_properties.connection_string
        database = lakehouse.properties.sql_endpoint_properties.id

        return {
            'server': server,
            'database': database
        }

    @classmethod
    def refresh_sql_endpoint_metadata(cls, workspace_id, sql_endpoint_id):
        """Refresh SL Endpoint"""
        AppLogger.log_substep("Updating SQL Endpoint metadata...")
        cls.fabric_client.sqlendpoint.items.refresh_sql_endpoint_metadata(
                        workspace_id=workspace_id,
                        sql_endpoint_id=sql_endpoint_id,
                        sql_endpoint_refresh_metadata_request={}
                    ).value
            
        AppLogger.log_substep(f"SQL Endpoint metadata refresh job completed successfully")

    @classmethod
    def list_shortcuts(cls, workspace_id, lakehouse_id):
        """List Shortcuts"""
        return cls.fabric_client.core.one_lake_shortcuts.list_shortcuts(workspace_id, lakehouse_id)

    @classmethod
    def create_onelake_shortcut(cls, 
                                workspace_id, 
                                target_lakehouse_id,
                                source_lakehouse_id,
                                name, 
                                path,
                                ):
        """Create ADLS Gen2 Shortcut"""
        AppLogger.log_step('Creating OneLake shortcut using ADLS connection...')
        create_request = {
            'name': name,
            'path': f'/{path}',
            'target': {
                'onelake': {
                    'itemId': source_lakehouse_id,
                    'path': f'{path}/{name}',
                    'workspaceId': workspace_id
                }
            }
        }
        
        cls.fabric_client.core.one_lake_shortcuts.create_shortcut(
            workspace_id, 
            target_lakehouse_id,
            create_request
        )
                
        AppLogger.log_substep(f'Shortcut [{path}/{name}] successfullly created')
       
    @classmethod
    def create_adls_gen2_shortcut(cls, workspace_id, lakehouse_id, name, path,
                                    location, subpath, connection_id):
        """Create ADLS Gen2 Shortcut"""
        AppLogger.log_substep(f'Creating OneLake shortcut [{path}/{name}] using ADLS connection...')
        create_request = {
            'name': name,
            'path': path,
            'target': {
                'adlsGen2': {
                'location': location,
                'subpath': subpath,
                'connectionId': connection_id
                }
            }
        }
        cls.fabric_client.core.one_lake_shortcuts.create_shortcut(
            workspace_id, 
            lakehouse_id,
            create_request,
            shortcut_conflict_policy='CreateOrOverwrite'
        )

    @classmethod
    def reset_adls_gen2_shortcut(cls, workspace_id, lakehouse_id, shortcut):
        """Reset ADLS Gen2 Shortcut"""
        cls.create_adls_gen2_shortcut(
            workspace_id,
            lakehouse_id,
            shortcut.name,
            shortcut.path,
            "$(/**/environment_settings/adls_server)",
            "$(/**/environment_settings/adls_shortcut_subpath)",
            "$(/**/environment_settings/adls_connection_id)"
        )
 
    #endregion

    #region job functions

    @classmethod
    def run_notebook_with_sdk(cls, workspace_id, notebook):
        """Run notebook and wait for job completion"""
        AppLogger.log_substep(f"Running notebook [{notebook.display_name}]...")

        response = cls.fabric_client.core.job_scheduler.run_on_demand_item_job(
            workspace_id=workspace_id,
            item_id=notebook.id,
            job_type='RunNotebook'            
        )

        AppLogger.log_substep("Notebook run job completed successfully")
        return response


    @classmethod
    def run_data_pipeline_with_sdk(cls, workspace_id, pipeline):
        """Run pipeline and wait for job completion"""
        AppLogger.log_substep(f"Running data pipeline [{pipeline.display_name}]...")
        
        response = cls.fabric_client.core.job_scheduler.run_on_demand_item_job(
            workspace_id=workspace_id,
            item_id=pipeline.id,
            job_type='Pipeline'
        )
        
        AppLogger.log_substep("Data pipeline run job completed successfully")
        return response

    #endregion
 
    #region semantic model functions
 
    @classmethod
    def bind_semantic_model_to_connection(cls, workspace_id, semantic_model_id, connection_id):
        """Bind semantic model to connection"""
        # Fabric REST API does not yet support binding semantic models to connections, so using Power BI REST API for this operation
        PowerBiRestApi.bind_semantic_model_to_connection(workspace_id, semantic_model_id, connection_id)

    @classmethod
    def refresh_semantic_model(cls, workspace_id, semantic_model_id):
        """Refresh semantic model"""
        # Fabric REST API does not yet support refreshing semantic models, so using Power BI REST API for this operation
        PowerBiRestApi.refresh_semantic_model(workspace_id, semantic_model_id)

    @classmethod
    def list_datasources_for_semantic_model(cls, workspace_id, semantic_model_id):
        """Get Datasource for semantic model using Power BI REST API"""
        # Fabric REST API does not yet support listing datasources for semantic models, so using Power BI REST API for this operation
        return PowerBiRestApi.list_datasources_for_semantic_model(workspace_id, semantic_model_id)

    @classmethod
    def get_sql_endpoint_from_semantic_model(cls, workspace_id, semantic_model_id):
        """Get Web datasource URL from semantic model"""
        data_sources = cls.list_datasources_for_semantic_model(workspace_id, semantic_model_id)
        for data_source in data_sources:
            if data_source['datasourceType'] == 'Sql':
                return data_source['connectionDetails']
        return None

    @classmethod
    def create_and_bind_semantic_model_connecton(cls, workspace,
                                                 semantic_model_id, lakehouse = None):
        """Create connection and bind it to semantic model"""
        datasources = PowerBiRestApi.list_datasources_for_semantic_model(workspace.id, semantic_model_id)
        for datasource in datasources:

            if datasource['datasourceType'].lower() == 'sql':
                AppLogger.log_substep('Creating SQL connection for semantic model')
                server = datasource['connectionDetails']['server']
                database = datasource['connectionDetails']['database']
                connection = cls.create_sql_connection_with_service_principal(server,
                                                                              database,
                                                                              workspace,
                                                                              lakehouse)
                AppLogger.log_substep('Binding semantic model to SQL connection')
                cls.bind_semantic_model_to_connection(workspace.id,
                                                        semantic_model_id,
                                                        connection.id)

            elif datasource['datasourceType'].lower() == 'web':
                AppLogger.log_substep('Creating Web connection for semantic model')
                web_url    = datasource['connectionDetails']['url']
                connection = cls.create_anonymous_web_connection(web_url)
                AppLogger.log_substep('Binding semantic model to Web connection')
                cls.bind_semantic_model_to_connection(workspace.id,
                                                        semantic_model_id,
                                                         connection.id)
                cls.refresh_semantic_model(workspace.id, semantic_model_id)

            elif datasource['datasourceType'] == 'AzureDataLakeStorage':
                AppLogger.log_substep('Creating AzureDataLakeStorage connection for semantic model')
                server    = datasource['connectionDetails']['server']
                path      = datasource['connectionDetails']['path']
                connection = cls.create_azure_storage_connection_with_sas_token(server, path)
                AppLogger.log_substep('Binding semantic model to OneLake connection')
                cls.bind_semantic_model_to_connection(workspace.id, semantic_model_id, connection.id)
                cls.refresh_semantic_model(workspace.id, semantic_model_id)

    #endregion
    
    #region deployment pipelines
          
    @classmethod
    def list_deployment_pipelines(cls):
        """Get all deployment pipelines accessible to caller"""
        return cls.fabric_client.core.deployment_pipelines.list_deployment_pipelines()

    @classmethod
    def get_deployment_pipeline_by_name(cls, display_name):
        """Get Deployment Pipeline item by display name"""
        pipelines = cls.list_deployment_pipelines()
        for pipeline in pipelines:
            if pipeline.display_name == display_name:
                return pipeline
        return None

    @classmethod
    def list_deployment_pipeline_stages(cls, pipeline_id):
        """List all deployment pipeline stages"""
        return cls.fabric_client.core.deployment_pipelines.list_deployment_pipeline_stages(pipeline_id)

    @classmethod
    def delete_deployment_pipeline(cls, pipeline_id):
        """Delete Deployment Pipeline"""
        cls.fabric_client.core.deployment_pipelines.delete_deployment_pipeline(pipeline_id)

    @classmethod
    def display_deployment_pipelines(cls):
        """Display Deployment Pipeline"""
        AppLogger.log_step('Deployment Pipelines:')
        pipelines = cls.list_deployment_pipelines()
        for pipeline in pipelines:
            AppLogger.log_substep(f"{pipeline.id} - {pipeline.display_name}")

    @classmethod
    def create_deployment_pipeline(cls, display_name, stages):
        """Create Deployment Pipeline"""
        AppLogger.log_step(f'Creating Deployment Pipeline [{display_name}]')
        pipeline_stages = []
        for stage in stages:
            pipeline_stages.append({
                'displayName': stage,
                'description': f'stage for {stage}',
                'isPublic': False
            })
        create_request = {
            'displayName': display_name,
            'description': 'great example',
            'stages': pipeline_stages
        }
        
        pipeline = cls.fabric_client.core.deployment_pipelines.create_deployment_pipeline(create_request)
        
        AppLogger.log_substep(f"Pipeline create with id [{pipeline.id}]")

        AppLogger.log_substep('Adding deployment pipeline role of [Admin] for admin user')
        cls.add_deployment_pipeline_role_assignment(pipeline.id,
                                                    cls.ADMIN_USER_ID,
                                                    'User',
                                                    'Admin')

        return pipeline

    @classmethod
    def add_deployment_pipeline_role_assignment(cls, pipeline_id, principal_id, principal_type, role):
        """Add Deployment Pipeline Role Assignment"""
        add_request = {
            'principal': {
                'id': principal_id,
                'type': principal_type
            },
            'role': role
        }
        return cls.fabric_client.core.deployment_pipelines.add_deployment_pipeline_role_assignment(
            pipeline_id, 
            add_request
        )

    @classmethod
    def assign_workpace_to_pipeline_stage(cls, workspace_id, pipeline_id, stage_id):
        """Assign workspace to pipeline stage """
        assign_request = { 'workspaceId': workspace_id }
        cls.fabric_client.core.deployment_pipelines.assign_workspace_to_stage(
            pipeline_id,
            stage_id,
            assign_request
        )

    @classmethod
    def unassign_workpace_from_pipeline_stage(cls, pipeline_id, stage_id):
        """Assign workspace to pipeline stage"""
        cls.fabric_client.core.deployment_pipelines.unassign_workspace_from_stage(
            pipeline_id,
            stage_id
        )

    @classmethod
    def deploy_to_pipeline_stage_with_sdk(cls, pipeline_id, source_stage_id, target_stage_id,    note = None):
        """Deploy to pipeline stage"""
        deploy_request = {
            'sourceStageId': source_stage_id,
            'targetStageId': target_stage_id
        }
        if note is not None:
            deploy_request['note'] = note
        else:
            deploy_request['note'] = 'A bunch of saves'

        cls.fabric_client.core.deploymentpipelines.deploy_stage_content(
            pipeline_id,
            deploy_request
        )

    @classmethod
    def deploy_to_pipeline_stage(cls, pipeline_id, source_stage_id, target_stage_id,    note = None):
        """Deploy to pipeline stage"""
        endpoint = f'deploymentPipelines/{pipeline_id}/deploy'
        deploy_request = {
            'sourceStageId': source_stage_id,
            'targetStageId': target_stage_id
        }
        if note is not None:
            deploy_request['note'] = note
        else:
            deploy_request['note'] = 'Demo of automating deployment using APIs'


        cls._execute_post_request(endpoint, deploy_request)
    
    #endregion
    
    #region generic Git integration functions

    @classmethod
    def initialize_git_connection(cls, workspace_id, initialize_connection_request):
        """Initialize GIT Connection"""
        return cls.fabric_client.core.git.initialize_connection(
            workspace_id=workspace_id,
            git_initialize_connection_request=initialize_connection_request            
        )

    @classmethod
    def get_git_status(cls, workspace_id):
        """Get GIT Connection Status"""
        return cls.fabric_client.core.git.get_status(workspace_id=workspace_id)

    @classmethod
    def get_git_connection(cls, workspace_id):
        """Get GIT Connection"""
        return cls.fabric_client.core.git.get_connection(workspace_id=workspace_id)

    @classmethod
    def disconnect_workspace_from_git(cls, workspace_id):
        """Disconnect Workspace from GIT Repository"""
        return cls.fabric_client.core.git.disconnect(workspace_id)

    @classmethod
    def commit_workspace_to_git(cls, workspace_id, commit_to_git_request = None, commit_comment = "commit workspace changes back to repo"):
        """Commit Workspace to GIT Repository"""
          
        AppLogger.log_substep("Committing Workspace content to GIT repository")
                
        if commit_to_git_request is None:
            currest_status = cls.get_git_status(workspace_id)
            changes = currest_status.changes
            if len(changes) == 0:
                AppLogger.log_substep("There are no changes to push")
                return None
            commit_to_git_request = {
                    'mode': 'All',
                    'workspaceHead': currest_status.workspace_head,
                    'remoteCommitHash': currest_status.remote_commit_hash,
                    'comment': commit_comment
            }
            
        cls.fabric_client.core.git.commit_to_git(
            workspace_id, 
            commit_to_git_request)
        
        AppLogger.log_substep('GIT sync process completed successfully')

    @classmethod
    def update_workspace_from_git(cls, workspace_id, update_from_git_request = None):
        """Update Workspace from GIT Repository"""
        
        AppLogger.log_substep("Updating workspace items from item definition in GIT")
        
        if update_from_git_request is None:            
            git_status = FabricRestApi.get_git_status(workspace_id)
            update_from_git_request = {
                "workspaceHead": git_status.workspace_head,
                "remoteCommitHash": git_status.remote_commit_hash,
                "conflictResolution": {
                    "conflictResolutionType": "Workspace",
                    "conflictResolutionPolicy": "PreferRemote"
                },
                "options": { "allowOverrideItems": True }                
            }
                    
        cls.fabric_client.core.git.update_from_git(workspace_id, update_from_git_request)
        AppLogger.log_substep("GIT synchronization process complete")

    @classmethod
    def get_my_git_credentials(cls, workspace_id):
        """Get My GIT Credential"""
        return cls.fabric_client.core.git.get_my_git_credentials(workspace_id)

    @classmethod
    def update_my_git_credentials(cls, workspace_id, update_git_credentials_request):
        """Update My GIT Credentials"""
        endpoint = f"workspaces/{workspace_id}/git/myGitCredentials"
        return cls.fabric_client.core.git.update_my_git_credentials(
            workspace_id,
            update_git_credentials_request
        )    
    
    #endregion
   
    #region GitHub specific functionality

    @classmethod
    def _create_github_source_control_connection(cls, url):
        """Create GitHub connections with Personal Access Token"""

        display_name = f"GIT-GitHub-PAT-[{url}]"

        create_connection_request = {
            'displayName': display_name,
            'connectivityType': 'ShareableCloud',
            'privacyLevel': 'Organizational',
            'connectionDetails': {
                'type': 'GitHubSourceControl',
                'creationMethod': 'GitHubSourceControl.Contents',
                'parameters': [ 
                    { 'name': 'url', 'dataType': 'Text', 'value': url }
                ]
            },
            'credentialDetails': {
                'credentials': {
                    'key': EnvironmentSettings.PERSONAL_ACCESS_TOKEN_GITHUB,
                    'credentialType': 'Key'
                },
                'singleSignOnType': 'None',
                'connectionEncryption': 'NotEncrypted',
                'skipTestConnection': 'false'
            }
        }

        return cls.create_connection(create_connection_request)

    @classmethod
    def _get_github_source_control_connection(cls, repo_name):
        """Get GitHub Repo Connection"""
        
        github_org = EnvironmentSettings.ORGANIZATION_GITHUB

        github_repo_url = f'https://github.com/{github_org}/{repo_name}'

        connections = FabricRestApi.list_connections()

        for connection in connections:
            if connection.connection_details.type == 'GitHubSourceControl' and \
                connection.connection_details.path == github_repo_url:
                return connection

        return cls._create_github_source_control_connection(github_repo_url)
    
    @classmethod
    def _create_workspace_connection_to_github_repo(cls, workspace_id, repo_name, connection_id, branch = 'main'):
        """Connect Workspace to GIT Repository"""
        endpoint = f"workspaces/{workspace_id}/git/connect"

        connect_request = {
            "gitProviderDetails": {
                "ownerName": EnvironmentSettings.ORGANIZATION_GITHUB,
                "gitProviderType": "GitHub",
                "repositoryName": repo_name,
                "branchName": branch,
                "directoryName": "/workspace"
            },
            "myGitCredentials": {
                "source": "ConfiguredConnection",
                "connectionId": connection_id            
            }
        }

        return cls._execute_post_request(endpoint, connect_request)

    @classmethod
    def connect_workspace_to_github_repo(cls, workspace, repo_name, branch = 'main'):
        """Connect Workspace to GitHub Repository"""

        AppLogger.log_substep(f"Connecting workspace[{workspace.display_name}] " + \
                              f"to branch[{branch}] in GitHub repository [{repo_name}]")

        connection = cls._get_github_source_control_connection(repo_name)
        connection_id = connection.id

        cls._create_workspace_connection_to_github_repo(workspace.id, repo_name, connection_id, branch)

        AppLogger.log_substep("Workspace connection created successfully")


        init_request = {
            'initializationStrategy': 'PreferWorkspace'
        }

        init_response = cls.initialize_git_connection(workspace.id, init_request)

        required_action = init_response.required_action
        if required_action == 'CommitToGit':
            commit_to_git_request = {
                'mode': 'All',
                'workspaceHead': init_response.workspace_head,
                'comment': 'Initial commit'
            }
            cls.commit_workspace_to_git(
                workspace.id, 
                commit_to_git_request, 
                'Initial commt from workspace')

        if required_action == 'UpdateFromGit':
            update_from_git_request = {
                "workspaceHead": init_response.workspace_head,
                "remoteCommitHash": init_response.remote_commit_hash,
                "conflictResolution": {
                    "conflictResolutionType": "Workspace",
                    "conflictResolutionPolicy": "PreferWorkspace"
                },
                "options": {
                    "allowOverrideItems": True
                }
                            
            }
            cls.update_workspace_from_git(workspace.id, update_from_git_request)

        AppLogger.log_substep("Workspace connection successfully created and synchronized")


    #endregion

    #region  direct calls to Fabric REST API for gaps and bugs where the SDK does not work
    
    @classmethod
    def run_notebook(cls, workspace_id, notebook):
        """Run notebook and wait for job completion"""
        AppLogger.log_substep(f"Running notebook [{notebook.display_name}]...")
        rest_url = f"workspaces/{workspace_id}/items/{notebook.id}" + \
                    "/jobs/instances?jobType=RunNotebook"
        response = cls._execute_post_request_for_job_scheduler(rest_url)
        AppLogger.log_substep("Notebook run job completed successfully")
        return response

    @classmethod
    def run_data_pipeline(cls, workspace_id, pipeline):
        """Run notebook and wait for job completion"""
        AppLogger.log_substep(f"Running data pipeline [{pipeline.display_name}]...")

        rest_url = f"workspaces/{workspace_id}/items/{pipeline.id}" + \
                    "/jobs/instances?jobType=Pipeline"
        response = cls._execute_post_request_for_job_scheduler(rest_url)
        AppLogger.log_substep("Data pipeline run job completed successfully")
        return response

    @classmethod
    def refresh_sql_endpoint_metadata_no_sdk(cls, workspace_id, sql_endpoint_id):
        """Refresh SL Endpoint"""
        AppLogger.log_substep("Updating SQL Endpoint metadata (NO SDK)...")
        endpoint = \
            f"workspaces/{workspace_id}/sqlEndpoints/{sql_endpoint_id}/refreshMetadata?preview=True"
        cls._execute_post_request(endpoint, {})        

    @classmethod
    def _execute_post_request(cls, endpoint, post_body=''):
        """Execute POST request with support for Long-running Operations (LRO)"""
        rest_url = 'https://api.fabric.microsoft.com/v1/' + endpoint        
        fabric_rest_api_scope = 'https://api.fabric.microsoft.com/.default'
        access_token = cls.credential.get_token(fabric_rest_api_scope).token
        request_headers = {'Content-Type':'application/json',
                             'Authorization': f'Bearer {access_token}'}

        response = requests.post(url=rest_url, json=post_body, headers=request_headers, timeout=60)

        if response.status_code in { 200, 201, 204 }:
            try:
                return response.json()
            except JSONDecodeError:
                return None

        if response.status_code == 202:
            operation_state_url = response.headers.get('Location')
            wait_time = 10 # int(response.headers.get('Retry-After'))
            time.sleep(wait_time)
            response = requests.get(url=operation_state_url, headers=request_headers, timeout=60)
            operation_state = response.json()
            while operation_state['status'] != 'Succeeded' and \
                    operation_state['status'] != 'Failed':
                time.sleep(wait_time)
                response = requests.get(url=operation_state_url,
                                        headers=request_headers,
                                        timeout=60)
                operation_state = response.json()

            if operation_state['status'] == 'Succeeded':
                if 'Location' in response.headers:
                    operation_result_url = response.headers.get('Location')
                    response = requests.get(url=operation_result_url,
                                            headers=request_headers,
                                            timeout=60)
                    if response.status_code == 200:
                        return response.json()
                    else:
                        AppLogger.log_error(f"Error - {response.status_code}")
                        return None
                else:
                    return None
            else:
                AppLogger.log_error(f"Error - {operation_state}")

        elif response.status_code == 429: # handle TOO MANY REQUESTS error
            wait_time = int(response.headers.get('Retry-After'))
            time.sleep(wait_time)
            return cls._execute_post_request(endpoint, post_body)
     
        elif response.status_code == 404: # handle NOT FOUND error
            AppLogger.log_substep('Received 404 NOT FOUND error - waiting 10 seconds and retrying')
            wait_time = 10
            time.sleep(wait_time)
            return cls._execute_post_request(endpoint, post_body)
        
        else:
            AppLogger.log_error(
                f'Error executing POST request: {response.status_code} - {response.text}')
            raise RuntimeError(f'Error executing POST request: {response.status_code} - {response.text}')

    @classmethod
    def _execute_patch_request(cls, endpoint, post_body):
        """Execute GET Request on Fabric REST API Endpoint"""
        rest_url = 'https://api.fabric.microsoft.com/v1/' + endpoint        
        fabric_rest_api_scope = 'https://api.fabric.microsoft.com/.default'
        access_token = cls.credential.get_token(fabric_rest_api_scope).token
        request_headers = {'Content-Type':'application/json',
                           'Authorization': f'Bearer {access_token}'}
        response = requests.patch(url=rest_url, json=post_body, headers=request_headers, timeout=60)
        if response.status_code in {200, 204}:
            return response.json()

        if response.status_code == 429: # handle TOO MANY REQUESTS error
            wait_time = int(response.headers.get('Retry-After'))
            time.sleep(wait_time)
            return cls._execute_patch_request(endpoint, post_body)
        else:
            AppLogger.log_error(
                f'Error executing PATCH request: {response.status_code} - {response.text}')
            return None




    @classmethod
    def _execute_post_request_for_job_scheduler(cls, endpoint, post_body=''):
        """Execute POST request with support for Om-demand Job with Job Scheduler"""
        rest_url = 'https://api.fabric.microsoft.com/v1/' + endpoint        
        fabric_rest_api_scope = 'https://api.fabric.microsoft.com/.default'
        access_token = cls.credential.get_token(fabric_rest_api_scope).token
        request_headers = {'Content-Type':'application/json',
                             'Authorization': f'Bearer {access_token}'}
        response = requests.post(url=rest_url, headers=request_headers, json=post_body, timeout=60)

        if response.status_code == 202:
            operation_state_url = response.headers.get('Location')
            wait_time = 10 # int(response.headers.get('Retry-After'))
            time.sleep(wait_time)
            response = requests.get(url=operation_state_url, headers=request_headers, timeout=60)
            operation_state = response.json()
            while operation_state['status'] == 'NotStarted' or \
                    operation_state['status'] == 'InProgress' or \
                    (operation_state['status'] == 'Failed' and \
                     operation_state['failureReason']['errorCode'] == 'RequestExecutionFailed'    ):
                time.sleep(wait_time)
                response = requests.get(url=operation_state_url,
                                        headers=request_headers,
                                        timeout=60)
                operation_state = response.json()

            if operation_state['status'] == 'Completed':
                return

            if operation_state['status'] == 'Failed':
                AppLogger.log_error('On-demand job Failed')
                print('----------------------------')
                print(operation_state)
                print('----------------------------')
                print(response)
                print('----------------------------')
                raise RuntimeError('On-demand job started but Failed')

            if operation_state['status'] == 'Cancelled':
                AppLogger.log_error('On-demand job was cancelled')

            if operation_state['status'] == 'Deduped':
                AppLogger.log_error('On-demand job was depuped')

        elif response.status_code == 429: # handle TOO MANY REQUESTS error
            wait_time = int(response.headers.get('Retry-After'))
            time.sleep(wait_time)
            cls._execute_post_request_for_job_scheduler(endpoint, post_body)
        else:
            AppLogger.log_error(
                f'Error executing POST request: {response.status_code} - {response.text}')

    #endregion

class PowerBiRestApi:
    """Power BI REST API Wrapper Class used for operations not yet supported by Fabric REST API"""

    # used for creating DefaultAzureCredential connections with SPN creds
    AZURE_TENANT_ID = os.getenv('AZURE_TENANT_ID')
    AZURE_CLIENT_ID = os.getenv('AZURE_CLIENT_ID')
    AZURE_CLIENT_SECRET = os.getenv('AZURE_CLIENT_SECRET')
    
    credential = DefaultAzureCredential()
    fabric_client = FabricClient(credential)
    
    powerbi_rest_api_scope = 'https://api.fabric.microsoft.com/.default'
    powerbi_rest_api_base_url = 'https://api.powerbi.com/v1.0/myorg/'
    
    @classmethod
    def _execute_get_request_to_powerbi(cls, endpoint):
        """Execute GET Request on Power BI REST API Endpoint"""
        rest_url = cls.powerbi_rest_api_base_url + endpoint
        scope = cls.powerbi_rest_api_scope
        access_token = cls.credential.get_token(scope).token
        request_headers = {'Content-Type':'application/json',
                             'Authorization': f'Bearer {access_token}'}
        response = requests.get(url=rest_url, headers=request_headers, timeout=60)
        if response.status_code in { 200, 202 }:
            return response.json()
        elif response.status_code == 429: # handle TOO MANY REQUESTS error
            wait_time = int(response.headers.get('Retry-After'))
            AppLogger.log_substep(f'Waiting {wait_time} seconds due to 429 TOO MANY REQUESTS error')
            time.sleep(wait_time)
            return cls._execute_get_request_to_powerbi(endpoint)
        else:
            AppLogger.log_error(
                f'Error executing GET request: {response.status_code} - {response.text}')
            return None

    @classmethod
    def _execute_post_request_to_powerbi(cls, endpoint, post_body=''):
        rest_url = cls.powerbi_rest_api_base_url + endpoint
        scope = cls.powerbi_rest_api_scope
        access_token = cls.credential.get_token(scope).token
        request_headers = {'Content-Type':'application/json',
                             'Authorization': f'Bearer {access_token}'}
        response = requests.post(url=rest_url, headers=request_headers, json=post_body, timeout=60)
        return response

    @classmethod
    def list_datasources_for_semantic_model(cls, workspace_id, semantic_model_id):
        """Get Datasource for semantic model using Power BI REST API"""
        rest_url    = f'groups//{workspace_id}//datasets//{semantic_model_id}//datasources'
        return cls._execute_get_request_to_powerbi(rest_url)['value']

    @classmethod
    def get_web_url_from_semantic_model(cls, workspace_id, semantic_model_id):
        """Get Web datasource URL from semantic model"""
        data_sources = cls.list_datasources_for_semantic_model(workspace_id, semantic_model_id)
        for data_source in data_sources:
            if data_source['datasourceType'] == 'Web':
                return data_source['connectionDetails']['url']

    @classmethod
    def bind_semantic_model_to_connection(cls, workspace_id, semantic_model_id, connection_id):
        """Bind semantic model to connection"""
        rest_url    = f'groups//{workspace_id}//datasets//{semantic_model_id}//Default.BindToGateway'
        post_body    = {
            'gatewayObjectId': '00000000-0000-0000-0000-000000000000',
            'datasourceObjectIds': [ connection_id ]
        }
        cls._execute_post_request_to_powerbi(rest_url, post_body)

    @classmethod
    def refresh_semantic_model(cls, workspace_id, semantic_model_id):
        """Refresh semantic model"""
        AppLogger.log_substep('Refreshing semantic model...')
        rest_url    = f'groups//{workspace_id}//datasets//{semantic_model_id}//refreshes'
        post_body = { 'notifyOption': 'NoNotification', 'type': 'Automatic' }
        response = cls._execute_post_request_to_powerbi(rest_url, post_body)
        refresh_id = response.headers.get('x-ms-request-id')
        rest_url_refresh_details = \
            f'groups/{workspace_id}/datasets/{semantic_model_id}/refreshes/{refresh_id}'
        refresh_details = cls._execute_get_request_to_powerbi(rest_url_refresh_details)

        while 'status' not in refresh_details or refresh_details == 'Unknown':
            time.sleep(6)
            refresh_details = cls._execute_get_request_to_powerbi(rest_url_refresh_details)

        AppLogger.log_substep("Refresh operation complete")
        
class Variable:
    """Variable in Variable Library"""
    name: str
    value: str
    type: str
    note: str

    def __init__(self, name: str, value: str, variable_type: str = 'String', note: str = '') -> None:
        self.name = name
        self.value = value
        self.type = variable_type
        self.note = note

    def encode(self):
        """encode support"""
        return self.__dict__

class VariableOverride:
    """Variable in Variable Library"""
    name: str
    value: str

    def __init__(self, name: str, value: str) -> None:
        self.name = name
        self.value = value

    def encode(self):
        """encode support"""
        return self.__dict__

class Valueset:
    """Variable Library"""
    variableOverrides: List[VariableOverride]

    def __init__(self, name):
        self.name = name
        self.variableOverrides = []

    def encode(self):
        """encode support"""
        return self.__dict__
    
    def add_variable_override(self, name: str, value: str):
        """"add variable"""
        self.variableOverrides.append( VariableOverride(name, value) )

class VariableLibrary:
    """Variable Library"""
    variables: List[Variable]
    valuesets: List[Valueset]

    def __init__(self, variables = None, valuesets = None):
        self.variables = variables if variables is not None else []
        self.valuesets = valuesets if valuesets is not None else []

    def encode(self):
        """encode support"""
        return self.__dict__

    def add_variable(self, name: str, value: str, variable_type: str = 'String', note: str = 'some note'):
        """"add variable"""
        self.variables.append( Variable(name, value, variable_type, note) )

    def add_valueset(self, valueset: Valueset):
        """"add valueset"""
        self.valuesets.append( valueset )


    def get_variable_json(self):
        "Get JSON for variables.json"
        variable_lib = {
            '$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/variableLibrary/definition/variables/1.0.0/schema.json',
            'variables': self.variables
        }
        return json.dumps(variable_lib, default=lambda o: o.encode(), indent=4)

    def get_valueset_json(self, valueset_name):
        """Get JSON for valueset.json"""
        valueset_list = list(filter(lambda valueset: valueset.name == valueset_name, self.valuesets))
        valueset: Valueset = valueset_list[0]
               
        valueset_export = {
            '$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/variableLibrary/definition/valueSet/1.0.0/schema.json',
            'name': valueset.name,
            'variableOverrides': valueset.variableOverrides
        }
        return json.dumps(valueset_export, default=lambda o: o.encode(), indent=4)

class ItemDefinitionFactory:
    """Logic to to create and update item definitions"""

    @classmethod
    def _create_inline_base64_part(cls, path, payload):
        """create item definition part with base64 encoding"""
        return {
            'path': path,
            'payload': base64.b64encode(payload.encode('utf-8')).decode('utf-8'),
            'payloadType': 'InlineBase64'
        }

    @classmethod
    def _get_part_path(cls, item_folder_path, file_path):
        """get path for item definition part"""
        offset = file_path.find(item_folder_path) + len(item_folder_path) + 1
        return file_path[offset:].replace('\\', '/')

    @classmethod
    def _search_and_replace_in_payload(cls, payload, search_replace_text):
        payload_bytes = base64.b64decode(payload)
        payload_content = payload_bytes.decode('utf-8')
        for entry in search_replace_text.keys():
            payload_content = payload_content.replace(entry, search_replace_text[entry])
        return base64.b64encode(payload_content.encode('utf-8')).decode('utf-8')

    @classmethod
    def _search_and_replace_in_payload_with_regex(cls, payload, search_replace_terms):
        payload_bytes = base64.b64decode(payload)
        payload_content = payload_bytes.decode('utf-8')

        for search, replace in search_replace_terms.items():
            payload_content, count = re.subn(search, replace, payload_content)

        return base64.b64encode(payload_content.encode('utf-8')).decode('utf-8')

    @classmethod
    def get_template_file(cls, path):
        """get contents of a file from templates folder"""
        file_path = f".//templates//ItemDefinitionTemplateFiles//{path}"
        file = open(file_path,'r', encoding="utf-8")
        file_content = file.read()
        file.close()
        return file_content

    @classmethod
    def get_create_item_request_from_folder(cls, item_folder):
        """generate create item request from folder"""
        folder_path = f".//templates//ItemDefinitionTemplateFolders//{item_folder}"
        platform_file_path = f'{folder_path}//.platform'
        file = open(platform_file_path,'r', encoding="utf-8")
        file_content = json.loads(file.read())
        file.close()
        item_type = file_content['metadata']['type']
        item_display_name = file_content['metadata']['displayName']

        item_definition_parts = []

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                part_path = cls._get_part_path(item_folder, file_path)
                file = open(file_path,'r', encoding="utf-8")
                part_content = file.read()
                item_definition_parts.append(cls._create_inline_base64_part(part_path, part_content))

        return {
            'displayName': item_display_name,
            'type': item_type,
            'definition': {
                'parts': item_definition_parts
            }

        }

    @classmethod
    def update_item_definition_part(cls, item_definition, part_path, search_replace_text):
        """Update Item Definition Part"""
        item_part = next((part for part in item_definition['parts'] if part['path'] == part_path), None)
        if item_part is not None:
            item_definition['parts'].remove(item_part)
            item_part['payload'] = cls._search_and_replace_in_payload(item_part['payload'], search_replace_text)
            item_definition['parts'].append(item_part)
        return item_definition

    @classmethod
    def update_item_definition_part_with_regex(cls, item_definition, part_path, search_replace_terms):
        """Update Item Definition Part"""
        item_part = next((part for part in item_definition['parts'] if part['path'] == part_path), None)
        if item_part is not None:
            item_definition['parts'].remove(item_part)
            item_part['payload'] = cls._search_and_replace_in_payload_with_regex(item_part['payload'], search_replace_terms)
            item_definition['parts'].append(item_part)
        return item_definition

    @classmethod
    def update_part_in_create_request(cls, create_item_request, part_path, search_replace_text):
        """Update Item Definition Part"""
        item_definition = create_item_request['definition']
        item_part = next((part for part in item_definition['parts'] if part['path'] == part_path), None)
        if item_part is not None:
            item_definition['parts'].remove(item_part)
            item_part['payload'] = cls._search_and_replace_in_payload(item_part['payload'], search_replace_text)
            item_definition['parts'].append(item_part)
        
        return {
            'displayName': create_item_request['displayName'],
            'type': create_item_request['type'],
            'definition': item_definition
        }

    @classmethod
    def get_notebook_create_request(cls, workspace_id, lakehouse, display_name, py_file):
        """Create Item Definition for a Notebook"""
        py_content = cls.get_template_file(f"Notebooks//{py_file}")
        py_content = py_content.replace('{WORKSPACE_ID}', workspace_id) \
                             .replace('{LAKEHOUSE_ID}', lakehouse.id) \
                             .replace('{LAKEHOUSE_NAME}', lakehouse.display_name)

        item_part = cls._create_inline_base64_part('notebook-content.py', py_content)
        item_definition = {
            'parts': [ item_part ]
        }

        return {
            'displayName': display_name,
            'type': 'Notebook',
            'definition': item_definition
        }

    @classmethod
    def get_semantic_model_create_request(cls, display_name, bim_file):
        """Create semantic model create request from BIM file"""
        pbism_content = cls.get_template_file("SemanticModels//definition.pbism")
        bim_content  = cls.get_template_file(f'SemanticModels//{bim_file}')

        return {
            'displayName': display_name,
            'type': "SemanticModel",
            'definition': {
                'parts': [
                    cls._create_inline_base64_part('definition.pbism', pbism_content),
                    cls._create_inline_base64_part('model.bim', bim_content)
                ]
            }
        }

    @classmethod
    def get_semantic_model_create_request_from_definition(cls, display_name, bim_definition):
        """Create semantic model create request from BIM file"""
        pbism_content = cls.get_template_file("SemanticModels//definition.pbism")

        return {
            'displayName': display_name,
            'type': "SemanticModel",
            'definition': {
                'parts': [
                    cls._create_inline_base64_part('definition.pbism', pbism_content),
                    cls._create_inline_base64_part('model.bim', bim_definition)
                ]
            }
        }

    @classmethod
    def get_directlake_model_create_request(cls, display_name, bim_file, server, database):
        """Get Create Request for DirectLake Semantic Model"""

        pbism_content = cls.get_template_file("SemanticModels//definition.pbism")
        bim_template  = cls.get_template_file(f'SemanticModels//{bim_file}')

        bim_content = bim_template.replace('abc-xyz.datawarehouse.fabric.microsoft.com', server) \
                                  .replace('{SQL_ENDPOINT_DATABASE}', database)

        return {
            'displayName': display_name,
            'type': "SemanticModel",
            'definition': {
                'parts': [
                    cls._create_inline_base64_part('definition.pbism', pbism_content),
                    cls._create_inline_base64_part('model.bim', bim_content)
                ]
            }
        }

    @classmethod
    def get_report_create_request(cls, semantic_model_id, display_name, report_json_file):
        """Get Create Request for Report using Report.json file"""

        pbir_content = \
            cls.get_template_file("Reports//definition.pbir").replace('{SEMANTIC_MODEL_ID}',
                                                                      semantic_model_id)

        report_json_content  = cls.get_template_file(f'Reports//{report_json_file}')
        theme_file_content = \
            cls.get_template_file(
                "Reports//StaticResources//SharedResources//BaseThemes//CY24SU02.json")
        return {
            'displayName': display_name,
            'type': "Report",
            'definition': {
                'parts': [
                    cls._create_inline_base64_part('definition.pbir', pbir_content),
                    cls._create_inline_base64_part('report.json', report_json_content),
                    cls._create_inline_base64_part(
                        'StaticResources/SharedResources/BaseThemes/CY24SU02.json', 
                        theme_file_content )
                ]
            }
        }

    @classmethod
    def update_report_definition_with_semantic_model_id(cls, item_definition, target_model_id):
        """Update Item Definition Part"""
        item_part = next((part for part in item_definition['parts'] if part['path'] == 'definition.pbir'), None)
        if item_part is not None:
            item_definition['parts'].remove(item_part)
            file_template = cls.get_template_file(r"Reports//definition.pbir")
            file_content = file_template.replace('{SEMANTIC_MODEL_ID}', target_model_id)
            item_part = cls._create_inline_base64_part('definition.pbir', file_content)
            item_definition['parts'].append(item_part)

        return item_definition

    @classmethod
    def update_create_report_request_with_semantic_model(cls, create_report_request, target_model_id):
        """Update Item Definition Part"""
        item_definition = create_report_request['definition']
        item_part = next((part for part in item_definition['parts'] if part['path'] == 'definition.pbir'), None)
        if item_part is not None:
            item_definition['parts'].remove(item_part)
            file_template = cls.get_template_file(r"Reports//definition.pbir")
            file_content = file_template.replace('{SEMANTIC_MODEL_ID}', target_model_id)
            item_part = cls._create_inline_base64_part('definition.pbir', file_content)
            item_definition['parts'].append(item_part)

        return {
            'displayName': create_report_request['displayName'],
            'type': "Report",
            'definition': item_definition
        }

    @classmethod
    def update_create_pbir_report_request_with_semantic_model(cls, create_report_request, target_model_id):
        """Update Item Definition Part"""
        item_definition = create_report_request['definition']
        item_part = next((part for part in item_definition['parts'] if part['path'] == 'definition.pbir'), None)
        if item_part is not None:
            item_definition['parts'].remove(item_part)
            file_template = cls.get_template_file(r"Reports//definition_pbir.pbir")
            file_content = file_template.replace('{SEMANTIC_MODEL_ID}', target_model_id)
            item_part = cls._create_inline_base64_part('definition.pbir', file_content)
            item_definition['parts'].append(item_part)

        return {
            'displayName': create_report_request['displayName'],
            'type': "Report",
            'definition': item_definition
        }

    @classmethod
    def get_data_pipeline_create_request(cls, display_name, pipeline_definition):
        """Get Create Request for Data Pipeline using pipeline-content.json file"""
        return {
            'displayName': display_name,
            'type': "DataPipeline",
            'definition': {
                'parts': [
                    cls._create_inline_base64_part('pipeline-content.json', pipeline_definition),
                ]
            }
        }
 
    @classmethod
    def get_variable_library_create_request(cls, display_name, variable_library: VariableLibrary):
        """Get Create Request for Variable Library file"""

        variables_json = variable_library.get_variable_json()

        parts = [
            cls._create_inline_base64_part('variables.json', variables_json)
        ]

        for valueset in variable_library.valuesets:
            path = f"valueSets/{valueset.name}.json"
            content = variable_library.get_valueset_json(valueset.name)
            parts.append( cls._create_inline_base64_part(path, content ) )


        settings_json = cls.get_template_file("VariableLibraries//settings.json")
        parts.append( cls._create_inline_base64_part('settings.json', settings_json ) )

        return {
            'displayName': display_name,
            'type': "VariableLibrary",
            'definition': {
                'parts': parts
            }
        }

    @classmethod
    def get_variable_library_update_request(cls, variable_library: VariableLibrary):
        """Get Create Request for Variable Library file"""

        variables_json = variable_library.get_variable_json()

        parts = [
            cls._create_inline_base64_part('variables.json', variables_json)
        ]

        for valueset in variable_library.valuesets:
            path = f"valueSets/{valueset.name}.json"
            content = variable_library.get_valueset_json(valueset.name)
            parts.append( cls._create_inline_base64_part(path, content ) )


        settings_json = cls.get_template_file("VariableLibraries//settings.json")
        parts.append( cls._create_inline_base64_part('settings.json', settings_json ) )

        return {
            'definition': {
                'parts': parts
            }
        }

class DeploymentManager:
    """Deployment Manager"""

    @classmethod
    def update_source_lakehouse_in_notebook(cls,
                workspace_name,
                notebook_name,
                lakehouse_name):
        """Update datasource path in notebook"""
        workspace = FabricRestApi.get_workspace_by_name(workspace_name)
        notebook = FabricRestApi.get_item_by_name(workspace.id, notebook_name, 'Notebook')
        lakehouse = FabricRestApi.get_item_by_name(workspace.id, lakehouse_name, "Lakehouse")

        workspace_id = workspace.id
        lakehouse_id = lakehouse.id

        search_replace_terms = {
            r'("default_lakehouse"\s*:\s*)".*"': rf'\1"{lakehouse_id}"',
            r'("default_lakehouse_name"\s*:\s*)".*"': rf'\1"{lakehouse_name}"',
            r'("default_lakehouse_workspace_id"\s*:\s*)".*"': rf'\1"{workspace_id}"',
            r'("known_lakehouses"\s*:\s*)\[[\s\S]*?\]': rf'\1[{{"id": "{lakehouse_id}"}}]',
        }

        notebook_definition = FabricRestApi.get_item_definition(workspace.id, notebook).as_dict()

        notebook_definition = {
            'definition': ItemDefinitionFactory.update_item_definition_part_with_regex(
                notebook_definition['definition'],
                'notebook-content.py',
                search_replace_terms)
        }

        FabricRestApi.update_item_definition(workspace.id, notebook, notebook_definition)

    @classmethod
    def update_imported_semantic_model_source(cls, workspace,
                                                semantic_model_name, 
                                                web_datasource_path):
        """Update Imported Sementic Model Source"""
        model = FabricRestApi.get_item_by_name(workspace.id, semantic_model_name, 'SemanticModel')
        old_web_datasource_path = PowerBiRestApi.get_web_url_from_semantic_model(workspace.id, model.id) + '/'

        if web_datasource_path == old_web_datasource_path:
            AppLogger.log_substep(f"Verified web datasource path: [{web_datasource_path}]")
        else:
            old_model_definition = FabricRestApi.get_item_definition(workspace.id, model).as_dict()
    
            search_replace_terms = {
                old_web_datasource_path: web_datasource_path
            }

            model_definition = {
                'definition': ItemDefinitionFactory.update_item_definition_part(
                    old_model_definition['definition'],
                    'definition/expressions.tmdl',
                    search_replace_terms)
            }

            FabricRestApi.update_item_definition(workspace.id, model, model_definition)

    @classmethod
    def update_directlake_semantic_model_source(cls,
                                                workspace_name,
                                                semantic_model_name,
                                                lakehouse_name):
        """Update DirectLake Sementic Model Source"""
        workspace = FabricRestApi.get_workspace_by_name(workspace_name)
        lakehouse = FabricRestApi.get_item_by_name(workspace.id, lakehouse_name, 'Lakehouse')
        model = FabricRestApi.get_item_by_name(workspace.id, semantic_model_name, 'SemanticModel')
        
        old_sql_endpoint =    FabricRestApi.get_sql_endpoint_from_semantic_model(
            workspace.id,
            model.id
        )

        new_sql_endpoint = FabricRestApi.get_sql_endpoint_for_lakehouse(
            workspace.id,
            lakehouse)

        old_model_definition = FabricRestApi.get_item_definition(workspace.id, model).as_dict()

        search_replace_terms = {
            old_sql_endpoint['server']: new_sql_endpoint['server']
        }

        AppLogger.log_substep(f"Connect string: [{new_sql_endpoint['server']}]")
        
        model_definition = {
            'definition': ItemDefinitionFactory.update_item_definition_part(
                old_model_definition['definition'],
                'definition/expressions.tmdl',
                search_replace_terms)
        }

        FabricRestApi.update_item_definition(workspace.id, model, model_definition)

    @classmethod
    def create_and_bind_model_connection(cls, workspace_name):
        """Create and Bind Model Connections"""
        workspace = FabricRestApi.get_workspace_by_name(workspace_name)
        model_name = 'Product Sales DirectLake Model'
        model = FabricRestApi.get_item_by_name(workspace.id, model_name, 'SemanticModel')
        FabricRestApi.create_and_bind_semantic_model_connecton(workspace, model.id)

    @classmethod
    def apply_post_sync_fixes(cls, workspace_id, deploy_job):

        """Apply Post Sync Fixes"""
        workspace = FabricRestApi.get_workspace_info(workspace_id)
        workspace_name = workspace.display_name
        AppLogger.log_step(f"Applying post sync fixes to [{workspace.display_name}]")
        
        workspace_items = list(FabricRestApi.list_workspace_items(workspace.id))

        notebooks = list(filter(lambda item: item.type=='Notebook', workspace_items))
        for notebook in notebooks:
            
            # bind notebooks to sales lakehouse
            if notebook.display_name in [
                'Create Lakehouse Tables', 
                'Build 01 Silver Layer',
                'Build 02 Gold Layer',
                'Create 01 Silver Layer',
                'Create 02 Gold Layer',
                'Build 02 Gold Tables']:
                AppLogger.log_substep(f"Updating notebook[{notebook.display_name}]")
                cls.update_source_lakehouse_in_notebook(
                    workspace_name,
                    notebook.display_name,
                    "sales")

            # bind notebooks to sales_silver lakehouse
            if notebook.display_name in ['Build 01 Silver Tables']:
                AppLogger.log_substep(f"Updating notebook[{notebook.display_name}]")
                cls.update_source_lakehouse_in_notebook(
                    workspace_name,
                    notebook.display_name,
                    "sales_silver")

        models = list(filter(lambda item: item.type=='SemanticModel', workspace_items))
        for model in models:
             
            if model.display_name == 'Product Sales Imported Model':
                web_datasource_path = deploy_job['parameters']['web_datasource_path']
                DeploymentManager.update_imported_semantic_model_source(
                    workspace,
                    model.display_name,
                    web_datasource_path)

            if model.display_name == 'Product Sales DirectLake Model':
                AppLogger.log_substep(f"Updating semantic model[{model.display_name}]")
                # patch connection string to lakehouse SQL endpoint
                target_lakehouse_name = 'sales'
                DeploymentManager.update_directlake_semantic_model_source(
                    workspace_name,
                    model.display_name,
                    target_lakehouse_name)

    @classmethod
    def apply_post_deploy_fixes(cls, workspace_id):        
        """Apply Post Deploy Fixes"""

        workspace = FabricRestApi.get_workspace_info(workspace_id)
        workspace_name = workspace.display_name                         
        workspace_items = list(FabricRestApi.list_workspace_items(workspace.id))
       
        AppLogger.log_step(f"Applying post deploy fixes to [{workspace_name}]")
        
        notebooks = list(filter(lambda item: item.type == 'Notebook', workspace_items))        
        for notebook in notebooks:
            if 'Create' in notebook.display_name:
                FabricRestApi.run_notebook(workspace.id, notebook)
    
        pipelines  = list(filter(lambda item: item.type == 'DataPipeline', workspace_items))
        for pipeline in pipelines:
            if 'Create' in pipeline.display_name:
                FabricRestApi.run_data_pipeline(workspace.id, pipeline)

        sql_endpoints = list(filter(lambda item: item.type == 'SQLEndpoint', workspace_items))
        for sql_endpoint in sql_endpoints:
            FabricRestApi.refresh_sql_endpoint_metadata(
                workspace.id,
                sql_endpoint.id)

        models = list(filter(lambda item: item.type == 'SemanticModel', workspace_items))
        for model in models:
            FabricRestApi.create_and_bind_semantic_model_connecton(
                workspace,
                model.id,
                FabricRestApi.get_item_by_name(workspace.id, 'sales', 'Lakehouse'))

    @classmethod
    def run_data_pipeline(cls, workspace_name, data_pipeline_name):
        """Run data pipeline"""
        workspace = FabricRestApi.get_workspace_by_name(workspace_name)
        data_pipeline_name = 'Create Lakehouse Tables'
        data_pipeline = FabricRestApi.get_item_by_name(
            workspace.id,
            data_pipeline_name,
            'DataPipeline')

        FabricRestApi.run_data_pipeline(workspace.id, data_pipeline)

    @classmethod
    def get_sql_endpoint_info_by_name(cls, workspace_name, lakehouse_name):
        """Get SQL Endpoint"""
        workspace = FabricRestApi.get_workspace_by_name(workspace_name)
        lakehouse = FabricRestApi.get_item_by_name(workspace.id, 
                                                     lakehouse_name, 'Lakehouse')
        
        return FabricRestApi.get_sql_endpoint_for_lakehouse(workspace.id, lakehouse)

    @classmethod
    def create_feature_workspace_in_github(cls, repo_name, feature_name, base_branch):
        """Create feature workspace from new GitHub branch"""

        feature_workspace_name = F'{repo_name}-dev-{feature_name}'
        feature_workspace = FabricRestApi.create_workspace(feature_workspace_name)
        
        feature_branch_name = f'dev-{feature_name}'
        GitHubRestApi.create_branch(repo_name, feature_branch_name, base_branch)

        FabricRestApi.connect_workspace_to_github_repo(
            feature_workspace,
            repo_name,
            feature_branch_name
        )

        DeploymentManager.apply_post_sync_fixes(
            feature_workspace.id,
            EnvironmentSettings.DEPLOYMENT_JOBS['dev']
        )

        DeploymentManager.apply_post_deploy_fixes(feature_workspace.id)

        FabricRestApi.commit_workspace_to_git(feature_workspace.id)

        return feature_workspace

