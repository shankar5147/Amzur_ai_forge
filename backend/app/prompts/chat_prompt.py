from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful, concise AI assistant. Answer clearly and accurately.",
        ),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{message}"),
    ]
)
