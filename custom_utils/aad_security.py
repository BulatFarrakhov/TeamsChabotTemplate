from azure.identity import ManagedIdentityCredential
from azure.core.credentials import AccessToken
import requests
import os
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
GROUP_ID = os.getenv('ad_group_id')
def get_access_token():
    # Use ManagedIdentityCredential to obtain an access token
    credential = ManagedIdentityCredential()
    token: AccessToken = credential.get_token("https://graph.microsoft.com/.default")
    return token.token

def check_user_in_group(aad_object_id, access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    url = f"{GRAPH_API_ENDPOINT}/groups/{GROUP_ID}/members?$filter=id eq '{aad_object_id}'"
    response = requests.get(url, headers=headers)
    members = response.json().get('value', [])
    return any(member['id'] == aad_object_id for member in members)