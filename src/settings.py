from os import getenv
from pydantic import Field
from pydantic_settings import BaseSettings


LOCAL = 'local'
QA = 'qa'
PRODUCTION = 'production'


class Settings(BaseSettings):
    environment: str = LOCAL
    app_name: str = Field(alias='GITHUB_REPOSITORY', default='app')
    version: str = '0.0.1'
    logger_level: str = 'INFO'
    aws_region: str = 'us-east-1'
    aws_account_id: str = '000000000000'
    
    def lambda_env_vars(self, **kwargs) -> dict[str, str]:
        env = {
            'ENVIRONMENT': self.environment,
            'APP_NAME': self.app_name,
            'VERSION': self.version,
            'LOGGER_LEVEL': self.logger_level,
        }
        env.update(kwargs)
        return env

    @property
    def resource_prefix(self) -> str:
        return f"{self.app_name}-{self.environment}-"
