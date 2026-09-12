# 配置层：所有可变配置走环境变量（.env），不写死在代码里 —— 大厂红线
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # 印库根目录

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )
    database_path: str = "data/yinku.db"  # 默认值和现在一致

    @property
    def db_path(self) -> str:
        p = Path(self.database_path)
        return str(p if p.is_absolute() else BASE_DIR / p)

settings = Settings()
