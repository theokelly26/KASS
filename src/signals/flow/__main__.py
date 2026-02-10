"""Run both flow processors (toxicity + OI divergence) when invoked as package."""
from src.signals.flow.toxicity import main
import asyncio
asyncio.run(main())
