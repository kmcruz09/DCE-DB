import streamlit as st
from notion_client import Client
import re

# Helper: Initialize Client
def init_notion_client(api_key):
    """Initialize the Notion Client."""
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
    """
    Extracts plain text from Notion rich_text objects, ignoring annotations.
    """
    return "".join([t.get("plain_text", "") for t in rich_text_list])

# Helper: Markdown Conversion
def rich_text_to_markdown(rich_text_list):
    """
    Parses Notion rich_text objects into Markdown.
    """
    markdown_text = ""
    for text_obj in rich_text_list:
        content = ""
        
        # Handle Text
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
                
                content = f"{prefix}{content}{suffix}"
                
        # Handle Equations
        elif text_obj["type"] == "equation":
            expression = text_obj["equation"]["expression"]
            content = f" $ {expression} $ "
            
        markdown_text += content

    return markdown_text

# Helper: Property Extraction
def get_property_value(page, property_name, as_plain_text=False):
    """
    Safe extraction of property values based on Notion types.
    Supports Rollups and allows forcing plain text output.
    """
    props = page.get("properties", {})
    if property_name not in props:
        return None
    
    prop_data = props[property_name]
    prop_type = prop_data["type"]
    
    # Determine which converter to use
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

# --- Cached Data Functions ---

@st.cache_data(ttl=3600, persist='disk', show_spinner="Fetching Database...")
def fetch_database_entries(api_key, db_id):
    """
    Fetches entries using the new Data Source API workflow (v2025).
    Cached for 1 hour to improve performance.
    """
    notion = init_notion_client(api_key)
    results = []
    has_more = True
    start_cursor = None
    
    clean_id = format_uuid(db_id)
    target_source_id = clean_id

    # 1. Resolve Data Source ID from Database Container
    try:
        db_meta = notion.databases.retrieve(database_id=clean_id)
        data_sources = db_meta.get("data_sources", [])
        if data_sources:
            target_source_id = data_sources[0]["id"]
    except Exception:
        pass

    # 2. Query Data Source
    try:
        while has_more:
            response = notion.data_sources.query(
                data_source_id=target_source_id,
                start_cursor=start_cursor,
                page_size=100
            )

            results.extend(response["results"])
            has_more = response["has_more"]
            start_cursor = response["next_cursor"]
        return results
    except Exception as e:
        st.error(f"Error fetching database: {e}")
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_page_blocks(api_key, page_id):
    """
    Fetches the children blocks of a page (to find images).
    """
    notion = init_notion_client(api_key)
    try:
        response = notion.blocks.children.list(block_id=page_id)
        return response["results"]
    except Exception as e:
        return []