"""
Azure AI Foundry Agent integration.

Calls the Foundry agent with telemetry data and returns coaching feedback.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("f1dashboard.foundry")


def call_foundry_agent(telemetry_content: str, config: Dict[str, Any]) -> str:
    """Call the Azure Foundry agent using the AI Projects SDK."""
    foundry_cfg = config.get("foundry", {})
    endpoint = foundry_cfg.get("endpoint", "")
    agent_name = foundry_cfg.get("agent_name", "")
    agent_version = foundry_cfg.get("agent_version", "1")

    if not endpoint or not agent_name:
        return "Foundry agent not configured. Check config.yaml [foundry] section."

    try:
        from azure.identity import DefaultAzureCredential
        from azure.ai.projects import AIProjectClient
    except ImportError as e:
        return f"Azure AI SDK import failed: {e}. Run: pip install azure-ai-projects>=2.0.0 azure-identity"

    try:
        project_client = AIProjectClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
        )

        openai_client = project_client.get_openai_client()

        message_content = (
            "Analyze this F1 telemetry session data and provide brief racing feedback "
            "(driving tips, braking points, throttle application, tyre management). "
            "Keep it concise (3-4 sentences max) for voice readout:\n\n"
            + telemetry_content
        )

        response = openai_client.responses.create(
            input=[{"role": "user", "content": message_content}],
            extra_body={
                "agent_reference": {
                    "name": agent_name,
                    "version": agent_version,
                    "type": "agent_reference",
                }
            },
        )

        return response.output_text or "No response from agent."

    except Exception as e:
        logger.error("Agent call failed: %s", e)
        return f"Agent call failed: {e}"


def collect_session_data(recorder, telemetry_state: Dict[str, Any]) -> str:
    """Collect the latest session telemetry data for the agent."""
    try:
        data_lines = []

        # Check for JSONL append file from current session
        if recorder._session_file:
            append_file = recorder._session_file.with_suffix(".jsonl")
            if append_file.exists():
                with open(append_file, "r") as f:
                    data_lines = f.readlines()

        # Snapshot unflushed samples
        samples_copy = list(recorder._samples)
        for sample in samples_copy:
            data_lines.append(json.dumps(sample, separators=(",", ":")) + "\n")

        # If no current session data, read the most recent session JSON file
        if not data_lines and recorder.data_dir.exists():
            json_files = sorted(recorder.data_dir.glob("session_*.json"), reverse=True)
            if json_files:
                with open(json_files[0], "r") as f:
                    session_data = json.load(f)
                samples = session_data.get("samples", [])
                max_samples = 200
                if len(samples) > max_samples:
                    step = len(samples) // max_samples
                    samples = samples[::step][:max_samples]
                for sample in samples:
                    data_lines.append(json.dumps(sample, separators=(",", ":")) + "\n")

        if not data_lines:
            return json.dumps(telemetry_state, indent=2, default=str)

        # Limit to N samples for token limits
        max_lines = 200
        if len(data_lines) > max_lines:
            step = len(data_lines) // max_lines
            data_lines = data_lines[::step][:max_lines]

        return "".join(data_lines)
    except Exception as e:
        logger.error("collect_session_data error: %s", e)
        return json.dumps(telemetry_state, indent=2, default=str)
