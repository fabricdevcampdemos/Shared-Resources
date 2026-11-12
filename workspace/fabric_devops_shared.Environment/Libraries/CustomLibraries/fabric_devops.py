import json
import logging
import requests
import os
from datetime import datetime, timezone, timedelta
import time
import sys
import base64
import shutil
import re
import msal
import notebookutils

class AppLogger:
  """Provides support for logging into setup_logs lakehouse"""

  LOGGER = None
  LOGGER_NOTEBOOK = None

  @classmethod
  def ensure_logger_setup(cls):
      """ Setup logging """
      current_notebook = notebookutils.runtime.context.get('currentNotebookName')
      if (cls.LOGGER is None) or (cls.LOGGER_NOTEBOOK != current_notebook):
        cls.configure_logger()

  @classmethod
  def configure_logger(cls):
      """ Setup logging """
      cls.LOGGER_NOTEBOOK = notebookutils.runtime.context.get('currentNotebookName')
      formatted_datetime = datetime.now(timezone(timedelta(hours=-5))).strftime('%Y-%m-%d__%H-%M')
      log_folder = "/lakehouse/default/Files/logs/"
      log_file_name = f"{formatted_datetime}__{cls.LOGGER_NOTEBOOK}.log"
      
      os.makedirs(log_folder, exist_ok=True)
      log_path = os.path.join(log_folder, log_file_name)
      
      cls.LOGGER = logging.getLogger('FabricDevOps')
      cls.LOGGER.setLevel(logging.INFO)

      cls.LOGGER.propagate = False  # Prevent propagation to root logger

      # Clear any existing handlers to prevent duplicates on re-execution
      if cls.LOGGER.hasHandlers():
          cls.LOGGER.handlers.clear()

      cls.LOGGER.addHandler(logging.StreamHandler(sys.stdout))
      cls.LOGGER.addHandler(logging.FileHandler(log_path))

      # formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
      formatter = logging.Formatter('%(message)s')
      for handler in cls.LOGGER.handlers:
          handler.setFormatter(formatter)

  @classmethod
  def info(cls, message):
    cls.ensure_logger_setup()
    cls.LOGGER.info(message)
    for handler in cls.LOGGER.handlers:
      handler.flush()

  @classmethod
  def log_step(cls, message):
    cls.info(f'\n> {message}')

  @classmethod
  def log_substep(cls, message):
    cls.info(f' - {message}')

  @classmethod
  def log_json(cls, message):
    cls.info( f'\n{json.dumps(message, indent=4)}\n' )

  @classmethod
  def log_dataframe(cls, df):

    schema_str = df.schema.simpleString()
    cls.log_substep(f'schema: {schema_str}')

    table_string = df._jdf.showString(20, 20, False)
    cls.info(f'\nSample Rows:\n{table_string}')

  @classmethod
  def error(cls, message):
    cls.LOGGER.error(message)

  @classmethod  
  def log_current_context(cls):

   log_start_message = f"\n*** Fabric DevOps deployment job started at {datetime.now(timezone(timedelta(hours=-5))).strftime('%Y-%m-%d-%H:%M')}\n"
   cls.info(log_start_message)
   
   cls.log_step("Logging current notebook context...")
    
   userId = notebookutils.runtime.context.get("userId")
   cls.log_substep(f'userId: {userId}')

   currentNotebookName = notebookutils.runtime.context.get('currentNotebookName')
   cls.log_substep(f'currentNotebookName: {currentNotebookName}')
  
   currentWorkspaceName = notebookutils.runtime.context.get("currentWorkspaceName")
   cls.log_substep(f'currentWorkspaceName: {currentWorkspaceName}')

   currentWorkspaceId = notebookutils.runtime.context.get("currentWorkspaceId")
   cls.log_substep(f'currentWorkspaceId: {currentWorkspaceId}')

  @classmethod  
  def end_logging_session(cls):
    # flush and close handlers for current logging session
    for handler in cls.LOGGER.handlers:
      handler.flush()
      handler.close()
    # reset handlers for next logging session
    cls.LOGGER = None

