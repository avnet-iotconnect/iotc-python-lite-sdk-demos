from .base import Mode

__all__ = ["Mode", "make_mode"]


def make_mode(name: str) -> Mode:
    if name == "asl":
        from .asl import ASLMode
        return ASLMode()
    if name == "ball":
        from .ball_follow import BallFollowMode
        return BallFollowMode()
    raise ValueError(f"Unknown mode: {name}")
