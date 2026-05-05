import json
import os

from core.entities import UserScope

current_path = os.getcwd()

USER_SCOPES_SEEDS: list[UserScope] = []

with open(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_scopes.json"),
    "r",
    encoding="utf-8",
) as f:
    user_scopes = json.load(f)
    for user_scope in user_scopes:
        USER_SCOPES_SEEDS.append(UserScope(**user_scope))