class TokenManager: 

    CURRENT_USER_ID = notebookutils.runtime.context.get("userId") 
    SPN_USER_ID = 'c7b17a8e-3113-4f27-8b8c-9dc2439bd0a3' 
    
    # use single MSAL app instance across calls for in-memory SPN tokencaching
    _MSAL_APP = None 

    @classmethod 
    def get_fabric_access_token(cls): 
        if cls.CURRENT_USER_ID == cls.SPN_USER_ID: 
            return cls._get_fabric_access_token_for_service_principal() 
        else: 
            return notebookutils.credentials.getToken("pbi") 

    @classmethod 
    def _get_fabric_access_token_for_service_principal(cls): 
        spn_scopes = ['https://api.fabric.microsoft.com/.default'] 
        
        # 1. Initialize the MSAL app instance only once to preserve the cache across executions
        if cls._MSAL_APP is None:
            AppLogger.log_step('Aquiring access token for SPN...')
            vault_url = "https://fabricdevopssecrets.vault.azure.net/" 
            tenant_id = notebookutils.credentials.getSecret(vault_url, 'tenant-id') 
            client_id = notebookutils.credentials.getSecret(vault_url, 'client-id') 
            client_secret = notebookutils.credentials.getSecret(vault_url, 'client-secret') 
            
            cls._MSAL_APP = msal.ConfidentialClientApplication( 
                client_id, 
                authority = f'https://login.microsoftonline.com/{tenant_id}', 
                client_credential = client_secret 
            ) 
        
        authentication_result = cls._MSAL_APP.acquire_token_for_client(
          scopes=spn_scopes
        )

        if "access_token" not in authentication_result:
            logging.error(
              f"Token acquisition failed: {authentication_result.get('error')} - "
              f"{authentication_result.get('error_description')}"
            )
            raise RuntimeError(
                f"Token acquisition failed: {authentication_result.get('error')} - "
                f"{authentication_result.get('error_description')}"
            )

        return authentication_result["access_token"]

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
    def update_item_definition_part(cls, item_definition, part_path, search_replace_text):
        """Update Item Definition Part"""
        item_part = next((part for part in item_definition['parts'] if part['path'] == part_path), None)
        if item_part is not None:
            item_definition['parts'].remove(item_part)
            item_part['payload'] = cls._search_and_replace_in_payload(item_part['payload'], search_replace_text)
            item_definition['parts'].append(item_part)
        return item_definition


