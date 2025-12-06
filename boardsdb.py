import streamlit as st
import streamlit.components.v1 as components
import random
import re
import fxn
import time

# --- Page Config ---
st.set_page_config(page_title="DCE Prep", layout="centered", page_icon="🩺")

# --- CSS ---
st.markdown("""
<style>
    .block-container {
        padding-top: 4rem;
        padding-bottom: 2rem;
    }
    .stMarkdown p {
        margin-bottom: 0.5rem;
    }
    .katex { font-size: 1.1em; }
    
    .entry-title {
        font-weight: 700;
        font-size: 1.1em;
        margin-bottom: 0.2rem;
        margin-top: 0rem !important;
        padding-top: 0rem !important;
    }
    
    .entry-counter {
        text-align: center;
        font-weight: 600;
        padding-top: 8px;
    }
    
    .stButton button {
        margin-top: 0px; 
    }
    
    .info-text {
        text-align: left;
        font-size: 0.9em;
        color: #666;
    }
    
    .end-text {
        text-align: center;
        font-size: 0.9em;
        color: #888;
        font-style: italic;
        padding: 10px;
    }
    
    .load-more-status {
        text-align: center;
        font-size: 0.9em;
        color: #666;
        margin-bottom: 5px;
    }
    
    /* Back to Top Link */
    .back-to-top {
        text-align: center;
        margin-top: 20px;
        padding-bottom: 20px;
    }
    .back-to-top a {
        text-decoration: none;
        color: #666;
        font-weight: 600;
        cursor: pointer;
    }
    .back-to-top a:hover {
        color: #fbc02d;
    }
</style>
""", unsafe_allow_html=True)

# --- UI Helpers ---

def reset_view():
    """Resets view state and scrolls to top when filters change."""
    st.session_state.focused_index = 0
    st.session_state.visible_count = 30
    st.session_state.scroll_to_top = True
    st.session_state.render_key = str(random.randint(0, 1000000))

def load_more_entries():
    st.session_state.scroll_to_entry = st.session_state.visible_count + 1
    st.session_state.visible_count += 30

def clear_search():
    st.session_state.search_query = ""
    st.session_state.selected_entry_types = []
    reset_view()

def render_entry(item, index, api_key, unique_suffix=""):
    """Renders a single entry card."""
    container_key = f"card_{item['id']}_{index}_{unique_suffix}"
    
    with st.container(key=container_key, border=True):
        markdown_content = f"<div id='entry-{index}-{unique_suffix}'></div>"
        if item["Highlighted"]:
            markdown_content += f"""<style>div.st-key-{container_key}{{background-color:#fffdf5;border:1px solid #e6c845;}}div.st-key-{container_key} p,div.st-key-{container_key} span,div.st-key-{container_key} div{{color:#262730!important;}}div.st-key-{container_key} .katex{{color:#262730!important;}}</style>"""
        title_prop = "Untitled"
        for key, val in item["raw"]["properties"].items():
            if val["type"] == "title":
                title_text = fxn.rich_text_to_markdown(val["title"])
                if title_text: title_prop = title_text
                break
        title_prop = f"[{index}] {title_prop}"
        markdown_content += f"<div class='entry-title'>{title_prop}</div>"
        st.markdown(markdown_content, unsafe_allow_html=True)

        # Metadata
        meta_parts = []
        if item["Entry Type"]: meta_parts.append(f"◾️ {', '.join(item['Entry Type'])}")
        if item["Section"]: meta_parts.append(f"📂 {', '.join(item['Section'])}")
        if item["Reference"]: meta_parts.append(f"🔗 {', '.join(item['Reference'])}")
        meta_string = " • ".join(meta_parts)

        if meta_string:
            st.caption(meta_string)
        
        # Body
        if item["Body"]:
            st.markdown(item["Body"])

        # Content Blocks (Images)
        types_needing_images = ["Imaging", "Figure", "Slides", "Table"]
        
        if any(t in types_needing_images for t in item["Entry Type"]):
            with st.container(key=f"imgs_{container_key}"):
                blocks = fxn.fetch_page_blocks(api_key, item["id"])
                if blocks:
                    for block in blocks:
                        if block["type"] == "image":
                            img_type = block["image"]["type"]
                            img_url = block["image"][img_type]["url"]
                            st.image(img_url, width=400)

# --- Secrets ---
try:
    api_key = st.secrets["NOTION_API_KEY"]
    db_id = st.secrets["NOTION_DATABASE_ID"]
except:
    st.error("Missing secrets.toml")
    st.stop()

# --- Main Interface ---

