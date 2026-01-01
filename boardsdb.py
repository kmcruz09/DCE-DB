import streamlit as st
import streamlit.components.v1 as components
import random
import re
import fxn
import time
import concurrent.futures

st.set_page_config(page_title="DCE Prep", layout="centered", page_icon="🩺")
def kb_shortcuts():
    # This script attaches a listener to the parent document (the Streamlit app)
    # It intercepts Ctrl+B and Ctrl+I on any textarea to wrap text.
    js = """
    <script>
    (function() {
        if (window.parent.shortcutsAdded) return;
        
        window.parent.document.addEventListener('keydown', function(e) {
            // Only fire if a text area is focused
            if (e.target.tagName !== 'TEXTAREA') return;

            // Ctrl+B or Cmd+B for Bold
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'b') {
                e.preventDefault();
                const textarea = e.target;
                const start = textarea.selectionStart;
                const end = textarea.selectionEnd;
                const text = textarea.value;
                const selection = text.substring(start, end);
                
                // Wrap in **
                const replacement = "**" + selection + "**";
                
                textarea.value = text.substring(0, start) + replacement + text.substring(end);
                
                // Dispatch input event so Streamlit/React sees the change
                textarea.dispatchEvent(new Event('input', { bubbles: true }));
                
                // Restore selection range (including the new stars)
                textarea.setSelectionRange(start + 2, end + 2);
            }
            
            // Ctrl+I or Cmd+I for Italic
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'i') {
                e.preventDefault();
                const textarea = e.target;
                const start = textarea.selectionStart;
                const end = textarea.selectionEnd;
                const text = textarea.value;
                const selection = text.substring(start, end);
                
                // Wrap in *
                const replacement = "*" + selection + "*";
                
                textarea.value = text.substring(0, start) + replacement + text.substring(end);
                textarea.dispatchEvent(new Event('input', { bubbles: true }));
                textarea.setSelectionRange(start + 1, end + 1);
            }
        });
        window.parent.shortcutsAdded = true;
    })();
    </script>
    """
    components.html(js, height=0, width=0)
    
# --- CSS ---
st.markdown("""
<style>
    .block-container { padding-top: 4rem; padding-bottom: 2rem; }
    .stMarkdown p { margin-bottom: 0.5rem; }
    .katex { font-size: 1.1em; }
    
    .entry-title {
        font-weight: 700; font-size: 1.1em;
        margin-bottom: 0.2rem; margin-top: 0rem !important; padding-top: 0rem !important;
    }
            
    .entry-title a { text-decoration: none; color: #666; font-weight: 600; cursor: pointer; }
    .entry-title a:hover { color: #fbc02d; }
    .entry-counter { text-align: center; font-weight: 600; padding-top: 8px; }
    .stButton button { margin-top: 0px; }
    
    .info-text { text-align: left; font-size: 0.9em; color: #666; }
    .end-text { text-align: center; font-size: 0.9em; color: #888; font-style: italic; padding: 10px; }
    .load-more-status { text-align: center; font-size: 0.9em; color: #666; margin-bottom: 5px; }

    .back-to-top { text-align: center; margin-top: 20px; padding-bottom: 20px; }
    .back-to-top a { text-decoration: none; color: #666; font-weight: 600; cursor: pointer; }
    .back-to-top a:hover { color: #fbc02d; }
    /*div[data-testid="stButtonGroup"] {
        transform: scale(0.85);
        transform-origin: left top;
        margin-bottom: -15px !important; /* Pull up bottom space */
    }
    div[data-testid="stButtonGroup"] > div {
        padding-top: 0px !important;
        padding-bottom: 0px !important;
    }*/
    
    div[data-testid="stMultiSelect"] div[data-testid="stButtonGroup"] {
        transform: scale(0.9);
        transform-origin: left top;
    }

</style>
""", unsafe_allow_html=True)

# Updates
@st.cache_resource
def get_thread_pool():
    return concurrent.futures.ThreadPoolExecutor(max_workers=4)
executor = get_thread_pool()
if "priority_updates" not in st.session_state:
    st.session_state.priority_updates = {}
if "type_updates" not in st.session_state:
    st.session_state.type_updates = {}
if "body_updates" not in st.session_state:
    st.session_state.body_updates = {}
def update_priority_callback(page_id, key_name):
    new_val = st.session_state[key_name]
    st.session_state.priority_updates[page_id] = new_val
    executor.submit(fxn.update_page_property, api_key, page_id, "Priority", new_val, prop_type="select")
    st.toast(f"✅ Priority updated to {new_val}") 
