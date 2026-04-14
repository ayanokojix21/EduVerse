from gymnasium.envs.registration import register

register(
    id="EduVerse-v0",
    entry_point="app.rl.eduverse_env:EduverseEnv",
    order_enforce=False,
    disable_env_checker=True,
)
