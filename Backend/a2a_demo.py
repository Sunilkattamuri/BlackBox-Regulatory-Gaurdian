"""
A self-contained demonstration of true Agent-to-Agent (A2A) Peer-to-Peer communication using LangGraph.
Run this from your terminal: python a2a_demo.py
"""

import os
import operator
from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END

# Import your existing LLM setup
from app.config import settings

# Since we want them to debate creatively, we'll manually instantiate the LLM with a slightly higher temperature
if settings.LLM_PROVIDER == "ollama":
    from langchain_community.chat_models import ChatOllama
    llm = ChatOllama(model=settings.LLM_MODEL, temperature=0.5, base_url=settings.LLM_BASE_URL)
elif settings.LLM_PROVIDER == "openai":
    # pyrefly: ignore [missing-import]
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=0.5, api_key=settings.OPENAI_API_KEY)
else:
    raise ValueError("Only Ollama and OpenAI supported for this demo.")


class DebateState(TypedDict):
    """The Blackboard where agents write their messages to each other."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    revision_count: int


def policy_drafter(state: DebateState):
    print("\n[ Drafter is typing...]")
    messages = state["messages"]
    
    sys_msg = SystemMessage(content=(
        "You are a Banking Policy Drafter. Your job is to draft a short, 3-point internal policy "
        "based on the initial prompt. If the Critic gives you feedback, you MUST revise the policy "
        "to address their concerns. Keep it short!"
    ))
    
    response = llm.invoke([sys_msg] + list(messages))
    print(f"\n DRAFTER:\n{response.content}\n")
    print("-" * 50)
    
    return {
        "messages": [AIMessage(content=response.content, name="Drafter")],
        "revision_count": state.get("revision_count", 0) + 1
    }


def compliance_critic(state: DebateState):
    print("\n[ Critic is reviewing...]")
    messages = state["messages"]
    
    sys_msg = SystemMessage(content=(
        "You are a strict Compliance Critic. Review the policy drafted by the Drafter (the last message). "
        "If it is missing strict financial penalties or is too vague, critique it and demand changes. "
        "If it looks perfect and strict enough (has penalties and clear rules), reply with EXACTLY the word 'APPROVED'."
    ))
    
    response = llm.invoke([sys_msg] + list(messages))
    print(f"\n CRITIC:\n{response.content}\n")
    print("=" * 50)
    
    return {
        "messages": [AIMessage(content=response.content, name="Critic")]
    }


def router(state: DebateState):
    """Decides if the debate should continue or end."""
    last_message = state["messages"][-1].content
    
    if "APPROVED" in last_message.upper():
        print("\n FINAL VERDICT: Policy Approved by Critic!")
        return END
        
    if state.get("revision_count", 0) >= 3:
        print("\n FINAL VERDICT: Max revisions reached. Debate forcefully ended.")
        return END
        
    return "drafter"


def main():
    print(" Starting A2A Debate: Policy Drafter vs Compliance Critic")
    
    # Build Graph
    workflow = StateGraph(DebateState)
    workflow.add_node("drafter", policy_drafter)
    workflow.add_node("critic", compliance_critic)

    workflow.set_entry_point("drafter")
    workflow.add_edge("drafter", "critic")
    workflow.add_conditional_edges("critic", router, {"drafter": "drafter", END: END})

    app = workflow.compile()

    # Start the debate
    initial_prompt = HumanMessage(content="We need a new policy for Employee Social Media Usage at the bank.")
    
    app.invoke({"messages": [initial_prompt], "revision_count": 0})

if __name__ == "__main__":
    main()
