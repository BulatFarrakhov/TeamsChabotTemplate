import azure.functions as func
import logging
import json
from pprint import pformat
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity, ActivityTypes, Attachment
from custom_utils.shared_data import tables
from litellm.types.utils import ChatCompletionMessageToolCall, Function
from custom_utils.aad_security import * 
from custom_utils.storage import * 
from custom_utils.conversation_manager import * 
from tools.tools_list import *
import os
from dotenv import load_dotenv  

load_dotenv(verbose=True, override=True) 

# model_to_use = os.getenv('llm_model_to_use')
# api_key = os.getenv('llm_api_key')
# llm_api_base = os.getenv('llm_api_base')
# llm_api_version = os.getenv('llm_api_version')

# Setup the adapter
settings = BotFrameworkAdapterSettings(app_id=os.getenv('bot_app_id'), app_password=os.getenv('bot_app_password'))

adapter = BotFrameworkAdapter(settings)

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.function_name(name="first_test_not_route")
@app.route(route="llm_call_test_function_name")
async def process_message(req: func.HttpRequest) -> func.HttpResponse:
    # TODO rewrite into smaller chunks 
    # TODO exception handling 
    try:
        litellm.set_verbose=True
        # os.environ['LITELLM_LOG'] = 'DEBUG'
        # Check for content type and ensure it's JSON
        def check_content_type(req):
            content_type = req.headers.get('Content-Type', '')
            if 'application/json' not in content_type:
                return func.HttpResponse("Invalid Content-Type", status_code=415)
        check_content_type(req)

        # Get JSON body and deserialize into an Activity object
        body = req.get_json()
        activity = Activity.deserialize(body)
        auth_header = req.headers.get("Authorization", "")
        aad_object_id = activity.from_property.aad_object_id
        # security
        access_token = get_access_token()
        if not check_user_in_group(aad_object_id, access_token):
            logging.info('user not allowed')
                        # Send a message to the user indicating they are not authorized
            unauthorized_message = Activity(
                type=ActivityTypes.message,
                text="You are not authorized to use this bot.",
                text_format='markdown'
            )

            return func.HttpResponse("You are not authorized to use this bot.", status_code=403)

        # Asynchronous function to handle the activity received
        async def bot_logic(turn_context):
            if turn_context.activity.type != ActivityTypes.message:
                logging.info("Received a non-message activity type")
                return  # Exit the function early if not a message
            text = turn_context.activity.text
            if text == "reset conversation":

                return     
            conversation_id = str(turn_context.activity.conversation.id)

            # state = await storage.read([conversation_id])
            state = await read_storage(conversation_id)
            # conversation_state = state.get(conversation_id, 
            #                                {"conversation_id": conversation_id, "messages": [], "metadata" : [], "price" : [], "conversation_cost" : None})
            conversation_state = state.get(conversation_id, 
                                           {"conversation_id": conversation_id, "messages": [],"conversation_cost" : None})
            
            conversation_manager = ConversationManager(conversation_state)
            # add_user_msg(text)
            conversation_manager.add_user_msg(text)

            def rehydrate_tool_calls(messages):
                for message in messages:
                    if message.get('tool_calls'):
                        message['tool_calls'] = [
                            ChatCompletionMessageToolCall(
                                function=Function(
                                    name=tool_call['function']['name'],
                                    arguments=json.loads(tool_call['function']['arguments'])
                                ),
                                id=tool_call['id'],
                                type=tool_call['type']
                            )
                            for tool_call in message['tool_calls']
                        ]
                return messages
                        # Rehydrate the tool calls after reading the state
            conversation_state['messages'] = rehydrate_tool_calls(conversation_state['messages'])
            response = conversation_manager.call_llm(conversation_state['messages'], tools_list)  
            
            # response = call_llm(conversation_state['messages'], model_to_use, tools_list)
            initial_message = response.choices[0].message
            logging.info(initial_message)
            if initial_message.get('content'):
                await turn_context.send_activity(Activity(
                    type=ActivityTypes.message,
                    text=initial_message['content'],
                    text_format='markdown' 
                    ))    
                # TODO : write an exception for 400 errors, safety stuff    
            # Process tool calls if they exist and loop through further responses
            tool_calls = getattr(initial_message, 'tool_calls', None)
            while tool_calls:
                logging.info('started a tool call ')
                # process_tool_use(tool_calls)
                conversation_manager.process_tool_use(tool_calls)
                # Call the LLM again after processing tool call
                conversation_state['messages'] = rehydrate_tool_calls(conversation_state['messages']) # maybe not needed
                response = conversation_manager.call_llm(conversation_state['messages'], tools_list)
                initial_message = response.choices[0].message
                # Check for text content and send if available
                if initial_message.get('content'): 
                    await turn_context.send_activity(Activity(
                        type=ActivityTypes.message,
                        text=initial_message['content'],
                        text_format='markdown' 
                        ))
                if 'global_markdown_table' in tables and tables['global_markdown_table']:
                    await turn_context.send_activity(Activity(
                        type=ActivityTypes.message,
                        text=tables['global_markdown_table'],
                        text_format='markdown'
                        ))
                    # global_markdown_table = ''  # Clear the global variable after sending
                    tables['global_markdown_table'] = None
                    
                # Check for more tool calls
                tool_calls = getattr(initial_message, 'tool_calls', None)
                # TODO - we need to make sure its user/assistant or user/assistant/tool/assistant/user
                # we cant save it with user msg last because above breaks - maybe separate for logs ? 
            # await storage.write({conversation_id: conversation_state}) 
            logging.info(f'going to write to storage now. writing this : {conversation_state} ')
            await write_storage(conversation_id, conversation_state)

        # Process the activity
        await adapter.process_activity(activity, auth_header, bot_logic)
        return func.HttpResponse("Message processed", status_code=200)
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return func.HttpResponse(f"Server error: {str(e)}", status_code=500)

