from langgraph.graph import StateGraph, START, END
from core.state import NotschoolState

# Import the isolated node functions. 
# Your AI/API engineers will build the actual logic inside these files.
from agents.architect_node import architect_node
from agents.librarian_node import librarian_node
from agents.scheduler_node import scheduler_node
from agents.db_node import db_node

def build_notschool_graph() -> StateGraph:
    """
    Compiles the LangGraph state machine.
    """
    workflow = StateGraph(NotschoolState)

    # 1. Register the Nodes (The "Workers")
    workflow.add_node("architect", architect_node)
    workflow.add_node("librarian", librarian_node)
    workflow.add_node("scheduler", scheduler_node)
    workflow.add_node("db_saver", db_node)

    # 2. Define the Edges (The "Workflow")
    # This is a linear path, but you can easily add conditional_edges here later
    workflow.add_edge(START, "architect")
    workflow.add_edge("architect", "librarian")
    workflow.add_edge("librarian", "scheduler")
    workflow.add_edge("scheduler", "db_saver")
    workflow.add_edge("db_saver", END)

    # Compile into an executable application
    return workflow.compile()

# Expose the compiled instance so the UI can import it cleanly
notschool_app = build_notschool_graph()