"""
Tool definitions
"""

TOOLS = [
    {
        "name": "save_document",
        "description": "Save a document to the local workspace. Use this when asked to write, draft, create, or prepare any document. The document will be saved locally - use commit_and_push afterwards to push changes to the repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path where the file should be saved relative to workspace root, e.g., 'notes/meeting-summary.md' or 'drafts/blog-post.md'. Use lowercase, hyphens, and .md or .txt extension."
                },
                "content": {
                    "type": "string",
                    "description": "The full content of the document to save."
                }
            },
            "required": ["file_path", "content"]
        }
    },
    {
        "name": "read_document",
        "description": "Read the contents of a document from the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read, e.g., 'notes/meeting-summary.md'"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "delete_document",
        "description": "Delete a document from the workspace. Use commit_and_push afterwards to push the deletion to the repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to delete, e.g., 'drafts/old-draft.md'"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "delete_folder",
        "description": "Delete a folder from the workspace. By default only deletes empty folders. Set force=true to delete a folder and all its contents. Use commit_and_push afterwards.",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder_path": {
                    "type": "string",
                    "description": "Path to the folder to delete, e.g., 'drafts/old-project'"
                },
                "force": {
                    "type": "boolean",
                    "description": "If true, delete folder even if not empty (deletes all contents). Default is false.",
                    "default": False
                }
            },
            "required": ["folder_path"]
        }
    },
    {
        "name": "rename_document",
        "description": "Rename or move a document within the workspace. Can be used to move files between folders. Use commit_and_push afterwards.",
        "input_schema": {
            "type": "object",
            "properties": {
                "old_path": {
                    "type": "string",
                    "description": "Current path of the file, e.g., 'drafts/old-name.md'"
                },
                "new_path": {
                    "type": "string",
                    "description": "New path for the file, e.g., 'published/new-name.md'"
                }
            },
            "required": ["old_path", "new_path"]
        }
    },
    {
        "name": "create_folder",
        "description": "Create a new folder in the workspace. Creates parent folders if needed. Use commit_and_push afterwards.",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder_path": {
                    "type": "string",
                    "description": "Path for the new folder, e.g., 'projects/new-project'"
                }
            },
            "required": ["folder_path"]
        }
    },
    {
        "name": "commit_and_push",
        "description": "Commit all current changes in the workspace and push to the GitHub repository. Use this after saving documents to make them available to your employer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "commit_message": {
                    "type": "string",
                    "description": "A clear, professional commit message describing the changes."
                }
            },
            "required": ["commit_message"]
        }
    },
    {
        "name": "examine_workspace",
        "description": "Examine the workspace structure. Returns all files and folders in the workspace. Use this to understand the current organization before creating, moving, or deleting files and folders.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "list_agent_core",
        "description": "List all files in your agent-core configuration repository. Use this to see what configuration files exist.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "read_agent_core",
        "description": "Read the contents of a file in your agent-core configuration repository. Use this to see your current personality, instructions, or other configuration before making changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read, e.g., 'IDENTITY.md'"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "create_agent_core",
        "description": "Create a new file in your agent-core configuration repository. Use this to add new configuration files. Changes are committed and pushed immediately.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path for the new file, e.g., 'preferences.md'"
                },
                "content": {
                    "type": "string",
                    "description": "The content for the new file"
                },
                "commit_message": {
                    "type": "string",
                    "description": "A clear commit message describing what this file is for"
                }
            },
            "required": ["file_path", "content", "commit_message"]
        }
    },
    {
        "name": "update_agent_core",
        "description": "Update an existing file in your agent-core configuration repository. Use this to modify your personality, instructions, or configuration. Changes take effect immediately. Always read the current file first before updating.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to update, e.g., 'IDENTITY.md'"
                },
                "content": {
                    "type": "string",
                    "description": "The complete new content for the file"
                },
                "commit_message": {
                    "type": "string",
                    "description": "A clear commit message describing what changed and why"
                }
            },
            "required": ["file_path", "content", "commit_message"]
        }
    }
]