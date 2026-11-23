"""Call GPT-style Azure deployments independently of any A2A routing policy."""

import logging
from dataclasses import dataclass

from openai import AsyncAzureOpenAI, OpenAIError, omit
from pydantic import BaseModel, ValidationError

from deck_router.utils.settings import AzureSettings

logger = logging.getLogger(__name__)


class LLMClientError(RuntimeError):
    """An LLM call cannot be configured, sent, or validated."""


@dataclass(frozen=True)
class LLMInput:
    """A prompt, system instructions, and an optional structured output model."""

    prompt: str
    system_prompt: str = "You are a helpful assistant."
    response_model: type[BaseModel] | None = None


@dataclass(frozen=True)
class LLMOutput:
    """Generated text and the validated model when structured output was requested."""

    text: str
    parsed: BaseModel | None


class LLMClient:
    """Use the configured Azure deployment or a per-call deployment override."""

    def __init__(self, settings: AzureSettings | None = None) -> None:
        self.settings = settings if settings is not None else AzureSettings()

    async def call_llm(self, data: LLMInput, *, model: str | None = None) -> LLMOutput:
        """Generate text, optionally parsed into a supplied Pydantic response model.

        Args:
            data: Prompt, instructions, and optional output schema.
            model: Azure deployment override; otherwise use AZURE_OPENAI_DEPLOYMENT.

        Raises:
            LLMClientError: Configuration is missing, the call fails,
                or no usable answer is returned.
        """
        settings = self.settings
        deployment = settings.deployment if model is None else model
        if (
            settings.endpoint is None
            or settings.api_key is None
            or not settings.api_key.get_secret_value().strip()
            or not deployment.strip()
            or not settings.api_version.strip()
        ):
            raise LLMClientError(
                "Configure AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, "
                "AZURE_OPENAI_DEPLOYMENT, and AZURE_OPENAI_API_VERSION "
                "in the root .env, or supply AzureSettings and a model override"
            )
        if not data.prompt.strip():
            raise LLMClientError("The LLM prompt must contain text")
        try:
            async with AsyncAzureOpenAI(
                azure_endpoint=str(settings.endpoint),
                api_key=settings.api_key.get_secret_value(),
                api_version=settings.api_version,
                timeout=settings.timeout,
                max_retries=1,
            ) as client:
                completion = await client.chat.completions.parse(
                    model=deployment,
                    messages=[
                        {"role": "system", "content": data.system_prompt},
                        {"role": "user", "content": data.prompt},
                    ],
                    response_format=data.response_model or omit,
                )
        except (OpenAIError, ValidationError) as error:
            logger.error("LLM request failed (%s)", type(error).__name__)
            raise LLMClientError(
                "LLM request failed; verify input, endpoint, deployment, and credentials"
            ) from error

        if not completion.choices:
            raise LLMClientError("The LLM returned no answer")
        answer = completion.choices[0].message
        if answer.refusal or not answer.content or not answer.content.strip():
            raise LLMClientError("The LLM refused the request or returned no text")
        if data.response_model is not None and not isinstance(answer.parsed, data.response_model):
            raise LLMClientError("The LLM did not return the requested structured output")
        return LLMOutput(text=answer.content, parsed=answer.parsed)
