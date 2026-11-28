# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "environment": {
# META       "environmentId": "7039e59a-8767-87c1-48a3-19c22464f63f",
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
