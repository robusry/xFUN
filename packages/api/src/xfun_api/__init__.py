"""Read-only public API.

    uvicorn xfun_api:app --reload

Reads precomputed scores from the store and applies calibration and composition,
both of which are arithmetic. It never executes a model.
"""

from .main import app

__all__ = ["app"]
