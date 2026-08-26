# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import asyncio
import importlib
import logging
import os
from typing import Any, Awaitable, Callable, Tuple
from typing_extensions import override

from pydantic import BaseModel
from openai import AsyncOpenAI
from semantic_kernel import Kernel
from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.channels.chat_history_channel import ChatHistoryChannel
from semantic_kernel.agents.strategies.selection.kernel_function_selection_strategy import \
    KernelFunctionSelectionStrategy
from semantic_kernel.agents.strategies.termination.kernel_function_termination_strategy import \
    KernelFunctionTerminationStrategy
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import \
    AzureChatPromptExecutionSettings
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.open_ai_prompt_execution_settings import \
    OpenAIChatPromptExecutionSettings
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.connectors.ai.open_ai.services.open_ai_chat_completion import OpenAIChatCompletion
from semantic_kernel.connectors.openapi_plugin import OpenAPIFunctionExecutionParameters
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.history_reducer.chat_history_truncation_reducer import ChatHistoryTruncationReducer
from semantic_kernel.functions.kernel_function_from_prompt import KernelFunctionFromPrompt
from semantic_kernel.kernel import Kernel, KernelArguments
from semantic_kernel.prompt_template.input_variable import InputVariable
from semantic_kernel.prompt_template.prompt_template_config import PromptTemplateConfig

from data_models.app_context import AppContext
from data_models.chat_context import ChatContext
from data_models.plugin_configuration import PluginConfiguration
from healthcare_agents import HealthcareAgent
from healthcare_agents import config as healthcare_agent_config
from utils.logging_http_client import create_logging_http_client
from utils.model_utils import model_supports_temperature

DEFAULT_MODEL_TEMP = 0
DEFAULT_TOOL_TYPE = "function"

logger = logging.getLogger(__name__)


class RateLimitedOpenAIChatCompletion(OpenAIChatCompletion):
    """Subclass of OpenAIChatCompletion that catches 429 rate limit errors and retries with backoff."""

    async def _send_completion_request(self, settings_dict):
        # Stripping 'seed' parameter for Gemini API compatibility as Gemini rejects payload containing 'seed'
        if (os.getenv("GEMINI_API_KEY") or "generativelanguage.googleapis.com" in str(settings_dict)) and "seed" in settings_dict:
            settings_dict.pop("seed", None)

        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                return await super()._send_completion_request(settings_dict)
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "rate limit" in err_str or "tokens per minute" in err_str or "quota" in err_str or "resource_exhausted" in err_str) and attempt < max_attempts - 1:
                    wait_time = 3 * (attempt + 1)
                    logger.warning(f"Rate limit (429) encountered. Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_attempts})")
                    await asyncio.sleep(wait_time)
                else:
                    raise e


class ChatRule(BaseModel):
    verdict: str
    reasoning: str


def create_auth_callback(chat_ctx: ChatContext) -> Callable[..., Awaitable[Any]]:
    """
    Creates an authentication callback for the plugin configuration.

    :param chat_ctx: The chat context to be used in the authentication.
    :return: A callable that returns an authentication token.
    """
    # TODO - get key or secret from Azure Key Vault for OpenAPI services.
    # Send the conversation ID as a header to the OpenAPI service.
    async def auth_callback():
        return {'conversation-id': chat_ctx.conversation_id}
    return auth_callback

# Need to introduce a CustomChatCompletionAgent and a CustomHistoryChannel because of issue https://github.com/microsoft/semantic-kernel/issues/12095


class CustomHistoryChannel(ChatHistoryChannel):
    @override
    async def receive(self, history: list[ChatMessageContent],) -> None:
        await super().receive(history)

        for message in history[:-1]:
            await self.thread.on_new_message(message)


