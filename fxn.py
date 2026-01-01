import streamlit as st
from notion_client import Client
import re

# Helper: Initialize Client
def init_notion_client(api_key):
    return Client(auth=api_key)

# Helper: ID Formatting
def format_uuid(id_str):
    """
    Ensures the ID is in the correct 8-4-4-4-12 UUID format with dashes.
    """
    if not id_str:
        return ""
    clean = id_str.split("?")[0]
    hex_match = re.search(r'([a-fA-F0-9]{32})', clean)
    if not hex_match:
        uuid_match = re.search(r'[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}', clean)
        if uuid_match:
            return uuid_match.group(0)
        return clean.strip()
    raw = hex_match.group(1)
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

#  Helper: Plain Text Extraction
def rich_text_to_plain_text(rich_text_list):
    return "".join([t.get("plain_text", "") for t in rich_text_list])

# Helper: HTML Conversion (for tables)
def rich_text_to_html(rich_text_list):
    html_content = ""
    for text_obj in rich_text_list:
        content = ""
        if text_obj["type"] == "text":
            content = text_obj["text"]["content"]
            # escaping
            content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            annotations = text_obj.get("annotations", {})
            if annotations.get("bold"): content = f"<b>{content}</b>"
            if annotations.get("italic"): content = f"<i>{content}</i>"
            if annotations.get("strikethrough"): content = f"<s>{content}</s>"
            if annotations.get("underline"): content = f"<u>{content}</u>"
            if annotations.get("code"): content = f"<code style='background:rgba(135,131,120,0.15); color:#EB5757; padding:0.2em 0.4em; border-radius:3px; font-size:85%'>{content}</code>"
            if annotations.get("color") and annotations["color"] != "default":
                color = annotations["color"]
                if "_background" not in color:
                    content = f"<span style='color:{color}'>{content}</span>"
        elif text_obj["type"] == "equation":
            expression = text_obj["equation"]["expression"]
            content = f"<code class='katex'>{expression}</code>"
        html_content += content
    return html_content

# Helper: Richtext → Markdown
def rich_text_to_markdown(rich_text_list):
    markdown_text = ""
    for text_obj in rich_text_list:
        content = ""
        # Text
        if text_obj["type"] == "text":
            content = text_obj["text"]["content"]
            content = content.replace(">", "\>") # Escape blockquotes
            annotations = text_obj.get("annotations", {})
            if annotations.get("code"):
                if "\n" in content:
                    content = f"\n```\n{content}\n```\n"
                else:
                    content = f"`{content}`"
            else:
                content = content.replace("\n", "  \n")
                prefix = ""
                suffix = ""
                
                # Handle spacing outside annotations
                if annotations.get("bold") or annotations.get("italic") or annotations.get("strikethrough"):
                    if content.startswith(" "):
                        prefix = " "
                        content = content.lstrip()
                    if content.endswith(" "):
                        suffix = " "
                        content = content.rstrip()
                    if content.endswith("  \n"):
                        suffix = "  \n"
                        content = content[:-3]
                if annotations.get("bold"):
                    content = f"**{content}**"
                if annotations.get("italic"):
                    content = f"*{content}*"
                if annotations.get("strikethrough"):
                    content = f"~~{content}~~"
                if annotations.get("underline"):
                    content = f"<u>{content}</u>"
                content = f"{prefix}{content}{suffix}"
                
        # Equations
        elif text_obj["type"] == "equation":
            expression = text_obj["equation"]["expression"]
            content = f" $ {expression} $ "
            
        markdown_text += content
    return markdown_text

