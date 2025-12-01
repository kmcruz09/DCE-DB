import streamlit as st
import streamlit.components.v1 as components
import random
import fxn
import re

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
    
    /* Compact expanders */
    .streamlit-expanderHeader {
        font-size: 1.1em;
        font-weight: 600;
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
    }
    .streamlit-expanderContent {
        padding-bottom: 1rem !important;
    }
    /* Center align the entry counter */
    .entry-counter {
        text-align: center;
        font-weight: 600;
        padding-top: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- UI Helper Functions ---

def reset_focus():
    """Resets the focused index to 0. Used as a callback for filters."""
    if "focused_index" in st.session_state:
        st.session_state.focused_index = 0

def render_entry(item, index, expanded_default, api_key):
    """
    Renders a single entry as a Streamlit expander.
    Uses fxn helper functions for parsing.
    """
    # Extract Title
    title_prop = "Untitled"
    for key, val in item["raw"]["properties"].items():
        if val["type"] == "title":
            title_text = fxn.rich_text_to_markdown(val["title"])
            if title_text: title_prop = title_text
            break
    
    # Add Star to Title if highlighted (removed background color)
    if item["Highlighted"]:
        title_prop = f"⭐ {title_prop}"
    
    # Prepend Entry Number to Title
    title_prop = f"#{index}. {title_prop}"

    # Compact Metadata String
    meta_parts = []
    if item["Entry Type"]: meta_parts.append(f"🏷️ {', '.join(item['Entry Type'])}")
    if item["Section"]: meta_parts.append(f"📂 {', '.join(item['Section'])}")
    if item["Reference"]: meta_parts.append(f"📖 {', '.join(item['Reference'])}")
    meta_string = " • ".join(meta_parts) # Bullet separator

    with st.expander(f"{title_prop}", expanded=expanded_default):
        if meta_string:
            st.caption(meta_string)
        
        # Body Content
        if item["Body"]:
            st.markdown(item["Body"])

        # Images & Content Blocks
        types_needing_images = ["Imaging", "Figure", "Slides", "Table"]
        if any(t in types_needing_images for t in item["Entry Type"]):
            with st.spinner(f"Loading content..."):
                blocks = fxn.fetch_page_blocks(api_key, item["id"])
                for block in blocks:
                    if block["type"] == "image":
                        img_type = block["image"]["type"]
                        img_url = block["image"][img_type]["url"]
                        caption = fxn.rich_text_to_markdown(block["image"].get("caption", []))
                        st.image(img_url, caption=caption, width=400)

# --- Load Secrets (Hidden) ---
try:
    api_key = st.secrets["NOTION_API_KEY"]
    db_id = st.secrets["NOTION_DATABASE_ID"]
except:
    st.error("Missing secrets.toml")
    st.stop()

# --- Main App Interface ---

# 1. Fetch Data
with st.spinner("Fetching Question Bank..."):
    raw_entries = fxn.fetch_database_entries(api_key, db_id)

if not raw_entries:
    st.warning("No entries found.")
    st.stop()

# 2. Process Data & Resolve IDs
processed_entries = []
ids_to_resolve = set()

for entry in raw_entries:
    p_type = fxn.get_property_value(entry, "Entry Type")
    p_section = fxn.get_property_value(entry, "Section")
    p_reference = fxn.get_property_value(entry, "Reference")
    p_body = fxn.get_property_value(entry, "Body")
    p_star = fxn.get_property_value(entry, "⭐")  # Extract Star Property
    
    # Normalize to lists
    types = p_type if isinstance(p_type, list) else ([p_type] if p_type else [])
    sections = p_section if isinstance(p_section, list) else ([p_section] if p_section else [])
    refs = p_reference if isinstance(p_reference, list) else ([p_reference] if p_reference else [])
    
    # Collect IDs for resolution
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

# 3. Resolve Names (Local Cache + API)
id_map = {}
if ids_to_resolve:
    # Only verify cache/fetch if needed
    id_map = fxn.resolve_page_titles(api_key, ids_to_resolve)

# Apply resolution map & build sets for filters
all_types = set()
all_sections = set()
# Note: all_references will be calculated dynamically based on section selection

for item in processed_entries:
    item["Section"] = [id_map.get(s, s) for s in item["Section"]]
    item["Reference"] = [id_map.get(r, r) for r in item["Reference"]]
    
    for t in item["Entry Type"]: all_types.add(t)
    for s in item["Section"]: all_sections.add(s)

# 4. Sidebar Controls
st.sidebar.header("View Settings")

# Focused Mode Toggle
focused_mode = st.sidebar.checkbox("Focused Mode", value=False, help="Show one entry at a time in the center")

# Column Selector (Only show if not in Focused Mode)
if not focused_mode:
    # Using segmented control for columns selection (1 to 3)
    num_columns = st.sidebar.segmented_control(
        "Columns",
        options=[1, 2, 3],
        default=1
    )
else:
    # Initialize focused index state if missing
    if "focused_index" not in st.session_state:
        st.session_state.focused_index = 0

st.sidebar.divider()
st.sidebar.subheader("Filter by Section")

# Section Checkboxes
sorted_sections = sorted(list(all_sections))

# Select/Clear All Section Buttons
btn_col1, btn_col2 = st.sidebar.columns(2)
with btn_col1:
    if st.button("Select All"):
        for sec in sorted_sections: st.session_state[f"chk_{sec}"] = True
with btn_col2:
    if st.button("Clear All"):
        for sec in sorted_sections: st.session_state[f"chk_{sec}"] = False

selected_sections = []
if not sorted_sections:
    st.sidebar.caption("No sections found")
else:
    for sec in sorted_sections:
        key = f"chk_{sec}"
        if key not in st.session_state: st.session_state[key] = False
        if st.sidebar.checkbox(sec, key=key):
            selected_sections.append(sec)

# Dynamic Reference Filter (Moved to Sidebar)
st.sidebar.divider()
st.sidebar.subheader("Filter by Reference")

# Determine available references based on selected sections
available_references = set()
if not selected_sections:
    # If no section selected, show ALL references (standard dashboard behavior)
    for item in processed_entries:
        for r in item["Reference"]: available_references.add(r)
else:
    # Only show references relevant to the selected sections
    for item in processed_entries:
        if any(s in selected_sections for s in item["Section"]):
            for r in item["Reference"]: available_references.add(r)

selected_references = st.sidebar.multiselect(
    "Select References", 
    sorted(list(available_references))
)

# 5. Main Page Filter (Entry Type as Pills)
st.write("**Filter by Entry Type**")
sorted_types = sorted(list(all_types))

# Use st.pills for compact, side-by-side clickable rounded rectangles
selected_types = st.pills(
    "Entry Types",
    sorted_types,
    selection_mode="multi",
    label_visibility="collapsed",
    on_change=reset_focus # Auto-reset focus when filter changes
)

# 6. Main Panel Controls (Highlight & Shuffle)
# Placed directly below the pills, using toggles side-by-side
ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 1, 2])

