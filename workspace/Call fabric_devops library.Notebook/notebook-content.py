# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "environment": {
# META       "environmentId": "bbb36882-9dae-85b7-4325-0c5e52a2123f",
# META       "workspaceId": "00000000-0000-0000-0000-000000000000"
# META     }
# META   }
# META }

# CELL ********************

import json
from fabric_devops import AppLogger, FabricRestApi, PowerBiRestApi

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

items = FabricRestApi.list_workspace_items()

AppLogger.log_step('Items in this workspace')
for item in items:
    AppLogger.log_substep(f'{item['displayName']}.{item['type']}')

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
