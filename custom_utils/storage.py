import os
from botbuilder.azure import BlobStorage, BlobStorageSettings

BLOB_CONNECTION_STRING = os.getenv('BLOB_CONNECTION_STRING')
BLOB_CONTAINER_NAME = os.getenv('BLOB_CONTAINER_NAME')

blob_settings = BlobStorageSettings(
    connection_string=BLOB_CONNECTION_STRING,
    container_name=BLOB_CONTAINER_NAME
)
storage = BlobStorage(blob_settings)


# Function to read from storage
async def read_storage(conversation_id):
    return await storage.read([conversation_id])

# Function to write to storage
async def write_storage(conversation_id, conversation_state):
    return await storage.write({conversation_id: conversation_state})