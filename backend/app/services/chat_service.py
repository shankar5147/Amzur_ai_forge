from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.models.db_models import Message
from app.prompts.chat_prompt import CHAT_PROMPT


class LLMServiceError(Exception):
    pass


_THREAD_NAME_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Generate a short, descriptive title (max 6 words) for a conversation that starts with the following message. "
            "Return ONLY the title, no quotes, no punctuation at the end.",
        ),
        ("human", "{message}"),
    ]
)


class ChatService:
    def __init__(self) -> None:
        if not settings.litellm_virtual_key:
            raise LLMServiceError("Missing LITELLM_VIRTUAL_KEY environment variable.")

        self._llm = ChatOpenAI(
            model=settings.litellm_model,
            openai_api_key=settings.litellm_virtual_key,
            openai_api_base=f"{settings.litellm_proxy_url}/v1",
            temperature=0.3,
            default_headers={
                "x-litellm-user": settings.litellm_user_id,
                "x-litellm-department": settings.litellm_department,
                "x-litellm-environment": settings.litellm_environment,
            },
        )

        self._chain = CHAT_PROMPT | self._llm | StrOutputParser()
        self._name_chain = _THREAD_NAME_PROMPT | self._llm | StrOutputParser()

    @staticmethod
    def format_history(messages: list[Message]) -> list[HumanMessage | AIMessage]:
        """Convert DB messages to LangChain message objects."""
        history: list[HumanMessage | AIMessage] = []
        for msg in messages:
            if msg.role == "user":
                history.append(HumanMessage(content=msg.content))
            else:
                history.append(AIMessage(content=msg.content))
        return history

    async def generate_response(self, message: str, history: list[Message] | None = None) -> str:
        try:
            formatted_history = self.format_history(history) if history else []
            response: str = await self._chain.ainvoke({
                "message": message,
                "history": formatted_history,
            })
            return response
        except Exception as exc:
            raise LLMServiceError("Failed to get a response from LLM.") from exc

    async def generate_thread_name(self, first_message: str) -> str:
        try:
            name: str = await self._name_chain.ainvoke({"message": first_message})
            return name.strip()[:255]
        except Exception:
            # Fallback: use first few words of the message
            words = first_message.split()[:5]
            return " ".join(words)[:255]
