import os


if os.getenv('ENV', 'local') == 'pro':
    from configs import env_config
    config = env_config
else:
    from configs import config
    config = config
