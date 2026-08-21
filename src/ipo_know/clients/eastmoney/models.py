"""东方财富北交所 IPO 项目查询响应模型."""

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator


class EastmoneyIPOItem(BaseModel):
    """东方财富北交所IPO项目简要信息."""

    model_config = ConfigDict(extra='ignore')

    security_code: str  # SECURITY_CODE（股票代码）
    csrc_industry: str | None = None  # CSRC_INDUSTRY（证监会行业）

    @field_validator('csrc_industry', mode='before')
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        """空字符串转为 None."""
        if v == '':
            return None
        return v


class EastmoneyIPOResult(BaseModel):
    """东方财富查询结果容器."""

    model_config = ConfigDict(extra='ignore')

    pages: int
    count: int
    data: list[EastmoneyIPOItem]