# Helper: Markdown → Notion RichText
def markdown_to_rich_text(markdown_str):
    if not markdown_str:
        return []
    pattern = re.compile(r'(\*\*.*?\*\*|`[^`]+`|<u>.*?</u>|\*[^*]+\*|\$[^$]+\$)')
    
    parts = pattern.split(markdown_str)
    rich_text = []
    
    for part in parts:
        if not part: continue
        
        # Check tokens
        if part.startswith("`") and part.endswith("`"):
            # Code
            rich_text.append({
                "type": "text",
                "text": {"content": part[1:-1]},
                "annotations": {"code": True}
            })
        elif part.startswith("$") and part.endswith("$"):
            # Equation [NEW]
            rich_text.append({
                "type": "equation",
                "equation": {"expression": part[1:-1]}
            })
        elif part.startswith("**") and part.endswith("**"):
            # Bold
            rich_text.append({
                "type": "text",
                "text": {"content": part[2:-2]},
                "annotations": {"bold": True}
            })
        elif part.startswith("<u>") and part.endswith("</u>"):
            # Underline
            rich_text.append({
                "type": "text",
                "text": {"content": part[3:-4]},
                "annotations": {"underline": True}
            })
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            # Italic
            rich_text.append({
                "type": "text",
                "text": {"content": part[1:-1]},
                "annotations": {"italic": True}
            })
        else:
            # Plain Text
            rich_text.append({
                "type": "text",
                "text": {"content": part}
            })
            
    return rich_text

# Helper: Property Extraction
def get_property_value(page, property_name, as_plain_text=False):
    props = page.get("properties", {})
    if property_name not in props:
        return None
    
    prop_data = props[property_name]
    prop_type = prop_data["type"]
    converter = rich_text_to_plain_text if as_plain_text else rich_text_to_markdown

    if prop_type == "select":
        return prop_data["select"]["name"] if prop_data["select"] else None
    elif prop_type == "multi_select":
        return [item["name"] for item in prop_data["multi_select"]]
    elif prop_type == "rich_text":
        return converter(prop_data["rich_text"])
    elif prop_type == "title":
        return converter(prop_data["title"])
    elif prop_type == "relation":
        return [rel["id"] for rel in prop_data["relation"]]
    elif prop_type == "checkbox":
        return prop_data["checkbox"]
    elif prop_type == "rollup":
        rollup = prop_data["rollup"]
        values = []
        if rollup["type"] == "array":
            for item in rollup["array"]:
                if item["type"] == "title":
                    values.append(converter(item["title"]))
                elif item["type"] == "rich_text":
                    values.append(converter(item["rich_text"])) 
        return values
    return None

@st.cache_data(persist='disk', show_spinner=False)
def fetch_database_entries(api_key, db_id):
    notion = init_notion_client(api_key)
    results = []
    has_more = True
    start_cursor = None
    clean_id = format_uuid(db_id)
    target_source_id = clean_id
    try:
        db_meta = notion.databases.retrieve(database_id=clean_id)
        data_sources = db_meta.get("data_sources", [])
        if data_sources: target_source_id = data_sources[0]["id"]
    except Exception: pass

    try:
        while has_more:
            response = notion.data_sources.query(
                data_source_id=target_source_id, start_cursor=start_cursor, page_size=100
            )
            results.extend(response["results"])
            has_more = response["has_more"]
            start_cursor = response["next_cursor"]
        
        def get_sort_key(item):
            props = item.get("properties", {})
            if "Created" in props:
                c_prop = props["Created"]
                if c_prop["type"] == "date" and c_prop["date"]: return c_prop["date"]["start"]
                elif c_prop["type"] == "created_time": return c_prop["created_time"]
            return item.get("created_time", "")
        results.sort(key=get_sort_key)
        return results
    except Exception as e:
        st.error(f"Error fetching database: {e}")
        return []

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_page_blocks(api_key, page_id):
    notion = init_notion_client(api_key)
    try:
        response = notion.blocks.children.list(block_id=page_id)
        return response["results"]
    except Exception as e:
        return []

def update_page_property(api_key, page_id, property_name, new_value, prop_type="select"):
    notion = init_notion_client(api_key)
    
    properties_payload = {}
    
    if prop_type == "select":
        properties_payload[property_name] = {
            "select": {"name": new_value} if new_value else None
        }
    elif prop_type == "multi_select":
        properties_payload[property_name] = {
            "multi_select": [{"name": val} for val in new_value]
        }
    elif prop_type == "rich_text":
        # Updated to use the new parser including equations
        rich_text_objects = markdown_to_rich_text(new_value)
        properties_payload[property_name] = {
            "rich_text": rich_text_objects
        }

    try:
        notion.pages.update(
            page_id=page_id,
            properties=properties_payload
        )
        return True
    except Exception as e:
        st.error(f"Failed to update Notion: {e}")
        return False