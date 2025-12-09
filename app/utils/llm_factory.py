import os
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrock
from app.utils.retry import RetryingLLM


def get_llm(
    provider: str = None,
    model_name: str = None,
    api_key: str = None,
    with_retry: bool = True,
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
) -> BaseChatModel:
    """
    Factory to return a LangChain Chat Model based on the provider.
    Reads defaults from environment variables if arguments are not provided.
    
    Args:
        provider: LLM provider (google, openai, anthropic, bedrock)
        model_name: Model name to use
        api_key: API key for the provider
        with_retry: Wrap LLM with retry logic for rate limit handling (default: True)
        max_retries: Maximum number of retries on rate limit (default: 5)
        base_delay: Base delay in seconds for exponential backoff (default: 2.0)
        max_delay: Maximum delay between retries (default: 60.0)
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

    # Create the base LLM
    llm = None
    if provider == "google":
        llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)

    elif provider == "openai":
        llm = ChatOpenAI(model=model_name, api_key=api_key)

    elif provider == "anthropic":
        llm = ChatAnthropic(model=model_name, api_key=api_key)

    elif provider == "bedrock":
        # Bedrock typically uses boto3 credentials (AWS_ACCESS_KEY_ID, etc.)
        llm = ChatBedrock(model_id=model_name)

    else:
        raise ValueError(f"Unsupported LLM Provider: {provider}")

    # Wrap with retry logic if requested (especially important for free tier rate limits)
    if with_retry:
        return RetryingLLM(
            llm,
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
        )

    return llm
