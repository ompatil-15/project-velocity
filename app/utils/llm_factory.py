import os
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrock


def get_llm(
    provider: str = None, model_name: str = None, api_key: str = None
) -> BaseChatModel:
    """
    Factory to return a LangChain Chat Model based on the provider.
    Reads defaults from environment variables if arguments are not provided.
    """
    provider = provider or os.getenv("LLM_PROVIDER", "google").lower()

    # Common default models if not specified
    defaults = {
        "google": "gemini-2.0-flash",
        "openai": "gpt-4o",
        "anthropic": "claude-3-opus-20240229",
        "bedrock": "anthropic.claude-3-sonnet-20240229-v1:0",
    }

    model_name = model_name or os.getenv("LLM_MODEL", defaults.get(provider))
    api_key = api_key or os.getenv("LLM_API_KEY")

    if (
        not api_key and provider != "bedrock"
    ):  # Bedrock might use AWS credentials from env
        # Fallback to provider-specific env vars if generic LLM_API_KEY is missing
        if provider == "google":
            api_key = os.getenv("GOOGLE_API_KEY")
        elif provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key and provider != "bedrock":
        raise ValueError(
            f"API Key not found for provider '{provider}'. Set LLM_API_KEY or provider-specific key."
        )

    if provider == "google":
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)

    elif provider == "openai":
        return ChatOpenAI(model=model_name, api_key=api_key)

    elif provider == "anthropic":
        return ChatAnthropic(model=model_name, api_key=api_key)

    elif provider == "bedrock":
        # Bedrock typically uses boto3 credentials (AWS_ACCESS_KEY_ID, etc.)
        return ChatBedrock(model_id=model_name)

    else:
        raise ValueError(f"Unsupported LLM Provider: {provider}")