async def create_channel(
    self, chat_history: ChatHistory | None = None, thread_id: str | None = None
) -> CustomHistoryChannel:
    """Create a ChatHistoryChannel.

    Args:
        chat_history: The chat history for the channel. If None, a new ChatHistory instance will be created.
        thread_id: The ID of the thread. If None, a new thread will be created.

    Returns:
        An instance of AgentChannel.
    """
    from semantic_kernel.agents.chat_completion.chat_completion_agent import ChatHistoryAgentThread

    CustomHistoryChannel.model_rebuild()

    thread = ChatHistoryAgentThread(chat_history=chat_history, thread_id=thread_id)

    if thread.id is None:
        await thread.create()

    messages = [message async for message in thread.get_messages()]

    return CustomHistoryChannel(messages=messages, thread=thread)


class CustomChatCompletionAgent(ChatCompletionAgent):
    """Custom ChatCompletionAgent to override the create_channel method."""

    @override
    async def create_channel(
        self, chat_history: ChatHistory | None = None, thread_id: str | None = None
    ) -> CustomHistoryChannel:
        return await create_channel(self, chat_history, thread_id)


def create_group_chat(
    app_ctx: AppContext, chat_ctx: ChatContext, participants: list[dict] = None
) -> Tuple[AgentGroupChat, ChatContext]:
    participant_configs = participants or app_ctx.all_agent_configs
    participant_names = [cfg.get("name") for cfg in participant_configs]
    logger.info(f"Creating group chat with participants: {participant_names}")

    is_groq = bool(os.getenv("GROQ_API_KEY"))
    is_gemini = bool(os.getenv("GEMINI_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_azure = bool(os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_OPENAI_API_KEY"))

    # Remove magentic agent from the list of agents. In the future, we could add agent type to deal with agents that should not be included in the Semantic Kernel group chat.
    all_agents_config = [
        agent for agent in participant_configs if agent.get("name") != "magentic"
    ]

    def _create_kernel_with_chat_completion() -> Kernel:
        kernel = Kernel()

        if is_gemini or is_groq or (has_openai and not has_azure):
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
            if is_gemini:
                base_url = os.getenv("OPENAI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai/"
                default_model = "gemini-2.0-flash"
            elif is_groq:
                base_url = os.getenv("OPENAI_BASE_URL") or "https://api.groq.com/openai/v1"
                default_model = "openai/gpt-oss-120b"
            else:
                base_url = os.getenv("OPENAI_BASE_URL")
                default_model = "gpt-4o"

            model_id = os.getenv("OPENAI_MODEL_ID", default_model)

            if base_url:
                async_client = AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=5)
                kernel.add_service(
                    RateLimitedOpenAIChatCompletion(
                        service_id="default",
                        ai_model_id=model_id,
                        async_client=async_client,
                    )
                )
            else:
                async_client = AsyncOpenAI(api_key=api_key, max_retries=5)
                kernel.add_service(
                    RateLimitedOpenAIChatCompletion(
                        service_id="default",
                        ai_model_id=model_id,
                        async_client=async_client,
                    )
                )
        else:
            azure_kwargs = {
                "service_id": "default",
                "deployment_name": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
                "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            }
            if os.getenv("AZURE_OPENAI_ENDPOINT"):
                azure_kwargs["endpoint"] = os.getenv("AZURE_OPENAI_ENDPOINT")
            if os.getenv("AZURE_OPENAI_API_KEY"):
                azure_kwargs["api_key"] = os.getenv("AZURE_OPENAI_API_KEY")
            elif hasattr(app_ctx, "cognitive_services_token_provider"):
                try:
                    azure_kwargs["ad_token_provider"] = app_ctx.cognitive_services_token_provider
                except Exception:
                    pass
            kernel.add_service(AzureChatCompletion(**azure_kwargs))
        return kernel

    def _create_agent(agent_config: dict):
        agent_kernel = _create_kernel_with_chat_completion()
        plugin_config = PluginConfiguration(
            kernel=agent_kernel,
            agent_config=agent_config,
            data_access=app_ctx.data_access,
            chat_ctx=chat_ctx,
            azureml_token_provider=app_ctx.azureml_token_provider,
            app_ctx=app_ctx,
        )
        is_healthcare_agent = healthcare_agent_config.yaml_key in agent_config and bool(
            agent_config[healthcare_agent_config.yaml_key])

        for tool in agent_config.get("tools", []):
            tool_name = tool.get("name")
            tool_type = tool.get("type", DEFAULT_TOOL_TYPE)

            # Add function tools
            if tool_type == "function":
                scenario = os.environ.get("SCENARIO")
                tool_module = importlib.import_module(f"scenarios.{scenario}.tools.{tool_name}")
                agent_kernel.add_plugin(tool_module.create_plugin(plugin_config), plugin_name=tool_name)
            # Add OpenAPI tools
            # See https://github.com/Azure-Samples/healthcare-agent-orchestrator/blob/main/docs/agent_development.md#agent-with-a-openapi-plugin-example
            elif tool_type == "openapi":
                openapi_document_path = tool.get("openapi_document_path")
                server_url_override = tool.get("server_url_override")
                timeout = tool.get("timeout", 600)
                debug_logging = tool.get("debug_logging", False)
                agent_kernel.add_plugin_from_openapi(
                    plugin_name=tool_name,
                    openapi_document_path=openapi_document_path,
                    execution_settings=OpenAPIFunctionExecutionParameters(
                        http_client=create_logging_http_client(timeout) if debug_logging else None,
                        auth_callback=create_auth_callback(chat_ctx),
                        server_url_override=server_url_override,
                        enable_payload_namespacing=True,
                        timeout=timeout
                    )
                )
            else:
                raise ValueError(f"Unknown tool type: {tool_type}")

        if model_supports_temperature():
            temperature = agent_config.get("temperature", DEFAULT_MODEL_TEMP)
            logger.info(f"Setting model temperature for agent {agent_config['name']} to {temperature}")
        else:
            temperature = None
            logger.info(
                f"Model does not support temperature. Setting temperature to None for agent {agent_config['name']}")

        if is_gemini:
            settings = OpenAIChatPromptExecutionSettings(
                function_choice_behavior=FunctionChoiceBehavior.Auto(), temperature=temperature)
        elif is_groq or (has_openai and not has_azure):
            settings = OpenAIChatPromptExecutionSettings(
                function_choice_behavior=FunctionChoiceBehavior.Auto(), seed=42, temperature=temperature)
        else:
            settings = AzureChatPromptExecutionSettings(
                function_choice_behavior=FunctionChoiceBehavior.Auto(), seed=42, temperature=temperature)

        arguments = KernelArguments(settings=settings)
        instructions = agent_config.get("instructions")
        if agent_config.get("facilitator") and instructions:
            agent_list_str = "\n\t\t".join([f"- {agent['name']}: {agent.get('description', '')}" for agent in all_agents_config])
            instructions = instructions.replace("{{aiAgents}}", agent_list_str)

        return (CustomChatCompletionAgent(kernel=agent_kernel,
                                          name=agent_config["name"],
                                          instructions=instructions,
                                          description=agent_config["description"],
                                          arguments=arguments) if not is_healthcare_agent else
                HealthcareAgent(name=agent_config["name"],
                                chat_ctx=chat_ctx,
                                app_ctx=app_ctx))

    if is_gemini:
        response_fmt = {"type": "json_object"}
        if model_supports_temperature():
            settings = OpenAIChatPromptExecutionSettings(
                temperature=0, response_format=response_fmt)
        else:
            settings = OpenAIChatPromptExecutionSettings(
                response_format=response_fmt)
    elif is_groq or (has_openai and not has_azure):
        response_fmt = {"type": "json_object"}
        if model_supports_temperature():
            settings = OpenAIChatPromptExecutionSettings(
                seed=42, temperature=0, response_format=response_fmt)
        else:
            settings = OpenAIChatPromptExecutionSettings(
                seed=42, response_format=response_fmt)
    else:
        if model_supports_temperature():
            settings = AzureChatPromptExecutionSettings(
                seed=42, temperature=0, response_format=ChatRule)
        else:
            settings = AzureChatPromptExecutionSettings(
                seed=42, response_format=ChatRule)

    facilitator_agent = next((agent for agent in all_agents_config if agent.get("facilitator")), all_agents_config[0])
    facilitator = facilitator_agent["name"]

    participants_list_str = "\n".join([("\t- " + agent["name"]) for agent in all_agents_config])
    participants_names_str = ",".join([agent["name"] for agent in all_agents_config])

    # Create selection function with proper input variable configuration
    selection_prompt_config = PromptTemplateConfig(
        name="selection",
        description="Agent selection prompt",
        template=f"""
        You are overseeing a group chat between several AI agents and a human user.
        Determine which participant takes the next turn in a conversation based on the most recent participant. Follow these guidelines:

        1. **Participants**: Choose only from these participants:
            {participants_list_str}

        2. **General Rules**:
            - **{facilitator} Always Starts**: {facilitator} always goes first to formulate a plan. If the only message is from the user, {facilitator} goes next.
            - **Interactions between agents**: Agents may talk among themselves. If an agent requires information from another agent, that agent should go next.
                EXAMPLE:
                    "*agent_name*, please provide ..." then agent_name goes next.
            - **"back to you *agent_name*": If an agent says "back to you", that agent goes next.
                EXAMPLE:
                    "back to you *agent_name*" then output agent_name goes next.
            - **Once per turn**: Each participant can only speak once per turn.
            - **Default to {facilitator}**: Always default to {facilitator}. If no other participant is specified, {facilitator} goes next.
            - **Use best judgment**: If the rules are unclear, use your best judgment to determine who should go next, for the natural flow of the conversation.
            
        **Output Format**: Respond strictly in valid JSON format:
        {{"verdict": "<exact_agent_name>", "reasoning": "<explanation>"}}
        The verdict MUST be the exact name of the participant who should go next.

        History:
        {{{{$history}}}}
        """,
        input_variables=[
            InputVariable(name="history", allow_dangerously_set_content=True)
        ]
    )

    selection_function = KernelFunctionFromPrompt(
        function_name="selection",
        prompt_template_config=selection_prompt_config,
        prompt_execution_settings=settings
    )

    termination_prompt_config = PromptTemplateConfig(
        name="termination",
        description="Agent termination prompt",
        template=f"""
        Determine if the conversation should end based on the most recent message.
        You only have access to the last message in the conversation.

        You MUST respond strictly in valid JSON format:
        {{"verdict": "yes" or "no", "reasoning": "<explanation>"}}

        You are part of a group chat with several AI agents and a user. 
        The agents are names are: 
            {participants_names_str}

        If the most recent message is a question addressed to the user, return "yes".
        If the question is addressed to "we" or "us", return "yes". For example, if the question is "Should we proceed?", return "yes".
        If the question is addressed to another agent, return "no".
        If it is a statement addressed to another agent, return "no".
        Commands addressed to a specific agent should result in 'no' if there is clear identification of the agent.
        Commands addressed to "you" or "User" should result in 'yes'.
        If you are not certain, return "yes".

        EXAMPLES:
            - "User, can you confirm the correct patient ID?" => "yes"
            - "*ReportCreation*: Please compile the patient timeline. Let's proceed with *ReportCreation*." => "no" (ReportCreation is an agent)
            - "*ReportCreation*, please proceed ..." => "no" (ReportCreation is an agent)
            - "If you have any further questions or need assistance, feel free to ask." => "yes"
            - "Let's proceed with Radiology." => "no" (Radiology is an agent)
            - "*PatientStatus*, please use ..." => "no" (PatientStatus is an agent)
        History:
        {{{{$history}}}}
        """,
        input_variables=[
            InputVariable(name="history", allow_dangerously_set_content=True)
        ]
    )

    termination_function = KernelFunctionFromPrompt(
        function_name="termination",
        prompt_template_config=termination_prompt_config,
        prompt_execution_settings=settings
    )
    agents = [_create_agent(agent) for agent in all_agents_config]

    def evaluate_termination(result):
        logger.info(f"Termination function result: {result}")
        try:
            val = str(result.value[0]).strip()
            if "```" in val:
                parts = val.split("```")
                if len(parts) > 1:
                    val = parts[1]
                    if val.startswith("json"):
                        val = val[4:]
                    val = val.strip()
            try:
                data = json.loads(val)
                verdict = str(data.get("verdict", "")).lower()
            except Exception:
                rule = ChatRule.model_validate_json(val)
                verdict = rule.verdict.lower()
            return verdict == "yes"
        except Exception as e:
            logger.warning(f"Error parsing termination verdict, fallback check: {e}")
            val_lower = str(result.value[0]).lower() if result and getattr(result, "value", None) else ""
            return "yes" if "yes" in val_lower else False

    def evaluate_selection(result):
        logger.info(f"Selection function result: {result}")
        try:
            val = str(result.value[0]).strip()
            if "```" in val:
                parts = val.split("```")
                if len(parts) > 1:
                    val = parts[1]
                    if val.startswith("json"):
                        val = val[4:]
                    val = val.strip()
            verdict = None
            try:
                data = json.loads(val)
                verdict = data.get("verdict")
            except Exception:
                try:
                    rule = ChatRule.model_validate_json(val)
                    verdict = rule.verdict
                except Exception:
                    pass

            if verdict:
                verdict_str = str(verdict).strip()
                for agent in all_agents_config:
                    if agent["name"].lower() == verdict_str.lower():
                        return agent["name"]

            val_str = str(result.value[0]) if result and getattr(result, "value", None) else ""
            for agent in all_agents_config:
                if agent["name"].lower() in val_str.lower():
                    return agent["name"]

            return facilitator
        except Exception as e:
            logger.warning(f"Error parsing selection verdict, fallback agent match: {e}")
            return facilitator

    class SafeKernelFunctionSelectionStrategy(KernelFunctionSelectionStrategy):
        async def next(self, agents: list, history: list) -> any:
            try:
                return await super().next(agents, history)
            except Exception as e:
                logger.warning(f"Selection strategy exception caught safely ({e}), defaulting to facilitator: {facilitator}")
                for agent in agents:
                    if agent.name.lower() == facilitator.lower():
                        return agent
                return agents[0]

    class SafeKernelFunctionTerminationStrategy(KernelFunctionTerminationStrategy):
        async def should_terminate(self, agent: any, history: list) -> bool:
            try:
                return await super().should_terminate(agent, history)
            except Exception as e:
                logger.warning(f"Termination strategy exception caught safely ({e}), defaulting to False")
                return False

    chat = AgentGroupChat(
        agents=agents,
        chat_history=chat_ctx.chat_history,
        selection_strategy=SafeKernelFunctionSelectionStrategy(
            function=selection_function,
            kernel=_create_kernel_with_chat_completion(),
            result_parser=evaluate_selection,
            agent_variable_name="agents",
            history_variable_name="history",
        ),
        termination_strategy=SafeKernelFunctionTerminationStrategy(
            agents=[
                agent for agent in agents if agent.name == facilitator
            ],  # Only facilitator decides if the conversation ends
            function=termination_function,
            kernel=_create_kernel_with_chat_completion(),
            result_parser=evaluate_termination,
            agent_variable_name="agents",
            history_variable_name="history",
            maximum_iterations=30,
            # Termination only looks at the last message
            history_reducer=ChatHistoryTruncationReducer(
                target_count=1, auto_reduce=True
            ),
        ),
    )

    return (chat, chat_ctx)
