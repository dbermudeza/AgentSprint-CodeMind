from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.agents.chat_agent import agente
from src.state import AgentState
from src.tools import all_tools

workflow = StateGraph(AgentState)
workflow.add_node("agente", agente)
workflow.add_node("tools", ToolNode(all_tools))

workflow.set_entry_point("agente")
workflow.add_conditional_edges("agente", tools_condition, {"tools": "tools", END: END})
workflow.add_edge("tools", "agente")

grafo = workflow.compile()
