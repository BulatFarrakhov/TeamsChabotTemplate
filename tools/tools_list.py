
from dotenv import load_dotenv  
import os
import json
import requests
from atlassian import Jira
from requests.auth import HTTPBasicAuth
import pandas as pd
from custom_utils.shared_data import tables
load_dotenv(verbose=True, override=True) 

username = os.getenv('jirausername')
token = os.getenv('jiratoken')
url = os.getenv('jiraurl')

# Create a Jira instance
jira = Jira(
        url=url,
        username=username,
        password=token
    )

tools_list = []  


# tools calls

def get_boards_data(search_keyword='ALL'):
    boards_data = []
    start_at = 0
    max_results = 50
    is_last = False
    
    while not is_last:
        response = jira.get_all_agile_boards(start=start_at, limit=max_results)
        boards_data.extend(response['values'])
        is_last = response['isLast']
        start_at += max_results
    
    # Check if the search keyword is 'ALL' or a specific term and filter boards accordingly
    if search_keyword == 'ALL':
        filtered_boards_data = [board for board in boards_data if 'Sprint' in board['name']]
    else:
        filtered_boards_data = [board for board in boards_data if 'Sprint' in board['name'] and search_keyword.lower() in board['name'].lower()]
    # print(filtered_boards_data)
    board_ids = [board['id'] for board in filtered_boards_data]
    
    # return board_ids
    return f'Function was successfull. Here is a list of board ids : {board_ids}'

get_board_data_desc = {
    "type": "function",
    "function": {
        "name": "get_boards_data",
        "description": "Fetches Agile board IDs from Jira, filtering by a search keyword if provided. The function retrieves all boards, and you can specify a keyword to filter the results.",
        "parameters": {
            "type": "object",
            "properties": {
                "search_keyword": {
                    "type": "string",
                    "description": "Keyword to filter boards by name (e.g., 'Violet', 'Amber'). Use 'ALL' to retrieve all boards with 'Sprint' in their name."
                }
            },
            "required": ["search_keyword"]
        }
    }
}

tools_list.append(get_board_data_desc)


def unified_fetch_sprint_data(board_ids):

    global global_markdown_table
    global_markdown_table = ''
    # First function logic (fetching velocity and other details)
    velocity_data = []
    for board in board_ids:
        url = f'https://endeavoranalytics.atlassian.net/rest/greenhopper/1.0/rapid/charts/velocity?rapidViewId={board}'
        response = requests.get(url, auth=HTTPBasicAuth(username, token))
        if response.status_code == 200:
            json_data = response.json()
            for sprint in json_data['sprints']:
                velocity_stats = json_data['velocityStatEntries'].get(str(sprint['id']), {})
                sprint_data = {
                    'originBoardId': board,
                    'sprint_id': sprint['id'],
                    'estimated_velocity': velocity_stats.get('estimated', {}).get('text', 'N/A'),
                    'completed_velocity': velocity_stats.get('completed', {}).get('text', 'N/A')
                }
                velocity_data.append(sprint_data)
        else:
            print(f'Failed to retrieve data for board ID {board}: {response.status_code}')
    
    velocity_df = pd.DataFrame(velocity_data)

    # Second function logic (fetching sprints data)
    all_sprints = []
    for board_id in board_ids:
        start_at = 0
        max_results = 50
        is_last = False
        while not is_last:
            response = jira.get_all_sprints_from_board(board_id, start=start_at, limit=max_results)
            filtered_sprints = [sprint for sprint in response['values'] if sprint['originBoardId'] == board_id]
            all_sprints.extend(filtered_sprints)
            is_last = response['isLast']
            start_at += max_results
    
    sprint_df = pd.DataFrame(all_sprints)
    sprint_df['sprint_id'] = sprint_df['id']
    sprint_df['startDate'] = sprint_df['startDate'].str[:10]
    sprint_df['endDate'] = sprint_df['endDate'].str[:10]
    sprint_df['completeDate'] = sprint_df['completeDate'].str[:10]

    # Perform the left join
    final_df = pd.merge(sprint_df, velocity_df, on=['sprint_id', 'originBoardId'], how='left')
    final_df = final_df[['name', 'state', 'startDate','endDate','completeDate','goal','estimated_velocity','completed_velocity']]
    final_df=final_df.fillna('--')
    tables['global_markdown_table'] = final_df.to_markdown(index=False) 
    # global_markdown_table = final_df.to_xml(index=False)

    # return final_df
    return 'The table was shown to the user'

unified_fetch_sprint_data_desc = {
    "type": "function",
    "function": {
        "name": "unified_fetch_sprint_data",
        "description": "Fetches sprint data and velocity metrics from Jira for specified board IDs. This function retrieves sprint details, including start and end dates, goals, and velocity metrics (estimated and completed) for each sprint. The data is merged into a single DataFrame.",
        "parameters": {
            "type": "object",
            "properties": {
                "board_ids": {
                    "type": "array",
                    "items": {
                        "type": "integer",
                        "description": "IDs of the boards to fetch sprint and velocity data from."
                    },
                    "description": "List of board IDs for which to retrieve sprint and velocity data."
                }
            },
            "required": ["board_ids"]
        }
    }
}



tools_list.append(unified_fetch_sprint_data_desc)

