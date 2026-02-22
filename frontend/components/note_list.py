import streamlit as st
from services import tag_service, note_service

def generate_markdown_from_notes(result: dict) -> str:
    """
    Generate markdown with proper heading hierarchy.
    Root tag = H1, deeper entries = H2, H3, etc.
    """
    md_lines = []
    
    title = result.get("title", "")
    if title:
        md_lines.append(f"# {title}\n")
    
    for section, notes in result.get("sections", {}).items():
        if notes:
            display_section = section.replace("_", " ").title()
            md_lines.append(f"## {display_section}\n")
            for n in notes:
                content = n.get("content", "")
                if content:
                    md_lines.append(f"- {content}")
                if n.get("media"):
                    md_lines.append(f"  - 📎 [Media]({n.get('media')})")
                tags = n.get("tags", [])
                if tags:
                    md_lines.append(f"  - Tags: {', '.join(tags)}")
            md_lines.append("")
    
    if result.get("remaining"):
        md_lines.append("## Other Notes\n")
        for n in result.get("remaining", []):
            content = n.get("content", "")
            if content:
                md_lines.append(f"- {content}")
            tags = n.get("tags", [])
            if tags:
                md_lines.append(f"  - Tags: {', '.join(tags)}")
        md_lines.append("")
    
    return "\n".join(md_lines)

def render_search_and_list():
    st.header("🔍 Browse Notes by Topic")
    browse_topic = st.text_input("Search by topic/tag (comma-separated for multiple)", key="browse_topic")

    if browse_topic:
        topics = [t.strip() for t in browse_topic.split(",") if t.strip()]
        
        if len(topics) > 1:
            # Multiple topics - resolve with context
            resolved_topics = {}
            for topic in topics:
                context = [resolved_topics[k]["tag"]["label"] for k in resolved_topics if "tag" in resolved_topics[k]]
                resolved = tag_service.resolve_tag(topic, note_tags=context)
                resolved_topics[topic] = resolved
                
            disambiguate_needed = {k: v for k, v in resolved_topics.items() 
                                   if v and v.get("status") == "multiple_matches"}
                                   
            if disambiguate_needed:
                st.warning("⚠️ Multiple matches found for some topics:")
                user_selections = {}
                for topic, resolved in disambiguate_needed.items():
                    candidates = resolved.get("candidates", [])
                    st.markdown(f"**{topic}:**")
                    options = [c.get("path") for c in candidates]
                    selected = st.radio(f"Choose path for '{topic}':", options, key=f"browse_{topic}")
                    user_selections[topic] = selected
                
                for topic, selected_path in user_selections.items():
                    if selected_path:
                        topic_path = selected_path.strip("/")
                        success, result = note_service.generate_topic_markdown(topic_path)
                        if success:
                            md_content = generate_markdown_from_notes(result)
                            st.markdown("---")
                            st.markdown(f"### 📄 {selected_path}")
                            st.code(md_content, language="markdown")
            else:
                for topic in topics:
                    resolved = resolved_topics.get(topic)
                    if resolved and resolved.get("status") == "unique_match":
                        tag_path = resolved.get("tag", {}).get("path", "")
                        topic_path = tag_path.strip("/")
                        success, result = note_service.generate_topic_markdown(topic_path)
                        if success:
                            md_content = generate_markdown_from_notes(result)
                            st.markdown("---")
                            st.markdown(f"### 📄 {tag_path}")
                            st.code(md_content, language="markdown")
        elif len(topics) == 1:
            topic = topics[0]
            resolved = tag_service.resolve_tag(topic)
            
            if resolved:
                if resolved.get("status") == "multiple_matches":
                    candidates = resolved.get("candidates", [])
                    st.warning(f"⚠️ Multiple '{topic}' tags found. Which one interests you?")
                    
                    for i, c in enumerate(candidates):
                        st.markdown(f"  - {c.get('label')} → `{c.get('path')}`")
                        
                    options = [c.get("path") for c in candidates]
                    selected_path = st.radio("Select one:", options, key="browse_topic_select")
                    
                    if selected_path:
                        topic_path = selected_path.strip("/")
                        success, result = note_service.generate_topic_markdown(topic_path)
                        if success:
                            md_content = generate_markdown_from_notes(result)
                            st.markdown("---")
                            st.markdown("### 📄 Generated Markdown")
                            st.code(md_content, language="markdown")
                elif resolved.get("status") == "unique_match":
                    tag_path = resolved.get("tag", {}).get("path", "")
                    topic_path = tag_path.strip("/")
                    success, result = note_service.generate_topic_markdown(topic_path)
                    if success:
                        md_content = generate_markdown_from_notes(result)
                        st.markdown("---")
                        st.markdown("### 📄 Generated Markdown")
                        st.code(md_content, language="markdown")
                elif resolved.get("status") == "not_found":
                    st.info(f"❌ Tag '{topic}' not found in hierarchy")
                    suggested = resolved.get("suggested_parents", [])
                    if suggested:
                        st.write("Did you mean:")
                        for s in suggested:
                            st.markdown(f"  - `{s.get('path')}`")
            else:
                success, result = note_service.generate_topic_markdown(topic.lower())
                if success:
                    md_content = generate_markdown_from_notes(result)
                    st.code(md_content, language="markdown")
        else:
            st.info("Enter at least one topic to browse")
