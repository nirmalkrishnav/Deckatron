"""Call Decision-family models with reusable state and typed questions."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from typesafe_sdk import (
    AsyncTypeSafeClient,
    Content,
    Question,
    RetryPolicy,
    SystemOneResponse,
    TypeSafeError,
)

from deck_router.utils.settings import DecisionSettings

logger = logging.getLogger(__name__)


class DecisionClientError(RuntimeError):
    """A Decision request cannot be configured, sent, or validated."""


@dataclass(frozen=True)
class DecisionInput:
    """Caller-supplied state and named Noul, Choice, or Score questions."""

    state: Content
    questions: Mapping[str, Question]


class DecisionClient:
    """Use a configured Decision model without any deck-specific routing logic."""

    def __init__(self, settings: DecisionSettings | None = None) -> None:
        self.settings = settings if settings is not None else DecisionSettings()

    async def call_decision(
        self, data: DecisionInput, *, model: str | None = None
    ) -> SystemOneResponse:
        """Evaluate input, returning typed answers and probabilities.

        Args:
            data: State and named questions to evaluate.
            model: Deployment override; otherwise use DECISION_MODEL.

        Raises:
            DecisionClientError: Configuration, request, or response is invalid.
        """
        settings = self.settings
        deployment = settings.model if model is None else model
        if (
            settings.endpoint is None
            or settings.api_key is None
            or not settings.api_key.get_secret_value().strip()
            or not deployment.strip()
        ):
            raise DecisionClientError(
                "Configure AZURE_DECISION_ENDPOINT, DECISION_API_KEY, and DECISION_MODEL "
                "in the root .env, or supply DecisionSettings and a model override"
            )
        try:
            async with AsyncTypeSafeClient(
                api_key=settings.api_key.get_secret_value(),
                base_url=str(settings.endpoint),
                model=deployment,
                timeout=settings.timeout,
                retry=RetryPolicy(max_retries=1),
            ) as client:
                return await client.system_one(state=data.state, questions=data.questions)
        except TypeSafeError as error:
            logger.error("Decision model request failed (%s)", type(error).__name__)
            raise DecisionClientError(
                "Decision model request failed; verify input, endpoint, deployment, and credentials"
            ) from error