class FabricRestApi:
    """Wrapper class for Fabric REST API"""

    FABRIC_REST_API_BASE_URL = 'https://api.fabric.microsoft.com/v1/'

    CURRENT_WORKSPACE_NAME = notebookutils.runtime.context.get("currentWorkspaceName")
    CURRENT_WORKSPACE_ID = notebookutils.runtime.context.get("currentWorkspaceId")
    CURRENT_NOTEBOOK_ID = notebookutils.runtime.context.get("currentNotebookId")
    DEFAULT_LAKEHOUSE_NAME = notebookutils.runtime.context.get("defaultLakehouseName")
    DEFAULT_LAKEHOUSE_ID = notebookutils.runtime.context.get("defaultLakehouseId")

    WORKSPACE_ADMIN_GROUP = "e4ff16d1-b3b1-4c33-b091-ff9a4b4172d6"
 
    @classmethod
    def _get_fabric_access_token(cls):
        return TokenManager.get_fabric_access_token()

    @classmethod
    def _execute_get_request(cls, endpoint):
        """Execute GET Request on Fabric REST API Endpoint"""
        rest_url = cls.FABRIC_REST_API_BASE_URL + endpoint
        access_token = cls._get_fabric_access_token()
        request_headers = {'Content-Type':'application/json',
                           'Authorization': f'Bearer {access_token}'}
        response = requests.get(url=rest_url, headers=request_headers, timeout=60)
        if response.status_code == 200:
            return response.json()
        if response.status_code == 429: # handle TOO MANY REQUESTS error
            wait_time = int(response.headers.get('Retry-After'))
            AppLogger.log_substep(f'Waiting {wait_time} seconds due to 429 TOO MANY REQUESTS error')
            time.sleep(wait_time)
            return cls._execute_get_request(endpoint)
        else:
            logging.error(f'Error executing GET request: {response.status_code} - {response.text}')
            return None

    @classmethod
    def _execute_post_request(cls, endpoint, post_body=''):
        """Execute POST request with support for Long-running Operations (LRO)"""
        rest_url = cls.FABRIC_REST_API_BASE_URL + endpoint
        access_token = cls._get_fabric_access_token()
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
                logging.error(f"Error - {operation_state}")

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
            logging.error(
                f'Error executing POST request: {response.status_code} - {response.text}')
            raise RuntimeError(f'Error executing POST request: {response.status_code} - {response.text}')

    @classmethod
    def _execute_patch_request(cls, endpoint, post_body):
        """Execute GET Request on Fabric REST API Endpoint"""
        
        rest_url = cls.FABRIC_REST_API_BASE_URL + endpoint
        access_token = cls._get_fabric_access_token()
        request_headers = {
          'Content-Type':'application/json',
          'Authorization': f'Bearer {access_token}'
        }

        response = requests.patch(url=rest_url, json=post_body, headers=request_headers, timeout=60)
        
        if response.status_code in {200, 204}:
            return response.json()

        if response.status_code == 429: # handle TOO MANY REQUESTS error
            wait_time = int(response.headers.get('Retry-After'))
            time.sleep(wait_time)
            return cls._execute_patch_request(endpoint, post_body)
        else:
            AppLogger.error(
                f'Error executing PATCH request: {response.status_code} - {response.text}')
            return None

    @classmethod
    def list_workspaces(cls):
        """ List Workpaces """
        return cls._execute_get_request('workspaces')

    @classmethod
    def get_workspace_info(cls):
        """Get Workspace information by ID"""
        return cls._execute_get_request(f'workspaces/{cls.CURRENT_WORKSPACE_ID}')

    @classmethod
    def add_workspace_user(cls, user_id, role_assignment):
        """Add workspace role for user"""
        endpoint =    f'workspaces/{cls.CURRENT_WORKSPACE_ID}/roleAssignments'
        post_body = {
            'role': role_assignment,
            'principal': {
            'id': user_id,
            'type': 'User'
            }
        }
        return cls._execute_post_request(endpoint, post_body)

    @classmethod
    def add_workspace_group(cls, group_id, role_assignment):
        """Add workspace role for group"""
        endpoint =    f'workspaces/{cls.CURRENT_WORKSPACE_ID}/roleAssignments'
        post_body = {
            'role': role_assignment,
            'principal': {
            'id': group_id,
            'type': 'Group'
            }
        }
        return cls._execute_post_request(endpoint, post_body)

    @classmethod
    def add_workspace_spn(cls, spn_id, role_assignment):
        """Add workspace role for user"""
        endpoint =    f'workspaces/{cls.CURRENT_WORKSPACE_ID}/roleAssignments'
        post_body = {
            'role': role_assignment,
            'principal': {
            'id': spn_id,
            'type': 'ServicePrincipal'
            }
        }
        return cls._execute_post_request(endpoint, post_body)

    @classmethod
    def list_workspace_items(cls, item_type = None):
        """Get items in workspace"""
        endpoint = f'workspaces/{cls.CURRENT_WORKSPACE_ID}/items'

        if item_type is not None:
            endpoint = endpoint + f'?type={item_type}'

        return cls._execute_get_request(endpoint)['value']

    @classmethod
    def get_item_by_name(cls, display_name, item_type):
        """Get Item by Name"""
        items = cls.list_workspace_items(item_type)
        for item in items:
            if item['displayName'] == display_name:
                return item
        return None

    @classmethod
    def get_item_definition(cls, item, export_format = None):
        """Get Item Definition"""
        endpoint = f"workspaces/{cls.CURRENT_WORKSPACE_ID}/items/{item['id']}/getDefinition"
        if export_format is not None:
            endpoint = endpoint + f'?format={export_format}'
        return cls._execute_post_request(endpoint)

    @classmethod
    def update_item_definition(cls, item, update_item_definition_request):
        """Update Item Definition using update-item--definition-request"""
        AppLogger.log_substep(
            f"Updating [{item['displayName']}.{item['type']}]...")
        endpoint = f"workspaces/{cls.CURRENT_WORKSPACE_ID}/items/{item['id']}/updateDefinition"
        item = cls._execute_post_request(endpoint, update_item_definition_request)
        return item

    @classmethod
    def provision_workspace_identity(cls, workspace_role = 'Admin'):
        """Provision Workspace Identity"""
        if cls.workspace_has_provisioned_identity():
            AppLogger.log_step('Workspace identity has already been provisioned')
            return

        AppLogger.log_step('Provisioning workspace identity')
        rest_url = f"workspaces/{cls.CURRENT_WORKSPACE_ID}/provisionIdentity"
        workspace_identity = cls._execute_post_request(rest_url)
        service_principal_id = workspace_identity['servicePrincipalId']
        AppLogger.log_substep(f'Workspace identity provisioned with service principal id [{service_principal_id}]')
        cls.add_workspace_spn(service_principal_id, workspace_role)
        AppLogger.log_substep(f'Workspace identity added to workspace role of [{workspace_role}]')

    @classmethod
    def workspace_has_provisioned_identity(cls):
        """Check if Workspace has a provisioned identity"""
        workspace_info = cls.get_workspace_info()
        return 'workspaceIdentity' in workspace_info

    @classmethod
    def deprovision_workspace_identity(cls):
        """Deprovision Workspace Identity"""
        if not cls.workspace_has_provisioned_identity():
            AppLogger.log_step('Workspace identity is not currently provisioned')
            return
        AppLogger.log_step('Deprovisioning workspace identity')
        rest_url = f"workspaces/{cls.CURRENT_WORKSPACE_ID}/deprovisionIdentity"
        cls._execute_post_request(rest_url)

    @classmethod
    def list_connections(cls):
        """List all connections accessible to caller"""
        return cls._execute_get_request("connections")['value']

    @classmethod
    def get_connection_by_name(cls, display_name):
        """Get Connection By Name"""
        connections = cls.list_connections()
        for connection in connections:
            if connection['displayName'] == display_name:
                return connection
        return None

    @classmethod
    def create_connection(cls, create_connection_request):
        """ Create new connection"""
        AppLogger.log_step(f"Creating connection with display name [{create_connection_request['displayName']}]")

        existing_connections = cls.list_connections()
        for connection in existing_connections:
            if 'displayName' in connection and \
                connection['displayName'] == create_connection_request['displayName']:
                AppLogger.log_substep(f"Using existing Connection with id [{connection['id']}]")
                return connection

        connection = cls._execute_post_request('connections', create_connection_request)

        AppLogger.log_substep(f"Connection created with id [{connection['id']}]")

        cls.add_connection_role_assignment_for_group(
          connection['id'],
          cls.WORKSPACE_ADMIN_GROUP,
          'Owner')

        return connection

    @classmethod
    def add_connection_role_assignment_for_user(cls, connection_id, admin_user_id, connection_role):
        """Add connection role assignment for user"""
        rest_url = f'connections//{connection_id}//roleAssignments'
        post_body = {
            'principal': {
                'id': admin_user_id,
                'type': "User"
            },
            'role': connection_role
        }
        return cls._execute_post_request(rest_url, post_body)

    @classmethod
    def add_connection_role_assignment_for_group(cls, connection_id, group_id, connection_role):
        """Add connection role assignment for group"""
        rest_url = f'connections//{connection_id}//roleAssignments'
        post_body = {
            'principal': {
                'id': group_id,
                'type': "Group"
            },
            'role': connection_role
        }
        return cls._execute_post_request(rest_url, post_body)

    @classmethod
    def add_connection_role_assignment_for_service_principal(cls, connection_id, spn_object_id, connection_role):
        """Add connection role assignment for service principal"""
        rest_url = f'connections//{connection_id}//roleAssignments'
        post_body = {
            'principal': {
                'id': spn_object_id,
                'type': "ServicePrincipal"
            },
            'role': connection_role
        }
        return cls._execute_post_request(rest_url, post_body)

    @classmethod
    def create_azure_storage_connection_with_sas_token(cls, server, path):
        """Create Azure Storage connections"""
        
        display_name = f"ADLS-SAS-[{server}{path}]"
     
        vault_url = "https://fabricdevopssecrets.vault.azure.net/"
        secret_name = "azure-storage-sas-token"
        sas_token = notebookutils.credentials.getSecret(vault_url, secret_name)
    
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
                    'token': sas_token,
                    'credentialType': 'SharedAccessSignature'
                },
                'singleSignOnType': 'None',
                'connectionEncryption': 'NotEncrypted',
                'skipTestConnection': 'false'
            }
        }

        return cls.create_connection(create_connection_request)

    @classmethod
    def set_active_valueset_for_variable_library(cls, library, valueset):
        """Set active valueset for variable library"""
        if valueset == 'dev':
            valueset = None
            
        AppLogger.log_step(
            "Setting active valueset for variable library " + \
            f"[{library['displayName']}] to [{valueset}]...")

        rest_url = f"workspaces/{cls.CURRENT_WORKSPACE_ID}/VariableLibraries/{library['id']}"
        post_body = {
            'properties': {                
                'activeValueSetName': valueset
            }
        }
        cls._execute_patch_request(rest_url, post_body)    
    
    @classmethod
    def get_lakehouse(cls, lakehouse_id):
        """Get lakehouse properties"""
        rest_url = f'workspaces/{cls.CURRENT_WORKSPACE_ID}/lakehouses/{lakehouse_id}'
        return cls._execute_get_request(rest_url)

    @classmethod
    def get_sql_endpoint_for_lakehouse(cls, lakehouse):
        """Get SQL endpoint properties for lakehouse"""

        lakehouse = cls.get_lakehouse(lakehouse['id'])
        while lakehouse['properties']['sqlEndpointProperties']['provisioningStatus'] != 'Success':
            wait_time = 10
            time.sleep(wait_time)
            lakehouse = cls.get_lakehouse(lakehouse['id'])

        server = lakehouse['properties']['sqlEndpointProperties']['connectionString']
        database = lakehouse['properties']['sqlEndpointProperties']['id']

        return {
            'server': server,
            'database': database
        }

    @classmethod
    def wait_for_lakehouse_provisioning_to_complete(cls, lakehouse):
        """Wait for lakehouse provisioning to complete"""

        AppLogger.log_step(
            f"Waiting for lakehouse[{lakehouse['displayName']}] provisioning to complete...")

        lakehouse = cls.get_lakehouse(lakehouse['id'])
        while lakehouse['properties']['sqlEndpointProperties']['provisioningStatus'] != 'Success':
            AppLogger.log_substep(f"lakehouse provisioning status: [{lakehouse['properties']['sqlEndpointProperties']['provisioningStatus']}]")
            wait_time = 10
            time.sleep(wait_time)
            lakehouse = cls.get_lakehouse(lakehouse['id'])

        server = lakehouse['properties']['sqlEndpointProperties']['connectionString']
        database = lakehouse['properties']['sqlEndpointProperties']['id']

        AppLogger.log_substep(f"lakehouse provisioning complete")
        AppLogger.log_substep(f"SQL endpoint server: {server}")
        AppLogger.log_substep(f"SQL endpoint database: {database}")

    @classmethod
    def create_sql_connection_with_service_principal(cls, server, database, lakehouse = None):
        """Create SQL Connection"""

        if lakehouse is not None:
          display_name = f'SQL-SPN-Workspace[{lakehouse["workspaceId"]}]-Lakehouse[{lakehouse["displayName"]}]'
        else:
          display_name = f'SQL-SPN-[{server}:{database}]'

        vault_url = "https://fabricdevopssecrets.vault.azure.net/" 
        tenant_id = notebookutils.credentials.getSecret(vault_url, 'tenant-id') 
        client_id = notebookutils.credentials.getSecret(vault_url, 'client-id') 
        client_secret = notebookutils.credentials.getSecret(vault_url, 'client-secret') 

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
                    'tenantId': tenant_id,
                    'servicePrincipalClientId': client_id,
                    'servicePrincipalSecret': client_secret,
                    'credentialType': 'ServicePrincipal'
                },
                'singleSignOnType': 'None',
                'connectionEncryption': 'NotEncrypted',
                'skipTestConnection': 'false'
            }
        }

        return cls.create_connection(create_connection_request)

    @classmethod
    def create_sql_connection_with_workspace_identity(cls, server, database, lakehouse = None):
        """Create SQL Connection"""
        
        # provision workspace identity
        cls.provision_workspace_identity()
        
        if lakehouse is not None:
          display_name = f'SQL-WI-Workspace[{lakehouse["workspaceId"]}]-Lakehouse[{lakehouse["displayName"]}]'
        else:
          display_name = f'SQL-WI-[{server}:{database}]'

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
                    'credentialType': 'WorkspaceIdentity'
                },
                'singleSignOnType': 'None',
                'connectionEncryption': 'NotEncrypted',
                'skipTestConnection': 'false'
            }
        }

        return cls.create_connection(create_connection_request)

    @classmethod
    def update_model_with_lakehouse_sql_datasource(cls, model, lakehouse):
      current = PowerBiRestApi.get_sql_dataource_from_semantic_model(model['id'])
      target = cls.get_sql_endpoint_for_lakehouse(lakehouse)
  
      current_model_definition = cls.get_item_definition(model)

      search_replace_terms = {
        current['server']: target['server'],
        current['database']: target['database'] 
      }

      update_request = {
          'definition': ItemDefinitionFactory.update_item_definition_part(
              current_model_definition['definition'],
              'definition/expressions.tmdl',
              search_replace_terms)
      }

      cls.update_item_definition(model, update_request)