def update_type_callback(page_id, key_name):
    new_val = st.session_state[key_name]
    st.session_state.type_updates[page_id] = new_val
    executor.submit(fxn.update_page_property, api_key, page_id, "Entry Type", new_val, prop_type="multi_select")
    st.toast(f"✅ Entry Type updated")
def update_body_callback(page_id, key_name):
    new_val = st.session_state[key_name]
    st.session_state.body_updates[page_id] = new_val
    executor.submit(fxn.update_page_property, api_key, page_id, "Body", new_val, prop_type="rich_text")
    st.toast(f"✅ Body updated")

# --- UI Helpers ---
def reset_view():
    """Resets view state and scrolls to top when filters change."""
    st.session_state.focused_index = 0
    st.session_state.visible_count = 30
    st.session_state.scroll_to_top = True
    st.session_state.render_key = str(random.randint(0, 1000000))
    if "count" in st.query_params: del st.query_params["count"]

def load_more_entries():
    st.session_state.scroll_to_entry = st.session_state.visible_count + 1
    st.session_state.visible_count += 30
    st.query_params["count"] = str(st.session_state.visible_count)

def clear_search():
    st.session_state.search_query = ""
    st.session_state.selected_entry_types = []
    reset_view()

def render_entry(item, index, api_key, edit_mode, all_available_types, unique_suffix=""):
    container_key = f"card_{item['id']}_{index}_{unique_suffix}"
    bg_color = "#ffffff"
    border_color = "rgba(49, 51, 63, 0.2)"
    text_color = "inherit"
    priority = item["Priority"]
    if priority == "1":
        bg_color = "#f0fdf4"
        border_color = "#86efac"
        text_color = "#262730"
    elif priority == "2":
        bg_color = "#fffdf5"
        border_color = "#e6c845"
        text_color = "#262730"
    elif priority == "3":
        bg_color = "#fff5f5" 
        border_color = "#ff99aa" 
        text_color = "#262730"

    with st.container(key=container_key, border=True):
        markdown_content = f"<div id='entry-{index}-{unique_suffix}'></div>"
        if priority in ["1", "2", "3"]:
            markdown_content += f"""
            <style>
                div.st-key-{container_key} {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                }}
                div.st-key-{container_key} p,
                div.st-key-{container_key} span,
                div.st-key-{container_key} div {{
                    color: {text_color} !important;
                }}
                div.st-key-{container_key} .katex {{
                    color: {text_color} !important;
                }}
            </style>
            """
        title_prop = "Untitled"
        page_url = item["raw"]["url"]

        for key, val in item["raw"]["properties"].items():
            if val["type"] == "title":
                title_text = fxn.rich_text_to_plain_text(val["title"])
                if title_text: title_prop = title_text
                break
        title_prop = f"[{index}] {title_prop}"
        markdown_content += f"<div class='entry-title'>{title_prop}<a href='{page_url}' target='_blank' title='link for Kaiser only ✌️'> ↗</a></div>"
        
        st.markdown(markdown_content, unsafe_allow_html=True)
        meta_parts = []
        if item["Entry Type"]: meta_parts.append(f"◾️ {', '.join(item['Entry Type'])}")
        if item["Section"]: meta_parts.append(f"🗄️ {', '.join(item['Section'])}")
        if item["Reference"]: meta_parts.append(f"📑 {', '.join(item['Reference'])}")
        meta_string = "&ensp;".join(meta_parts)
        if meta_string:
            st.caption(meta_string)
 
        # Body Entry
        if item["Body"]:
            st.markdown(item["Body"], unsafe_allow_html=True)

        # Blocks from Page (Images, Tables)
        types_needing_blocks = ["Imaging", "Figure", "Slides", "Table"]
        
        if any(t in types_needing_blocks for t in item["Entry Type"]):
            with st.container(key=f"imgs_{container_key}"):
                blocks = fxn.fetch_page_blocks(api_key, item["id"])
                if blocks:
                    for block in blocks:
                        # (1) Images
                        if block["type"] == "image":
                            img_type = block["image"]["type"]
                            img_url = block["image"][img_type]["url"]
                            img_html = f"""
                            <a href="{img_url}" target="_blank" title="Click to open full size">
                                <img src="{img_url}" 
                                     style="width: 400px; max-width: 100%; border-radius: 10px; margin-top: 0px; margin-bottom:12px;">
                            </a><br>
                            """
                            st.markdown(img_html, unsafe_allow_html=True)
                        
                        # (2) Tables
                        elif block["type"] == "table":
                            rows = fxn.fetch_page_blocks(api_key, block["id"])
                            if rows:
                                has_col_header = block["table"].get("has_column_header", False)
                                has_row_header = block["table"].get("has_row_header", False)
                                table_html = "<div style='overflow-x:auto; margin-bottom:12px;'><table style='width:100%; border-collapse:collapse; font-size:0.9em; border:1px solid #eee;'>"
                                
                                for i, row in enumerate(rows):
                                    if row["type"] == "table_row":
                                        cells = row["table_row"]["cells"]
                                        table_html += "<tr>"
                                        for j, cell in enumerate(cells):
                                            cell_html = fxn.rich_text_to_html(cell)
                                            tag = "td"
                                            bg_style = ""
                                            weight_style = ""
                                            if (i == 0 and has_col_header) or (j == 0 and has_row_header):
                                                tag = "th"
                                                bg_style = "background-color:#ccc;"
                                                weight_style = "font-weight:600;"
                                            
                                            table_html += f"<{tag} style='border:1px solid #ccc; padding:8px; {bg_style} {weight_style}'>{cell_html}</{tag}>"
                                        table_html += "</tr>"
                                table_html += "</table></div>"
                                st.markdown(table_html, unsafe_allow_html=True)
        
        # Edit Mode at the Bottom
        if edit_mode:
            with st.popover("Edit Body"):
                body_key = f"body_input_{unique_suffix}_{item['id']}"
                st.text_area(
                    "Body Content",
                    value=item["Body"] if item["Body"] else "",
                    key=body_key,
                    on_change=update_body_callback,
                    height="content",
                    args=(item["id"], body_key),
                    label_visibility="collapsed"
                )
            c1,c2 = st.columns([2,1])
            with c2:
                prio_key = f"prio_select_{unique_suffix}_{item['id']}"
                current_sel = priority if priority in ["0", "1","2", "3"] else None
                st.segmented_control(
                    "Priority",
                    options=["0", "1", "2", "3"],
                    selection_mode="single",
                    default=current_sel,
                    key=prio_key,
                    label_visibility="collapsed",
                    on_change=update_priority_callback,
                    args=(item["id"], prio_key)
                )
            with c1:
                type_key = f"type_select_{unique_suffix}_{item['id']}"
                st.multiselect(
                    "Type",
                    options=all_available_types,
                    default=item["Entry Type"],
                    key=type_key,
                    label_visibility="collapsed",
                    on_change=update_type_callback,
                    args=(item["id"], type_key),
                    placeholder="Type"
                )