# 1. Top Scroll Anchor
st.markdown("<div id='top'></div>", unsafe_allow_html=True)

# 2. Scroll Logic
js_scroll_script = ""
if st.session_state.get("scroll_to_top", False):
    js_scroll_script += f"""
        setTimeout(function() {{
            var target = window.parent.document.getElementById('top');
            if (target) {{
                target.scrollIntoView({{behavior: 'smooth', block: 'center'}});
            }}
        }}, 300);
        console.log("Link click simulation: {time.time()}");
    """
    st.session_state.scroll_to_top = False

entry_target = st.session_state.get("scroll_to_entry", None)
if entry_target:
    js_scroll_script += f"""
        setTimeout(function() {{
            var target = window.parent.document.getElementById('entry-{entry_target}-grid');
            if (target) {{
                target.scrollIntoView({{behavior: 'smooth', block: 'center'}});
            }}
        }}, 300);
    """
    st.session_state.scroll_to_entry = None
if js_scroll_script:
    components.html(f"<script>{js_scroll_script}</script>", height=0, width=0)

# 3. State Init
if "visible_count" not in st.session_state:
    st.session_state.visible_count = 30
if "render_key" not in st.session_state:
    st.session_state.render_key = "init"

# 4. Fetch Data
with st.spinner("Fetching Entries..."):
    raw_entries = fxn.fetch_database_entries(api_key, db_id)

if not raw_entries:
    st.warning("No entries found.")
    st.stop()

# 5. Process Data
processed_entries = []
all_sections = set()

for entry in raw_entries:
    p_type = fxn.get_property_value(entry, "Entry Type")
    p_body = fxn.get_property_value(entry, "Body")
    p_star = fxn.get_property_value(entry, "⭐")
    sections = fxn.get_property_value(entry, "Section-RU") or []
    refs = fxn.get_property_value(entry, "Reference-RU") or []
    
    for s in sections: 
        all_sections.add(s)

    processed_entries.append({
        "id": entry["id"],
        "Entry Type": p_type if isinstance(p_type, list) else ([p_type] if p_type else []),
        "Section": sections,
        "Reference": refs,
        "Body": p_body,
        "Highlighted": bool(p_star),
        "raw": entry,
    })

# --- Sidebar Controls ---
st.sidebar.subheader("Filter by Section")

sorted_sections = sorted(list(all_sections))
selected_sections = []
if not sorted_sections:
    st.sidebar.caption("No sections found")
else:
    for sec in sorted_sections:
        key = f"chk_{sec}"
        if key not in st.session_state: st.session_state[key] = False
        if st.sidebar.checkbox(sec, key=key, on_change=reset_view):
            selected_sections.append(sec)

if st.sidebar.button("Reset"):
    for sec in sorted_sections: st.session_state[f"chk_{sec}"] = False
    reset_view()

st.sidebar.subheader("Filter by Reference")

available_references = set()
if not selected_sections:
    for item in processed_entries:
        for r in item["Reference"]: available_references.add(r)
else:
    for item in processed_entries:
        if any(s in selected_sections for s in item["Section"]):
            for r in item["Reference"]: available_references.add(r)

selected_references = st.sidebar.multiselect(
    "Select References", 
    sorted(list(available_references)),
    on_change=reset_view
)

st.sidebar.divider()
if st.sidebar.button("🔄️ Refresh Cache", help="Clear cache and fetch updates"):
    st.cache_data.clear()
    st.rerun()

# --- Main Panel ---
if "shuffle_seed" not in st.session_state:
    st.session_state.shuffle_seed = 0

with st.container(horizontal=True):
    filter_highlight = st.toggle("Highlighted Only ⭐", value=False, on_change=reset_view)
    shuffle_enabled = st.toggle("Shuffle", value=False, on_change=reset_view)
    focused_mode = st.toggle("Focused Mode", value=False, help="One entry at a time")

if not focused_mode:
    if "focused_index" not in st.session_state:
        st.session_state.focused_index = 0

# Search
search_col1, search_col2= st.columns([4, 3])
with search_col1:
    search_query = st.text_input("🔍 Search Question Body", placeholder="Type keywords...", label_visibility="collapsed", key="search_query", on_change=reset_view)
with search_col2:
    with st.container(horizontal=True):
        st.button("✖", on_click=clear_search, help="Clear Filters")
        if shuffle_enabled:
            if st.button("🎲", help="Reshuffle"):
                st.session_state.shuffle_seed += 1
                reset_view()


