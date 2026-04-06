import streamlit as st
from datetime import datetime
import pytz

# The UI only imports the compiled graph, keeping it blind to internal agent logic
from core.graph import notschool_app

def main():
    st.set_page_config(page_title="Notschool OS", page_icon="🎓", layout="centered")

    st.title("Notschool OS")
    st.subheader("Your AI Orchestrator for Skills and Studies")

    # 1. Collect Inputs
    goal = st.text_input("What do you want to learn today?", placeholder="e.g., Master Advanced Python Decorators")
    uploaded_image = st.file_uploader("Upload a syllabus, diagram, or inspiration (optional)", type=["png", "jpg", "jpeg"])

    if st.button("Generate Learning Path"):
        if not goal:
            st.warning("Please provide a learning goal to proceed.")
            return

        with st.spinner("Orchestrating agents..."):
            # 2. Construct the Initial State
            # Enforcing IST for accurate calendar scheduling context
            ist_tz = pytz.timezone('Asia/Kolkata')
            current_time = datetime.now(ist_tz).strftime("%Y-%m-%d %H:%M:%S")

            initial_state = {
                "goal": goal,
                "image_bytes": uploaded_image.getvalue() if uploaded_image else None,
                "curriculum_json": None,
                "youtube_urls": [],
                "calendar_event_id": None,
                "db_record_id": None,
                "messages": [{"role": "user", "content": goal}],
                "user_timezone": "Asia/Kolkata",
                "current_timestamp": current_time
            }

            # 3. Fire and Forget
            try:
                # The entire multi-agent workflow happens in this single line
                final_state = notschool_app.invoke(initial_state)

                st.success("Workflow Complete!")

                # 4. Render the Final State
                if final_state.get("curriculum_json"):
                    st.json(final_state["curriculum_json"])

                if final_state.get("youtube_urls"):
                    st.markdown("### Curated Resources")
                    for url in final_state["youtube_urls"]:
                        st.write(f"- {url}")

            except Exception as e:
                st.error(f"Orchestration failed: {e}")

if __name__ == "__main__":
    main()