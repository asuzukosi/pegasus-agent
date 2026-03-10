# Pegasus

<p align="center">
  <img src="https://raw.githubusercontent.com/asuzukosi/pegasus/main/assets/pegasus.png" alt="Pegasus Logo" width="300"/>
</p>

Pegasus is a terminal-first agent runtime for long-running tasks. It combines a streaming CLI, tool calling, browser control, camera capture, MCP execution, subagents, and automatic context compression in one package.

It is designed for workflows that need more than simple code generation. Pegasus can keep working across multiple turns, use tools to interact with the local machine and external systems, and continue operating even as context grows.

## Features

- terminal agent workflow with streaming responses and tool execution
- built-in file, shell, edit, web search, memory, and todo tools
- browser automation with annotated screenshots for grounded actions
- camera capture with image handoff into the next model turn
- MCP executor for listing and composing MCP tools as Python-style functions
- subagents for delegated task execution
- automatic context compression when conversation history approaches the model limit

## Installation

Install from PyPI:

```bash
pip install pegasus-ai
```

Install from source:

```bash
git clone https://github.com/asuzukosi/pegasus.git
cd pegasus
pip install -e .
```

## Requirements

- python 3.9 or newer
- an API key exposed as `API_KEY`
- optional local dependencies for advanced tools, such as a working browser environment for Playwright-based automation and a camera device for vision capture

Get an API key from [OpenRouter](https://openrouter.ai/keys).

Set your API key:

```bash
export API_KEY="sk-xxx"
```

## Quick Start

Run the CLI:

```bash
pegasus-cli
```

Run a single prompt:

```bash
pegasus-cli --message "summarize the repository structure"
```

Run Pegasus from source without installing the console script:

```bash
python main.py
```

## Basic Usage

Interactive session:

```text
$ pegasus-cli
[user]> inspect this project and explain the main runtime flow
```

Single-shot invocation:

```bash
pegasus-cli --message "list the builtin tools and explain what each one is for"
```

Switch models from inside the CLI:

```text
/model gpt-5.4
```

Useful built-in commands:

- `/help`
- `/config`
- `/model <name>`
- `/clear`
- `/exit`

## Configuration

Pegasus loads project configuration from `.pegasus/config.toml` in the current working directory.

Example MCP configuration:

```toml
[mcp_servers.hackathon_manager]
enabled = true
startup_timeout_sec = 10.0
command = "node"
args = [".pegasus/mcp_servers/hackathon_manager_server.js"]
cwd = "."

[mcp_servers.event_booking]
enabled = true
startup_timeout_sec = 10.0
command = "node"
args = [".pegasus/mcp_servers/event_booking_server.js"]
cwd = "."
```

## Examples

Ask Pegasus to inspect a codebase:

```bash
pegasus-cli --message "inspect the current project and explain how session startup works"
```

Use browser-based task execution:

```text
[user]> open a browser, go to the target site, and tell me which clickable options are visible
```

Use camera capture in a multimodal workflow:

```text
[user]> capture the camera feed for 10 seconds and describe what changed across the frames
```

Use MCP composition:

```text
[user]> list the available mcp functions, then fetch details for the sf hackathons
```

## Packaging

The published distribution name is `pegasus-ai`.

Install command:

```bash
pip install pegasus-ai
```

Python import package:

```python
import pegasus
```