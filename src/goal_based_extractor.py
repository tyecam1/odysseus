# src/goal_based_extractor.py
"""
Goal-based content extraction prompt inspired by Alibaba Tongyi DeepResearch.
"""

from src import prompt_library as _prompt_lib
EXTRACTOR_SYSTEM = _prompt_lib.text("research/goal-extractor")
