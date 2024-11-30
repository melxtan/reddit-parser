import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List

from botocore.exceptions import ClientError
from langfuse.decorators import langfuse_context, observe

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    model_id: str
    anthropic_version: str = "bedrock-2023-05-31"
    max_tokens: int = 4096
    max_retries: int = 3
    base_delay: int = 2


@dataclass
class LLMResponse:
    content: str
    parsed_json: Any | None


class LLMCaller:
    def __init__(self, bedrock_runtime, config: LLMConfig):
        self.bedrock = bedrock_runtime
        self.config = config

    def _prepare_request_body(
        self,
        system_message: str | None,
        messages: List[Dict[str, str]],
        **override_params,
    ) -> Dict[str, Any]:
        """
        Prepare the request body with only essential parameters and any overrides.
        """
        # Only include the required parameters
        body = {
            "anthropic_version": self.config.anthropic_version,
            "max_tokens": self.config.max_tokens,
            "messages": messages,
        }

        # Optional system message
        if system_message:
            body["system"] = system_message

        # Override any parameters
        body.update(override_params)
        return body

    @observe(as_type="generation")
    def _invoke_bedrock(
        self, body: Dict[str, Any], trace_name: str | None = None
    ) -> LLMResponse:
        """
        Makes the actual Bedrock API call with Langfuse observability.
        """
        if trace_name:
            langfuse_context.update_current_trace(name=trace_name)

        # Update Langfuse context with all parameters that were actually used
        langfuse_context.update_current_observation(
            input=body,
            model=self.config.model_id,
            model_parameters={
                key: value
                for key, value in body.items()
                if key not in ["messages", "system", "anthropic_version"]
            },
        )

        response = self.bedrock.invoke_model(
            modelId=self.config.model_id,
            body=json.dumps(body, ensure_ascii=False),
            accept="application/json",
            contentType="application/json",
        )

        response_body = json.loads(response["body"].read().decode())
        content = response_body["content"][0]["text"]

        # Update Langfuse with response and actual usage
        langfuse_context.update_current_observation(
            output=content,
            usage={
                "input": response_body["usage"]["input_tokens"],
                "output": response_body["usage"]["output_tokens"],
            },
        )

        return LLMResponse(content=content, parsed_json=None)

    def _make_single_call(
        self,
        system_message: str | None,
        messages: List[Dict[str, str]],
        trace_name: str | None = None,
        **override_params,
    ) -> LLMResponse:
        """
        Prepares the request and handles errors.
        """
        try:
            body = self._prepare_request_body(
                system_message, messages, **override_params
            )
            return self._invoke_bedrock(body, trace_name)

        except ClientError as e:
            error_message = f"Bedrock API error: {str(e)}"
            langfuse_context.update_current_observation(
                level="ERROR", status_message=error_message
            )
            raise
        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            langfuse_context.update_current_observation(
                level="ERROR", status_message=error_message
            )
            raise

    def _extract_json_from_content(self, content: str) -> Any | None:
        try:
            import re

            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
            if json_match:
                return json.loads(json_match.group(1))
            return json.loads(content)
        except Exception:
            return None

    def call(
        self,
        messages: List[Dict[str, str]],
        system_message: str,
        trace_name: str,
        **override_params,
    ) -> LLMResponse:
        """
        Makes an LLM call with retry logic.
        Returns both the raw content and parsed JSON if available.
        """
        for attempt in range(self.config.max_retries):
            try:
                logger.debug(f"Attempt {attempt + 1}/{self.config.max_retries}")
                response = self._make_single_call(
                    system_message, messages, trace_name=trace_name, **override_params
                )
                content = response.content
                parsed_json = self._extract_json_from_content(content)
                return LLMResponse(content=content, parsed_json=parsed_json)

            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    logger.error(f"Final retry failed: {str(e)}")
                    raise

                delay = self.config.base_delay * (2**attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed, retrying in {delay} seconds..."
                )
                time.sleep(delay)

    def call_with_prefill(
        self,
        user_message: str,
        assistant_prefill: str,
        system_message: str,
        trace_name: str,
        **override_params,
    ) -> LLMResponse:
        """
        Makes an LLM call with a prefilled assistant message.
        The response will combine the prefilled message with the LLM's response.

        Args:
            user_message: The user's input message
            assistant_prefill: The initial part of the assistant's response
            system_message: System message for the LLM
            trace_name: Name for tracing
            **override_params: Additional parameters to override defaults

        Returns:
            LLMResponse with combined content (prefill + LLM response)
        """
        messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_prefill},
        ]

        response = self.call(
            messages=messages,
            system_message=system_message,
            trace_name=trace_name,
            **override_params,
        )

        # Combine the prefilled message with the LLM's response
        combined_content = assistant_prefill + response.content

        # Re-parse JSON from combined content if needed
        parsed_json = self._extract_json_from_content(combined_content)

        return LLMResponse(content=combined_content, parsed_json=parsed_json)
