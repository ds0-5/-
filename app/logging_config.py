# 结构化日志：统一 logger，替代散落的 print
import logging

def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # 别刷屏
