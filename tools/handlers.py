"""
Tool Handlers
"""

import json

def handle_save_document(workspace, file_path: str, content: str) -> str:
    """Handle the save_document tool call."""
    print(f"    -> Saving document: {file_path}")
    result = workspace.save_document(
        file_path=file_path,
        content=content
    )
    if not result.get("success"):
        print(f"    !! Error: {result.get('error')}")
    return json.dumps(result)

def handle_read_document(workspace, file_path: str) -> str:
    """Handle the read_document tool call."""
    print(f"    -> Reading document: {file_path}")
    result = workspace.read_document(file_path=file_path)
    if not result.get("success"):
        print(f"    !! Error: {result.get('error')}")
    return json.dumps(result)


def handle_delete_document(workspace, file_path: str) -> str:
    """Handle the delete_document tool call."""
    print(f"    -> Deleting document: {file_path}")
    result = workspace.delete_document(file_path=file_path)
    if not result.get("success"):
        print(f"    !! Error: {result.get('error')}")
    return json.dumps(result)


def handle_delete_folder(workspace, folder_path: str, force: bool = False) -> str:
    """Handle the delete_folder tool call."""
    print(f"    -> Deleting folder: {folder_path} (force={force})")
    result = workspace.delete_folder(folder_path=folder_path, force=force)
    if not result.get("success"):
        print(f"    !! Error: {result.get('error')}")
    return json.dumps(result)


def handle_rename_document(workspace, old_path: str, new_path: str) -> str:
    """Handle the rename_document tool call."""
    print(f"    -> Renaming document: {old_path} -> {new_path}")
    result = workspace.rename_document(old_path=old_path, new_path=new_path)
    if not result.get("success"):
        print(f"    !! Error: {result.get('error')}")
    return json.dumps(result)


def handle_create_folder(workspace, folder_path: str) -> str:
    """Handle the create_folder tool call."""
    print(f"    -> Creating folder: {folder_path}")
    result = workspace.create_folder(folder_path=folder_path)
    if not result.get("success"):
        print(f"    !! Error: {result.get('error')}")
    return json.dumps(result)

def handle_commit_and_push(workspace, commit_message: str) -> str:
    """Handle the commit_and_push tool call."""
    print(f"    -> Committing and pushing: {commit_message}")
    result = workspace.commit_and_push(
        commit_message=commit_message
    )
    if result.get("success"):
        print(f"    -> {result.get('action')}: {result.get('message')}")
    else:
        print(f"    !! Error: {result.get('error')}")
    return json.dumps(result)


def handle_examine_workspace(workspace) -> str:
    """Handle the examine_workspace tool call."""
    print(f"    -> Examining workspace")
    result = workspace.examine_workspace()
    return json.dumps(result)


def handle_list_agent_core(agent_core) -> str:
    """Handle the list_agent_core tool call."""
    print(f"    -> Listing agent-core files")
    result = agent_core.list_files()
    return json.dumps(result)


def handle_read_agent_core(agent_core, file_path: str) -> str:
    """Handle the read_agent_core tool call."""
    print(f"    -> Reading agent-core file: {file_path}")
    result = agent_core.read_file(file_path)
    return json.dumps(result)


def handle_create_agent_core(agent_core, file_path: str, content: str, commit_message: str) -> str:
    """Handle the create_agent_core tool call."""
    print(f"    -> Creating agent-core file: {file_path}")
    result = agent_core.create_file(
        file_path=file_path,
        content=content,
        commit_message=commit_message
    )
    return json.dumps(result)


def handle_update_agent_core(agent_core, file_path: str, content: str, commit_message: str) -> str:
    """Handle the update_agent_core tool call."""
    print(f"    -> Updating agent-core file: {file_path}")
    result = agent_core.update_file(
        file_path=file_path,
        content=content,
        commit_message=commit_message
    )
    return json.dumps(result)


def handle_tool_call(tool_name: str, tool_input: dict, services: dict) -> str:
    """
    Route a tool call to its handler.

    Args:
        tool_name: Name of the tool to call
        tool_input: Parameters for the tool
        services: Dict of available services (workspace, agent_core, etc.)
    """
    workspace = services.get("workspace")
    agent_core = services.get("agent_core")

    if tool_name == "save_document":
        return handle_save_document(
            workspace,
            file_path=tool_input["file_path"],
            content=tool_input["content"]
        )
        
    elif tool_name == "read_document":
        return handle_read_document(
            workspace,
            file_path=tool_input["file_path"]
        )

    elif tool_name == "delete_document":
        return handle_delete_document(
            workspace,
            file_path=tool_input["file_path"]
        )

    elif tool_name == "delete_folder":
        return handle_delete_folder(
            workspace,
            folder_path=tool_input["folder_path"],
            force=tool_input.get("force", False)
        )

    elif tool_name == "rename_document":
        return handle_rename_document(
            workspace,
            old_path=tool_input["old_path"],
            new_path=tool_input["new_path"]
        )

    elif tool_name == "create_folder":
        return handle_create_folder(
            workspace,
            folder_path=tool_input["folder_path"]
        )

    elif tool_name == "commit_and_push":
        return handle_commit_and_push(
            workspace,
            commit_message=tool_input["commit_message"]
        )
    
    elif tool_name == "examine_workspace":
        return handle_examine_workspace(workspace)

    elif tool_name == "list_agent_core":
        return handle_list_agent_core(agent_core)

    elif tool_name == "read_agent_core":
        return handle_read_agent_core(
            agent_core,
            file_path=tool_input["file_path"]
        )

    elif tool_name == "create_agent_core":
        return handle_create_agent_core(
            agent_core,
            file_path=tool_input["file_path"],
            content=tool_input["content"],
            commit_message=tool_input["commit_message"]
        )

    elif tool_name == "update_agent_core":
        return handle_update_agent_core(
            agent_core,
            file_path=tool_input["file_path"],
            content=tool_input["content"],
            commit_message=tool_input["commit_message"]
        )

    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})