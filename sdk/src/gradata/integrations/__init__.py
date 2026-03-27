"""
Framework Integrations — Be everywhere.
========================================
Stolen from: Mem0's integration blitz strategy.

Thin adapters that connect the brain to popular AI frameworks.
Each integration adds behavioral adaptation to the framework
with minimal configuration.

Supported frameworks:
    - OpenAI (chat completions API)
    - Anthropic (messages API)
    - LangChain (memory + callbacks)
    - CrewAI (agent memory)
    - Generic (any framework with request/response pattern)

Usage:
    # OpenAI
    from gradata.integrations.openai import patch_openai
    client = patch_openai(openai_client, brain_dir="./my-brain")

    # Anthropic
    from gradata.integrations.anthropic import patch_anthropic
    client = patch_anthropic(anthropic_client, brain_dir="./my-brain")

    # LangChain
    from gradata.integrations.langchain import BrainMemory
    memory = BrainMemory(brain_dir="./my-brain")

    # CrewAI
    from gradata.integrations.crewai import BrainCrewMemory
    crew = Crew(memory=BrainCrewMemory(brain_dir="./my-brain"))
"""