# SECRETS
try:
    api_key = st.secrets["NOTION_API_KEY"]
    db_id = st.secrets["NOTION_DATABASE_ID"]
except:
    st.error("Missing secrets.toml")
    st.stop()

# MAIN INTERFACE
# [0] Inject Shortcuts
kb_shortcuts()

# [1] Top Scroll Anchor
st.markdown("<div id='top'></div>", unsafe_allow_html=True)

# [2] Scroll Logic
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

# [3] State Init
if "visible_count" not in st.session_state:
    try:
        saved_count = int(st.query_params.get("count", 30))
    except:
        saved_count = 30
    st.session_state.visible_count = saved_count
if "render_key" not in st.session_state:
    st.session_state.render_key = "init"

# [4] Fetch Data
with st.spinner("Fetching Entries..."):
    raw_entries = fxn.fetch_database_entries(api_key, db_id)
if not raw_entries:
    st.warning("No entries found.")
    st.stop()

# [5] Process Data
processed_entries = []
all_sections = set()
global_all_types = set()
for entry in raw_entries:
    p_type_raw = fxn.get_property_value(entry, "Entry Type")
    p_type = p_type_raw if isinstance(p_type_raw, list) else ([p_type_raw] if p_type_raw else [])
    
    # Collect all types for dropdown
    for t in p_type: global_all_types.add(t)

    # 1. Apply Type Overrides (Local State)
    if entry["id"] in st.session_state.type_updates:
        p_type = st.session_state.type_updates[entry["id"]]

    # 2. Apply Priority Overrides (Local State)
    if entry["id"] in st.session_state.priority_updates:
        p_prio = st.session_state.priority_updates[entry["id"]]
    else:
        p_prio = fxn.get_property_value(entry, "Priority")

    p_body = fxn.get_property_value(entry, "Body")
    sections = fxn.get_property_value(entry, "Section-RU", as_plain_text=True) or []
    refs = fxn.get_property_value(entry, "Reference-RU", as_plain_text=True) or []
    
    for s in sections: 
        all_sections.add(s)

    processed_entries.append({
        "id": entry["id"],
        "Entry Type": p_type,
        "Section": sections,
        "Reference": refs,
        "Body": p_body,
        "Priority": p_prio,
        "raw": entry,
    })
all_types_list = sorted(list(global_all_types))

