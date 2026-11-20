# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# CELL ********************

from azure.identity import ClientSecretCredential
from notebookutils import credentials

def get_fabric_access_token():    
    return notebookutils.credentials.getToken('pbi')
    
def get_fabric_access_token_for_spn():

    vault_url = "https://fabricdevopssecrets.vault.azure.net/"

    tenant_id = credentials.getSecret(vault_url, "tenant-id")
    client_id = credentials.getSecret(vault_url, "client-id")
    client_secret = credentials.getSecret(vault_url, "client-secret")

    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )

    # Request an access token for a scope
    scope = "https://api.fabric.microsoft.com/.default"
    token_info = credential.get_token(scope)
    return token_info.token


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import requests
import time

FABRIC_REST_API_BASE_URL = 'https://api.fabric.microsoft.com/v1/'

def execute_fabric_get_request(endpoint):
    """Execute GET Request on Fabric REST API Endpoint"""
    rest_url = FABRIC_REST_API_BASE_URL + endpoint
    access_token = get_fabric_access_token()
    request_headers = {'Content-Type':'application/json',
                       'Authorization': f'Bearer {access_token}'}
    response = requests.get(url=rest_url, headers=request_headers, timeout=60)
    if response.status_code == 200:
        return response.json()
    if response.status_code == 429: # handle TOO MANY REQUESTS error
        wait_time = int(response.headers.get('Retry-After'))
        print(f'Waiting {wait_time} seconds due to 429 TOO MANY REQUESTS error')
        time.sleep(wait_time)
        return cls._execute_get_request(endpoint)
    else:
        print(f'Error executing GET request: {response.status_code} - {response.text}')
        return None

def execute_fabic_post_request(endpoint, post_body=''):
    """Execute POST request with support for Long-running Operations (LRO)"""
    rest_url = FABRIC_REST_API_BASE_URL + endpoint
    access_token = get_fabric_access_token()
    request_headers = {'Content-Type':'application/json',
                            'Authorization': f'Bearer {access_token}'}

    print(f'Executing POST to {rest_url}')
    response = requests.post(url=rest_url, json=post_body, headers=request_headers, timeout=60)

    if response.status_code in { 200, 201, 204 }:
        try:
            return response.json()
        except JSONDecodeError:
            return None

    if response.status_code == 202:
        print("async operation stated")
        operation_state_url = response.headers.get('Location')
        wait_time = 10 # int(response.headers.get('Retry-After'))
        time.sleep(wait_time)
        response = requests.get(url=operation_state_url, headers=request_headers, timeout=60)
        operation_state = response.json()
        while operation_state['status'] != 'Succeeded' and \
                operation_state['status'] != 'Failed':
            print(f'status: {operation_state['status']}')
            time.sleep(wait_time)
            response = requests.get(url=operation_state_url,
                                    headers=request_headers,
                                    timeout=60)
            operation_state = response.json()
            
        print(f'status: {operation_state['status']}')

        if operation_state['status'] == 'Succeeded':
            if 'Location' in response.headers:
                operation_result_url = response.headers.get('Location')
                response = requests.get(url=operation_result_url,
                                        headers=request_headers,
                                        timeout=60)
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Error - {response.status_code}")
                    return None
            else:
                return None
        else:
            print(f"Error - {operation_state}")

    elif response.status_code == 429: # handle TOO MANY REQUESTS error
        wait_time = int(response.headers.get('Retry-After'))
        time.sleep(wait_time)
        return execute_fabic_post_request(endpoint, post_body)
    
    elif response.status_code == 404: # handle NOT FOUND error
        print('Received 404 NOT FOUND error - waiting 10 seconds and retrying')
        wait_time = 10
        time.sleep(wait_time)
        return execute_fabic_post_request(endpoint, post_body)
    
    else:
        print(f'Error executing POST request: {response.status_code} - {response.text}')
        raise RuntimeError(f'Error executing POST request: {response.status_code} - {response.text}')


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

WORKSPACE_ID = notebookutils.runtime.context.get("currentWorkspaceId")

def get_workspace_info():
    """Get Workspace information by ID"""
    return execute_fabric_get_request(f'workspaces/{WORKSPACE_ID}')

def list_workspace_items(item_type = None):
    """Get items in workspace"""
    endpoint = f'workspaces/{WORKSPACE_ID}/items'

    if item_type is not None:
        endpoint = endpoint + f'?type={item_type}'

    return execute_fabric_get_request(endpoint)['value']

def get_item_by_name(display_name, item_type):
    """Get Item by Name"""
    items = list_workspace_items(item_type)
    for item in items:
        if item['displayName'] == display_name:
            return item
    return None


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

def get_environment(env_name):
    environment = get_item_by_name(env_name, "Environment")
    environment_id = environment['id']
    restUrl = f'workspaces/{WORKSPACE_ID}/environments/{environment_id}'
    return execute_fabric_get_request(restUrl)


def publish_environment(env_name):
    """Publish environment"""
    environment = get_item_by_name(env_name, "Environment")
    environment_id = environment['id']
    
    restUrl = f"workspaces/{WORKSPACE_ID}/environments/{environment_id}/staging/publish?beta=false"
    return execute_fabic_post_request(restUrl)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

env_name = "fabric_devops_shared"
publish_environment(env_name)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
