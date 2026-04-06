import streamlit as st
from typing import Dict, Any, List

def render_hero_section():
    """Renders the main headers and UI styling instructions."""
    st.title("Notschool OS")
    st.subheader("Your AI Orchestrator for Skills and Studies")
    st.markdown("---")

def render_curriculum_view(curriculum: Dict[str, Any]):
    """
    Takes the raw JSON state from LangGraph and renders it into 
    beautiful Streamlit components.
    """
    title = curriculum.get("title", "Generated Learning Path")
    st.header(f"🎓 {title}")
    
    st.markdown("### Your Step-by-Step Modules")
    modules = curriculum.get("modules", [])
    
    if not modules:
        st.warning("No modules were generated. Please try a different prompt.")
        return

    # Use Streamlit expanders or info boxes for a clean UI
    for idx, module in enumerate(modules):
        st.info(f"**Step {idx + 1}:** {module}")

def render_video_resources(urls: List[str]):
    """
    Transforms raw YouTube URLs into embedded video players.
    """
    st.markdown("### 📺 Curated Video Resources")
    
    if not urls:
        st.write("No videos found for this topic.")
        return

    # Create a responsive grid layout using Streamlit columns
    cols = st.columns(len(urls))
    
    for idx, url in enumerate(urls):
        with cols[idx]:
            try:
                # Streamlit natively supports YouTube embeds
                st.video(url)
            except Exception:
                # Fallback if the embed fails
                st.markdown(f"[Watch Resource on YouTube]({url})")