class PowerBiRestApi:
    """Power BI REST API Wrapper Class used for operations not yet supported by Fabric REST API"""

    CURRENT_WORKSPACE_ID = notebookutils.runtime.context.get("currentWorkspaceId")
    POWER_BI_RSET_API_ROOT_URL = 'https://api.powerbi.com/v1.0/myorg/'
    
    @classmethod
    def _get_access_token(cls):
        return TokenManager.get_fabric_access_token()

    @classmethod
    def _execute_get_request_to_powerbi(cls, endpoint):
        """Execute GET Request on Power BI REST API Endpoint"""
        rest_url = cls.POWER_BI_RSET_API_ROOT_URL + endpoint
        access_token = cls._get_access_token()
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
            logging.error(
                f'Error executing GET request: {response.status_code} - {response.text}')
            return None

    @classmethod
    def _execute_post_request_to_powerbi(cls, endpoint, post_body=''):
        rest_url = cls.POWER_BI_RSET_API_ROOT_URL + endpoint
        access_token = cls._get_access_token()
        request_headers = {'Content-Type':'application/json',
                             'Authorization': f'Bearer {access_token}'}
        response = requests.post(url=rest_url, headers=request_headers, json=post_body, timeout=60)
        return response

    @classmethod
    def list_datasources_for_semantic_model(cls, semantic_model_id):
        """Get Datasource for semantic model using Power BI REST API"""     
        rest_url    = f'groups//{cls.CURRENT_WORKSPACE_ID}//datasets//{semantic_model_id}//datasources'   
        return cls._execute_get_request_to_powerbi(rest_url)['value']

    @classmethod
    def get_adls_dataource_from_semantic_model(cls, semantic_model_id):
        """Get ADLS datasource from semantic model"""
        AppLogger.log_step(f'Calling list_datasources_for_semantic_model for semantic model {semantic_model_id}')
        data_sources = cls.list_datasources_for_semantic_model(semantic_model_id)
        for datasource in data_sources:                        
            if datasource['datasourceType'] == 'AzureDataLakeStorage':
                server    = f"https://{datasource['connectionDetails']['server']}"
                path      = datasource['connectionDetails']['path']
                return {
                  'server': server,
                  'path': path
                }

    @classmethod
    def get_sql_dataource_from_semantic_model(cls, semantic_model_id):
        """Get SQL datasource from semantic model"""
        data_sources = cls.list_datasources_for_semantic_model(semantic_model_id)
        for datasource in data_sources:                        
            if datasource['datasourceType'] == 'Sql':
                server   = datasource['connectionDetails']['server']
                database = datasource['connectionDetails']['database']
                return {
                  'server': server,
                  'database': database
                }

    @classmethod
    def bind_semantic_model_to_connection(cls, semantic_model_id, connection_id):
        """Bind semantic model to connection"""
        rest_url    = f'groups//{cls.CURRENT_WORKSPACE_ID}//datasets//{semantic_model_id}//Default.BindToGateway'
        post_body    = {
            'gatewayObjectId': '00000000-0000-0000-0000-000000000000',
            'datasourceObjectIds': [ connection_id ]
        }
        cls._execute_post_request_to_powerbi(rest_url, post_body)

    @classmethod
    def refresh_semantic_model(cls, semantic_model_id):
        """Refresh semantic model"""
        AppLogger.log_step('Refreshing semantic model...')
        rest_url    = f'groups//{cls.CURRENT_WORKSPACE_ID}//datasets//{semantic_model_id}//refreshes'
        post_body = { 'notifyOption': 'NoNotification', 'type': 'Automatic' }
        response = cls._execute_post_request_to_powerbi(rest_url, post_body)
        refresh_id = response.headers.get('x-ms-request-id')
        rest_url_refresh_details = \
            f'groups/{cls.CURRENT_WORKSPACE_ID}/datasets/{semantic_model_id}/refreshes/{refresh_id}'
        refresh_details = cls._execute_get_request_to_powerbi(rest_url_refresh_details)

        while 'status' not in refresh_details or refresh_details == 'Unknown':
            time.sleep(6)
            refresh_details = cls._execute_get_request_to_powerbi(rest_url_refresh_details)

        AppLogger.log_substep("Refresh operation complete")

