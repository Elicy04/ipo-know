"""深交所注册制审核项目响应模型."""

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator


class SZSEProjectItem(BaseModel):
    """深交所项目摘要."""

    model_config = ConfigDict(extra='ignore', populate_by_name=True)

    prjid: int  # 项目ID
    cmpnm: str  # 公司全称
    cmpsnm: str | None = None  # 公司简称
    csrcind: str | None = None  # 证监会行业
    prjst: str | None = None  # 项目状态（文字）
    updtdt: str | None = None  # 更新日期
    acptdt: str | None = None  # 受理日期
    board_name: str | None = Field(
        None, alias='boardName',
    )  # 板块（创业板/主板）

    @field_validator(
        'cmpsnm', 'csrcind', 'prjst', 'updtdt', 'acptdt', 'board_name',
        mode='before',
    )
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        """空字符串转为 None."""
        if v == '':
            return None
        return v


class SZSEFileItem(BaseModel):
    """深交所披露文件项."""

    model_config = ConfigDict(extra='ignore')

    dfid: int | None = None  # 文件ID
    dfnm: str | None = None  # 文件名
    dfpth: str | None = None  # 文件路径
    ddt: str | None = None  # 披露日期
    dfext: str | None = None  # 扩展名
    matnm: str | None = None  # 材料名称

    @field_validator('dfpth', mode='before')
    @classmethod
    def validate_dfpth(cls, v: object) -> object:
        """非字符串类型的 dfpth 转为 None."""
        if not isinstance(v, str):
            return None
        if v == '':
            return None
        return v

    @field_validator('dfnm', 'ddt', 'dfext', 'matnm', mode='before')
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        """空字符串转为 None."""
        if v == '':
            return None
        return v
