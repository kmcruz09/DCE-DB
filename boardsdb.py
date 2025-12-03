import streamlit as st
import streamlit.components.v1 as components
import re
import random
import fxn  # Importing helper functions from fxn.py

# --- Page Config ---
st.set_page_config(page_title="DCE DB", layout="wide", page_icon="📚")

# --- CSS for styling equations, spacing, and compactness ---
st.markdown("""
<style>
    /* Compact main container */
    .block-container {
        padding-top: 4rem; /* Increased padding to prevent top bar overlap */
        padding-bottom: 2rem;
    }
    /* Reduce spacing between elements */
    .stMarkdown p {
        margin-bottom: 0.5rem;
    }
    /* Make LaTeX larger and readable */
    .katex { font-size: 1.1em; }
    
    /* Card Title Styling */
    .entry-title {
        font-weight: 700;
        font-size: 1.1em;
        margin-bottom: 0.2rem;
        margin-top: 0rem !important; /* Force no top margin to fix spacing issues */
        padding-top: 0rem !important;
    }
    
    /* Center align the entry counter */
    .entry-counter {
        text-align: center;
        font-weight: 600;
        padding-top: 8px;
    }
    /* Align the clear button with the text input */
    .stButton button {
        margin-top: 0px; 
    }
    
    /* Adjust st.warning to look more like a card container */
    div[data-testid="stAlert"] {
        padding-top: 0.5rem;
        padding-bottom: 0.5rem;
        border: 1px solid #fbc02d; /* Add border to match highlight theme */
    }
    
    /* Info Text */
    .info-text {
        text-align: left;
        font-size: 0.9em;
        color: #666;
    }
    
    /* End of list text */
    .end-text {
        text-align: center;
        font-size: 0.9em;
        color: #888;
        font-style: italic;
        padding: 10px;
    }
    
    /* Load more status text */
    .load-more-status {
        text-align: center;
        font-size: 0.9em;
        color: #666;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- UI Helper Functions ---

def reset_view():
    """Resets the focused index and visible count to initial state."""
    st.session_state.focused_index = 0
    st.session_state.visible_count = 50

def load_more_entries():
    """Increments the visible entry count."""
    st.session_state.visible_count += 50

def trigger_scroll_top():
    """Sets the state to trigger a scroll to top on rerun."""
    st.session_state.scroll_to_top = True

def clear_search():
    """Clears the search query."""
    st.session_state.search_query = ""
    reset_view()

def clear_entry_types():
    """Clears the Entry Type pills selection."""
    st.session_state.selected_entry_types = []
    reset_view()

def render_entry(item, index, expanded_default, api_key, unique_suffix=""):
    """
    Renders a single entry.
    Uses st.container for all entries, with CSS injection for highlighting.
    """
    # COMPOSITE KEY FIX
    container_key = f"card_{item['id']}_{index}_{unique_suffix}"
    
    # We use a standard bordered container for layout consistency
    with st.container(key=container_key, border=True):
        
        # Extract Title
        title_prop = "Untitled"
        for key, val in item["raw"]["properties"].items():
            if val["type"] == "title":
                title_text = fxn.rich_text_to_markdown(val["title"])
                if title_text: title_prop = title_text
                break
        
        # Format Numbering: [1] Title
        title_prop = f"[{index}] {title_prop}"
        
        # Initialize content string
        markdown_content = ""

        # Highlight Logic: Append CSS to content string if highlighted
        # Merging CSS and HTML into one string prevents Streamlit from 
        # rendering an empty block for the style tag.
        if item["Highlighted"]:
            markdown_content += f"""<style>div.st-key-{container_key}{{background-color:#fffdf5;border:1px solid #e6c845;}}div.st-key-{container_key} p,div.st-key-{container_key} span,div.st-key-{container_key} div{{color:#262730!important;}}div.st-key-{container_key} .katex{{color:#262730!important;}}</style>"""

        # Append Title HTML
        markdown_content += f"<div class='entry-title'>{title_prop}</div>"

        # 1. Render Title + CSS (Combined)
        st.markdown(markdown_content, unsafe_allow_html=True)

        # 2. Render Metadata
        meta_parts = []
        if item["Entry Type"]: meta_parts.append(f"🏷️ {', '.join(item['Entry Type'])}")
        if item["Section"]: meta_parts.append(f"📂 {', '.join(item['Section'])}")
        if item["Reference"]: meta_parts.append(f"📖 {', '.join(item['Reference'])}")
        meta_string = " • ".join(meta_parts)

        if meta_string:
            st.caption(meta_string)
        
        # 3. Render Body
        if item["Body"]:
            st.markdown(item["Body"])

        # 4. Render Images (Safeguarded)
        image_area = st.empty()
        
        types_needing_images = ["Imaging", "Figure", "Slides", "Table"]
        if any(t in types_needing_images for t in item["Entry Type"]):
            with image_area.container():
                with st.spinner(f"Loading content..."):
                    blocks = fxn.fetch_page_blocks(api_key, item["id"])
                    if blocks:
                        for block in blocks:
                            if block["type"] == "image":
                                img_type = block["image"]["type"]
                                img_url = block["image"][img_type]["url"]
                                caption = fxn.rich_text_to_markdown(block["image"].get("caption", []))
                                st.image(img_url, caption=caption, width=400)
                    else:
                        st.empty()
        else:
            image_area.empty()

# --- Load Secrets (Hidden) ---
try:
    api_key = st.secrets["NOTION_API_KEY"]
    db_id = st.secrets["NOTION_DATABASE_ID"]
except:
    st.error("Missing secrets.toml")
    st.stop()

# --- Main App Interface ---

# Scroll to top logic (Robust Implementation)
if st.session_state.get("scroll_to_top", False):
    js_scroll = """
        <script>
            setTimeout(function() {
                var doc = window.parent.document;
                // Target all possible scroll containers in Streamlit's iframe structure
                var containers = [
                    doc.querySelector('section.main'),
                    doc.querySelector('.stApp'),
                    doc.documentElement,
                    doc.body
                ];
                containers.forEach(function(el) {
                    if (el) el.scrollTop = 0;
                });
                // Fallback global scroll
                window.parent.scrollTo(0, 0);
            }, 150);
        </script>
    """
    components.html(js_scroll, height=0, width=0)
    st.session_state.scroll_to_top = False

# Initialize State
if "visible_count" not in st.session_state:
    st.session_state.visible_count = 50

# 1. Fetch Data
with st.spinner("Fetching Entries..."):
    raw_entries = fxn.fetch_database_entries(api_key, db_id)

if not raw_entries:
    st.warning("No entries found.")
    st.stop()

# 2. Process Data
processed_entries = []
ids_to_resolve = set()

for entry in raw_entries:
    p_type = fxn.get_property_value(entry, "Entry Type")
    p_section = fxn.get_property_value(entry, "Section")
    p_reference = fxn.get_property_value(entry, "Reference")
    p_body = fxn.get_property_value(entry, "Body")
    p_star = fxn.get_property_value(entry, "⭐")
    
    types = p_type if isinstance(p_type, list) else ([p_type] if p_type else [])
    sections = p_section if isinstance(p_section, list) else ([p_section] if p_section else [])
    refs = p_reference if isinstance(p_reference, list) else ([p_reference] if p_reference else [])
    
    for s in sections:
        if re.match(r'^[a-f0-9\-]{32,36}$', str(s)): ids_to_resolve.add(str(s))
    for r in refs:
        if re.match(r'^[a-f0-9\-]{32,36}$', str(r)): ids_to_resolve.add(str(r))

    processed_entries.append({
        "id": entry["id"],
        "Entry Type": types,
        "Section": [str(s) for s in sections],
        "Reference": [str(r) for r in refs],
        "Body": p_body,
        "Highlighted": bool(p_star),
        "raw": entry
    })

# 3. Resolve IDs
id_map = {}
if ids_to_resolve:
    id_map = fxn.resolve_page_titles(api_key, ids_to_resolve)

all_sections = set()
for item in processed_entries:
    item["Section"] = [id_map.get(s, s) for s in item["Section"]]
    item["Reference"] = [id_map.get(r, r) for r in item["Reference"]]
    for s in item["Section"]: all_sections.add(s)

# --- SIDEBAR CONTROLS ---
st.sidebar.header("View Settings")

# Focused Mode Toggle
focused_mode = st.sidebar.toggle("Focused Mode", value=False, help="Show one entry at a time in the center")

# Shuffle Controls
if "shuffle_seed" not in st.session_state:
    st.session_state.shuffle_seed = 0
shuffle_enabled = st.sidebar.toggle("Shuffle Order", value=False, on_change=reset_view)

if shuffle_enabled:
    if st.sidebar.button("Reshuffle", use_container_width=True):
        st.session_state.shuffle_seed += 1
        reset_view()

# Column Selector
num_columns = st.sidebar.segmented_control("Columns", options=[1, 2, 3], default=1)

# Initialize focused index
if "focused_index" not in st.session_state:
    st.session_state.focused_index = 0

# --- SIDEBAR FILTERS ---
st.sidebar.divider()
st.sidebar.subheader("Filter by Section")

sorted_sections = sorted(list(all_sections))
btn_col1, btn_col2 = st.sidebar.columns(2)
with btn_col1:
    if st.button("Select All"):
        for sec in sorted_sections: st.session_state[f"chk_{sec}"] = True
        reset_view()
with btn_col2:
    if st.button("Clear All"):
        for sec in sorted_sections: st.session_state[f"chk_{sec}"] = False
        reset_view()

selected_sections = []
if not sorted_sections:
    st.sidebar.caption("No sections found")
else:
    for sec in sorted_sections:
        key = f"chk_{sec}"
        if key not in st.session_state: st.session_state[key] = False
        if st.sidebar.checkbox(sec, key=key, on_change=reset_view):
            selected_sections.append(sec)

st.sidebar.divider()
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

# --- MAIN PANEL ---

# 4. Search Bar (Top)
search_col1, search_col2 = st.columns([10, 1])
with search_col1:
    search_query = st.text_input("🔍 Search Question Body", placeholder="Type keywords...", label_visibility="collapsed", key="search_query")
with search_col2:
    st.button("✖", on_click=clear_search, help="Clear Search")

# 5. Main Controls (Highlight)
filter_highlight = st.toggle("⭐ Highlighted Only", value=False, on_change=reset_view)

# 6. Pre-Filter Data
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

# 7. Dynamic Entry Type Pills
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

# 8. Final Filter & Shuffle
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

# --- DISPLAY LOGIC ---

# Calculate Filter State Hash for Unique Keys
filter_state = {
    "sections": tuple(sorted(selected_sections)),
    "refs": tuple(sorted(selected_references)),
    "types": tuple(sorted(selected_types)),
    "highlight": filter_highlight,
    "search": search_query,
    "shuffle": st.session_state.shuffle_seed,
    "columns": num_columns,
}
list_context_id = str(hash(str(filter_state)))

if focused_mode:
    # --- FOCUSED MODE ---
    st.session_state.focused_index = max(0, min(st.session_state.focused_index, total_entries - 1))
    current_idx = st.session_state.focused_index
    
    # JS Hack for Arrows
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
        render_entry(item, current_idx + 1, expanded_default=True, api_key=api_key, unique_suffix=f"focus_{list_context_id}")

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
    # --- INFINITE SCROLL / LOAD MORE MODE ---
    
    st.caption(f"Found {total_entries} entries")

    # Determine slice
    visible_count = st.session_state.visible_count
    visible_data = filtered_data[:visible_count]
    
    # --- Render Grid ---
    cols = st.columns(num_columns)
    
    for i, item in enumerate(visible_data):
        actual_index = i + 1
        col_idx = i % num_columns
        with cols[col_idx]:
            render_entry(item, actual_index, expanded_default=True, api_key=api_key, unique_suffix=f"grid_{list_context_id}")

    # --- Load More / End of List ---
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        if len(filtered_data) > visible_count:
            st.markdown(f"<div class='load-more-status'>Showing {len(visible_data)} / {total_entries} entries</div>", unsafe_allow_html=True)
            st.button("Load More Entries", on_click=load_more_entries, use_container_width=True)
        else:
            st.markdown("<div class='end-text'>End of entries</div>", unsafe_allow_html=True)
    
    # --- Back to Top ---
    _, top_btn_col, _ = st.columns([1, 2, 1])
    with top_btn_col:
        st.button("⬆ Back to Top", on_click=trigger_scroll_top, use_container_width=True)