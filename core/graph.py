from langgraph.graph import StateGraph, END
from core.state import NotschoolState

# Import the isolated node functions from the agents directory
from agents.architect_node import architect_node
from agents.librarian_node import librarian_node
from agents.scheduler_node import scheduler_node
from agents.db_node import db_node

def build_notschool_graph():
    """
    Compiles the LangGraph state machine.
    """
    # Initialize the graph with our strict schema
    workflow = StateGraph(NotschoolState)

    # 1. Register the Nodes (The "Workers")
    workflow.add_node("architect", architect_node)
    workflow.add_node("librarian", librarian_node)
    workflow.add_node("scheduler", scheduler_node)
    workflow.add_node("db_saver", db_node)

    # 2. Define the Edges (The "Workflow")
    # For langgraph v0.0.26, we define the start using set_entry_point()
    workflow.set_entry_point("architect")
    
    workflow.add_edge("architect", "librarian")
    workflow.add_edge("librarian", "scheduler")
    workflow.add_edge("scheduler", "db_saver")
    workflow.add_edge("db_saver", END)

    # Compile into an executable application
    return workflow.compile()

# Expose the compiled instance so the FastAPI server can invoke it
notschool_app = build_notschool_graph()