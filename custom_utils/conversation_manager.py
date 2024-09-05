import logging
import json
import litellm
import os
from tools.tools_list import *
from litellm.types.utils import ChatCompletionMessageToolCall, Function


class ConversationManager:
    def __init__(self, state):
        self.conversation_state = state
        self.model_to_use = os.getenv('llm_model_to_use')
        self.api_key = os.getenv('llm_api_key')
        self.llm_api_base = os.getenv('llm_api_base')
        self.llm_api_version = os.getenv('llm_api_version')

    def add_user_msg(self, user_msg):
        self.conversation_state['messages'].append({"role": "user", "content": user_msg})
        logging.info(f'added user msg {user_msg}')

    def add_assistant_msg(self, assistant_msg):
        self.conversation_state['messages'].append({
            "role": "assistant", 
            "content": assistant_msg['content'], 
            "tool_calls": assistant_msg.get('tool_calls', []), 
            "function_call": assistant_msg.get('function_call', None)
        })
        logging.info(f'added asst msg {assistant_msg}')

    def call_llm(self, conversation_list, chosen_tools_list):
        # logging.info(f'last msg in the list is : {conversation_list[-1]}')
        logging.info('this is what we sending to an llm : ')
        logging.info(conversation_list)
        response = litellm.completion(
            model=self.model_to_use,
            messages=conversation_list,
            tools=chosen_tools_list,
            tool_choice="auto",
            api_key=self.api_key,
            api_base=self.llm_api_base,
            api_version=self.llm_api_version
        )
        self.add_assistant_msg(response.choices[0].message)
        self.conversation_state['conversation_cost'] = "{:.8f}".format(response._hidden_params["response_cost"])
        return response

    def add_tool_msg(self, tool_call, function_name, function_response):
        self.conversation_state['messages'].append({
            "tool_call_id": tool_call.id,
            "role": "tool",
            "name": function_name,
            "content": function_response,
        })
        logging.info(f'added tool msg {tool_call.id}')

    def process_tool_use(self, tool_calls):
        for tool_call in tool_calls:
            logging.info(f'calling {tool_call}')
            function_name = tool_call.function.name
            function_to_call = globals().get(function_name)

            if function_to_call is None:
                function_response = "Wrong function name"
                self.add_tool_msg(tool_call, function_name, function_response)
                return function_response

            try:
                function_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as e:
                function_response = f"Invalid function arguments: {e}"
                self.add_tool_msg(tool_call, function_name, function_response)
                return function_response

            try:
                function_response = function_to_call(**function_args)
            except TypeError as e:
                function_response = f"Wrong parameters provided: {e}"
                self.add_tool_msg(tool_call, function_name, function_response)
                return function_response
            except Exception as e:
                function_response = f"An error occurred in the function: {e}"
                self.add_tool_msg(tool_call, function_name, function_response)
                return function_response
            self.add_tool_msg(tool_call, function_name, function_response)
        
        return function_response  # outside of loop !!
