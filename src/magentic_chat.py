# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from semantic_kernel.agents import Agent, AgentGroupChat

from data_models.app_context import AppContext


def convert_tools(agent: Agent):
    tools = []
    for plugin in agent.kernel.plugins.values():
        for function in plugin.functions.values():
            tools.append(function.method)

    return tools


def create_magentic_chat(chat: AgentGroupChat, app_context: AppContext, input_func) -> MagenticOneGroupChat:
    agent_config = app_context.all_agent_configs
    is_groq = bool(os.getenv("GROQ_API_KEY"))
    is_gemini = bool(os.getenv("GEMINI_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))

    if is_gemini or is_groq or has_openai:
        from autogen_ext.models.openai import OpenAIChatCompletionClient
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        if is_gemini:
            base_url = os.getenv("OPENAI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai/"
            model = os.getenv("OPENAI_MODEL_ID", "gemini-2.5-flash")
        elif is_groq:
            base_url = os.getenv("OPENAI_BASE_URL") or "https://api.groq.com/openai/v1"
            model = os.getenv("OPENAI_MODEL_ID", "openai/gpt-oss-120b")
        else:
            base_url = os.getenv("OPENAI_BASE_URL")
            model = os.getenv("OPENAI_MODEL_ID", "gpt-4o")

        kwargs = {"model": model, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        az_model_client = OpenAIChatCompletionClient(**kwargs)
    else:
        az_model_client = AzureOpenAIChatCompletionClient(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            api_version="2025-04-01-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_ad_token_provider=app_context.cognitive_services_token_provider if hasattr(app_context, "cognitive_services_token_provider") else None,
        )

    assistants = [
        AssistantAgent(agent.name, model_client=az_model_client, tools=convert_tools(agent),
                       system_message=agent.instructions, description=next((
                           config["description"]
                           for config in agent_config if agent.name == config["name"]
                       ), agent.name))
        for agent in chat.agents
    ]

    user_proxy = UserProxyAgent(name="user",
                                description="The user. As a last resort, when all else has been tried, we can ask the user for information.", input_func=input_func)
    assistants.append(
        user_proxy
    )

    team = MagenticOneGroupChat(assistants, model_client=az_model_client, max_turns=50)
    return team