with ctrl_col1:
    filter_highlight = st.toggle("⭐ Highlight Only", value=False)

with ctrl_col2:
    if "shuffle_seed" not in st.session_state:
        st.session_state.shuffle_seed = 0
    shuffle_enabled = st.toggle("Shuffle Order", value=False)

with ctrl_col3:
    if shuffle_enabled:
        if st.button("Reshuffle", use_container_width=False):
            st.session_state.shuffle_seed += 1
            if focused_mode: st.session_state.focused_index = 0

# 7. Apply Filters
filtered_data = []
for item in processed_entries:
    # Section Match
    match_section = True
    if selected_sections:
        match_section = any(s in selected_sections for s in item["Section"])
    
    # Reference Match
    match_ref = True
    if selected_references:
        match_ref = any(r in item["Reference"] for r in selected_references)
        
    # Type Match
    match_type = True
    if selected_types:
        match_type = any(t in item["Entry Type"] for t in selected_types)
        
    # Highlight Match
    match_highlight = True
    if filter_highlight:
        match_highlight = item["Highlighted"]
    
    if match_type and match_section and match_ref and match_highlight:
        filtered_data.append(item)

# 8. Shuffle Logic (Applied after filtering)
if shuffle_enabled:
    rng = random.Random(st.session_state.shuffle_seed)
    rng.shuffle(filtered_data)

st.divider()

# Ensure we have data to show
total_entries = len(filtered_data)
if total_entries == 0:
    st.warning("No entries found with current filters.")
    st.stop()

# 9. Display Logic (Branched: Focused Mode vs Grid Mode)

if focused_mode:
    # --- FOCUSED MODE UI ---
    
    # Clamp index to bounds
    st.session_state.focused_index = max(0, min(st.session_state.focused_index, total_entries - 1))
    current_idx = st.session_state.focused_index
    
    # JavaScript Hack for Arrow Key Navigation (Left/Right only - NO Down Arrow)
    components.html("""
    <script>
    const doc = window.parent.document;
    doc.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowLeft') {
            const buttons = Array.from(doc.querySelectorAll('button'));
            const prevBtn = buttons.find(b => b.innerText.includes('Previous'));
            if (prevBtn) {
                prevBtn.click();
            }
        }
        if (e.key === 'ArrowRight') {
            const buttons = Array.from(doc.querySelectorAll('button'));
            const nextBtn = buttons.find(b => b.innerText.includes('Next'));
            if (nextBtn) {
                nextBtn.click();
            }
        }
    });
    </script>
    """, height=0, width=0)
    
    # Render Entry (Centered)
    _, center_col, _ = st.columns([1, 6, 1])
    
    with center_col:
        item = filtered_data[current_idx]
        # In Focused Mode, we default to EXPANDED so the user sees content immediately
        render_entry(item, current_idx + 1, expanded_default=True, api_key=api_key)

    st.markdown("") # Spacing

    # Navigation Buttons (Below entry)
    _, nav_container, _ = st.columns([1, 4, 1])
    
    with nav_container:
        # Compact Row for Nav
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
    # --- GRID / LIST MODE UI ---
    st.caption(f"Showing {total_entries} entries")
    cols = st.columns(num_columns)

    # Enumerate starting from 1 to give a running count
    for i, item in enumerate(filtered_data, 1):
        col_idx = (i - 1) % num_columns
        with cols[col_idx]:
            # In List Mode, we default to EXPANDED for visibility
            render_entry(item, i, expanded_default=True, api_key=api_key)