# Entry Filters
pre_type_filtered_data = []
for item in processed_entries:
    match_section = True
    if selected_sections:
        match_section = any(s in selected_sections for s in item["Section"])
    match_ref = True
    if selected_references:
        match_ref = any(r in item["Reference"] for r in selected_references)
    match_highlight = True
    if filter_highlight:
        match_highlight = item["Highlighted"]
    match_search = True
    if search_query:
        query = search_query.lower()
        body_text = item["Body"].lower() if item["Body"] else ""
        in_body = query in body_text
        title_text = ""
        for key, val in item["raw"]["properties"].items():
            if val["type"] == "title":
                title_text = fxn.rich_text_to_markdown(val["title"]).lower()
                break
        in_title = query in title_text
        match_search = in_body or in_title
    if match_section and match_ref and match_highlight and match_search:
        pre_type_filtered_data.append(item)

# Pills
available_entry_types = set()
for item in pre_type_filtered_data:
    for t in item["Entry Type"]:
        available_entry_types.add(t)

st.write("**Filter by Entry Type**")
sorted_types = sorted(list(available_entry_types))

if not sorted_types:
    st.caption("No entry types available for current filters.")
    selected_types = []
else:
    selected_types = st.pills(
        "Entry Types",
        sorted_types,
        selection_mode="multi",
        label_visibility="collapsed",
        on_change=reset_view,
        key="selected_entry_types"
    )

# Final Filter
filtered_data = []
for item in pre_type_filtered_data:
    match_type = True
    if selected_types:
        match_type = any(t in item["Entry Type"] for t in selected_types)
    if match_type:
        filtered_data.append(item)

if shuffle_enabled:
    rng = random.Random(st.session_state.shuffle_seed)
    rng.shuffle(filtered_data)

total_entries = len(filtered_data)
if total_entries == 0:
    st.warning("No entries found with current filters.")
    st.stop()

list_context_id = f"{st.session_state.render_key}_{len(filtered_data)}"

# --- Display ---

if focused_mode:
    # Focused Mode
    st.session_state.focused_index = max(0, min(st.session_state.focused_index, total_entries - 1))
    current_idx = st.session_state.focused_index
    
    # Arrows Listener
    components.html("""
    <script>
    const doc = window.parent.document;
    doc.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowLeft') {
            const prev = Array.from(doc.querySelectorAll('button')).find(b => b.innerText.includes('Previous'));
            if (prev) prev.click();
        }
        if (e.key === 'ArrowRight') {
            const next = Array.from(doc.querySelectorAll('button')).find(b => b.innerText.includes('Next'));
            if (next) next.click();
        }
    });
    </script>
    """, height=0, width=0)
    
    _, center_col, _ = st.columns([1, 6, 1])
    with center_col:
        item = filtered_data[current_idx]
        render_entry(item, current_idx + 1, api_key=api_key, unique_suffix=f"focus_{list_context_id}")

    st.markdown("") 

    _, nav_container, _ = st.columns([1, 4, 1])
    with nav_container:
        n1, n2, n3 = st.columns([1, 2, 1])
        with n1:
            if st.button("⬅️ Previous", use_container_width=True):
                st.session_state.focused_index = (current_idx - 1) % total_entries
                st.rerun()
        with n2:
            st.markdown(f"<div class='entry-counter'>Entry {current_idx + 1} of {total_entries}</div>", unsafe_allow_html=True)
        with n3:
            if st.button("Next ➡️", use_container_width=True):
                st.session_state.focused_index = (current_idx + 1) % total_entries
                st.rerun()

else:
    # Grid / List Mode
    st.caption(f"Found {total_entries} entries")

    visible_count = st.session_state.visible_count
    visible_data = filtered_data[:visible_count]
    
    list_stage = st.empty()
    with list_stage.container():
        # Keep the unique key to ensure deep refreshing
        with st.container(key=f"list_root_{list_context_id}"):
            # Single Column Layout
            for i, item in enumerate(visible_data):
                actual_index = i + 1
                render_entry(item, actual_index, api_key=api_key, unique_suffix="grid")

    # Load More
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        if len(filtered_data) > visible_count:
            st.markdown(f"<div class='load-more-status'>Showing {len(visible_data)} / {total_entries} entries</div>", unsafe_allow_html=True)
            st.button("Load More Entries", on_click=load_more_entries, use_container_width=True)
        else:
            st.markdown("<div class='end-text'>End of entries</div>", unsafe_allow_html=True)
    
    # Always show Back to Top
    st.markdown("""
        <div class='back-to-top'>
            <a href='#top' target='_self'>⬆ Back to Top</a>
        </div>
        """, unsafe_allow_html=True)