# SIDEBAR
# [1] Section Filter
st.sidebar.subheader("Filter by Section")
sorted_sections = sorted(list(all_sections))
selected_sections = []
if st.sidebar.button("Reset"):
    for sec in sorted_sections: st.session_state[f"chk_{sec}"] = False
    reset_view()
if not sorted_sections:
    st.sidebar.caption("No sections found")
else:
    for sec in sorted_sections:
        key = f"chk_{sec}"
        if key not in st.session_state: st.session_state[key] = False
        if st.sidebar.checkbox(sec, key=key, on_change=reset_view):
            selected_sections.append(sec)

# [2] Reference Filter
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

# [3] Cache Refresh Button
st.sidebar.divider()
if st.sidebar.button("🔄️ Refresh Cache", help="Clear cache and fetch updates"):
    st.cache_data.clear()
    st.rerun()

# [4] Priority Edit 
edit_mode = False
admin_pass = st.sidebar.text_input("🔒 Edit Priorities", type="password", key="admin_password_input")
if "ADMIN_PASSWORD" in st.secrets and admin_pass == st.secrets["ADMIN_PASSWORD"]:
    edit_mode = st.sidebar.toggle("Enable Priority Editing", value=False)
elif admin_pass:
    st.error("Incorrect Password")


# MAIN PANEL
if "shuffle_seed" not in st.session_state: st.session_state.shuffle_seed = 0
# [1] Priority Segmented Control
with st.container(horizontal=True):
    prio_filter = st.segmented_control(
        "Priority Filter",
        options=["All", "0", "1", "2", "3", "None"],
        selection_mode="single",
        default="All",
        label_visibility="collapsed",
        on_change=reset_view
    )

# [2] Other Toggles
with st.container(horizontal=True):
    reverse_sort = st.toggle("Newest First", value=False, on_change=reset_view)
    shuffle_enabled = st.toggle("Shuffle", value=False, on_change=reset_view)
    focused_mode = st.toggle("Focused", value=False, help="One entry at a time")
if not focused_mode:
    if "focused_index" not in st.session_state: st.session_state.focused_index = 0

# [3] Search Bar + Reshuffle
with st.container(horizontal=True):
    search_query = st.text_input("Search", placeholder="Type keywords...", width=400, label_visibility="collapsed", key="search_query", on_change=reset_view)
    st.button("✖", on_click=clear_search, help="Clear Filters")
    if shuffle_enabled:
        if st.button("🎲", help="Reshuffle"):
            st.session_state.shuffle_seed += 1
            reset_view()

# [4] Pre-Filter Logic
pre_type_filtered_data = []
for item in processed_entries:
    match_section = True
    if selected_sections:
        match_section = any(s in selected_sections for s in item["Section"])
    match_ref = True
    if selected_references:
        match_ref = any(r in item["Reference"] for r in selected_references)
    match_prio = True
    if prio_filter == "None":
        if item["Priority"]: match_prio = False
    elif prio_filter and prio_filter != "All":
        p_val = item["Priority"] if item["Priority"] else "None"
        if p_val != prio_filter:
            match_prio = False
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
    if match_section and match_ref and match_prio and match_search:
        pre_type_filtered_data.append(item)

# [5] Entry Type Filters
available_entry_types = set()
for item in pre_type_filtered_data:
    for t in item["Entry Type"]: available_entry_types.add(t)
st.write("**Filter by Entry Type**")
sorted_types = sorted(list(available_entry_types))
if not sorted_types:
    st.caption("No entry types available for current filters.")
    selected_types = []
else:
    selected_types = st.pills(
        "Entry Types", sorted_types, selection_mode="multi",
        label_visibility="collapsed", on_change=reset_view, key="selected_entry_types"
    )

# [6] Final Filter Logic
filtered_data = []
for item in pre_type_filtered_data:
    match_type = True
    if selected_types:
        match_type = any(t in item["Entry Type"] for t in selected_types)
    if match_type: filtered_data.append(item)
if reverse_sort and not shuffle_enabled:
    filtered_data.reverse()
if shuffle_enabled:
    rng = random.Random(st.session_state.shuffle_seed)
    rng.shuffle(filtered_data)
total_entries = len(filtered_data)
if total_entries == 0:
    st.warning("No entries found with current filters.")
    st.stop()
list_context_id = f"{st.session_state.render_key}_{len(filtered_data)}"

# [7] DISPLAY
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
        render_entry(item, current_idx + 1, api_key=api_key, edit_mode=edit_mode, all_available_types=all_types_list, unique_suffix=f"focus_{list_context_id}")

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

else: # List Mode
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
                render_entry(item, actual_index, api_key=api_key, edit_mode=edit_mode, all_available_types=all_types_list, unique_suffix="grid")

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