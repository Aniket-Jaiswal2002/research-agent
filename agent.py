from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from tools import pdf_search_tool, web_search_tool

load_dotenv()

# ── Create the LLM with tools bound to it ────────────────────────────
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0
)

# Bind tools to the LLM — the model can now call them automatically
llm_with_tools = llm.bind_tools([pdf_search_tool, web_search_tool])

# ── System prompt ─────────────────────────────────────────────────────
system_prompt = """You are ResearchMind, an expert AI research assistant.
You help users understand documents and find information.
Always cite your sources — use page numbers for PDF content and URLs for web content.
When answering, first search the PDF, then supplement with web search if needed."""

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
    while response.tool_calls:
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_input = tool_call["args"]

            print(f"\nUsing tool: {tool_name}")
            print(f"Input: {tool_input}")

            # call the right tool
            if tool_name == "pdf_search_tool":
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