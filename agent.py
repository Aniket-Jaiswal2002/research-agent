from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from tools import pdf_search_tool, web_search_tool

load_dotenv()

# ── Create the LLM with tools bound to it ────────────────────────────
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0
)

# Bind tools to the LLM — the model can now call them automatically
llm_with_tools = llm.bind_tools([pdf_search_tool, web_search_tool])

# ── System prompt ─────────────────────────────────────────────────────
system_prompt = """You are ResearchMind, an expert AI research assistant.
You help users understand documents and find information.

STRICT RULES — ALWAYS FOLLOW:
- ALWAYS use pdf_search_tool first for every question, no exceptions
- ALWAYS cite your sources with page numbers for PDF and URLs for web
- NEVER answer from your own knowledge without searching first
- If PDF doesn't have the answer, use web_search_tool
- FAISS search works by topic/meaning, NOT by page numbers
- Never call the same tool twice with identical input
- Format web sources as markdown links like [Source Title](url)
- Format PDF sources as: (Source: filename, Page X)"""

# ── Agent loop ────────────────────────────────────────────────────────
def chat(question: str) -> str:
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=question)
    ]

    print("\n" + "="*60)
    print(f"Question: {question}")
    print("="*60)

    # Step 1: Ask LLM what to do
    response = llm_with_tools.invoke(messages)
    messages.append(response)

    # Step 2: Execute tool calls if any
    max_iterations = 6
    iteration = 0
    seen_queries = set()

    while response.tool_calls and iteration < max_iterations:
        iteration += 1
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_input = tool_call["args"]

            print(f"\nUsing tool: {tool_name}")
            print(f"Input: {tool_input}")

            # call the right tool
            if tool_name == "pdf_search_tool":
                query = str(tool_input)
                if query in seen_queries:
                    result = "Already searched this. Try different keywords."
                else:
                    seen_queries.add(query)
                    result = pdf_search_tool.invoke(tool_input)
            elif tool_name == "web_search_tool":
                result = web_search_tool.invoke(tool_input)
            else:
                result = "Tool not found"

            print(f"Result preview: {str(result)[:200]}...")

            # Add tool result to messages
            from langchain_core.messages import ToolMessage
            messages.append(ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"]
            ))

        # Step 3: Ask LLM again with tool results
        response = llm_with_tools.invoke(messages)
        messages.append(response)

    return response.content


# ── Interactive chat loop ─────────────────────────────────────────────
if __name__ == "__main__":
    print("🔬 ResearchMind Agent Ready!")
    print("Ask me anything about your PDF or any research topic.")
    print("Type 'quit' to exit\n")

    while True:
        question = input("You: ").strip()
        if question.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break
        if not question:
            continue
        answer = chat(question)
        print(f"\nResearchMind: {answer}\n")
          