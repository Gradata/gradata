"""
AIOS Brain SDK — Personal AI brains that compound knowledge over time.

Quick start:
    from aios_brain import Brain
    brain = Brain.init("./my-brain")
    brain.search("budget objections")
    brain.embed()
    brain.manifest()
"""

__version__ = "0.1.0"

from aios_brain.brain import Brain

__all__ = ["Brain", "__version__"]
