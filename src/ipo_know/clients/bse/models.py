"""北交所 IPO 项目审核信息披露响应模型."""

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator


class BSEProjectItem(BaseModel):
    """北交所项目摘要（来自 infoResult.do）.

    Attributes:
        id: 项目 ID.
        stock_code: 股票代码.
        stock_name: 股票简称.
        company_name: 公司全称.
        status: 审核状态编码.
        register_address: 注册地址.
        update_date: 最后更新日期 (YYYY-MM-DD).
        receive_date: 受理日期 (YYYY-MM-DD).
    """

    model_config = ConfigDict(extra='ignore')

    id: int
    stock_code: str
    stock_name: str | None = None
    company_name: str | None = None
    status: str | None = None
    register_address: str | None = None
    update_date: str | None = None
    receive_date: str | None = None

    @field_validator(
        'stock_name', 'company_name', 'status',
        'register_address', 'update_date', 'receive_date',
        mode='before',
    )
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        """空字符串统一转为 None."""
        if v == '':
            return None
        return v


class BSEFileItem(BaseModel):
    """北交所披露文件项.

    Attributes:
        dest_file_path: 文件相对路径 (用于拼接下载 URL).
        disclosure_title: 披露标题.
        disclosure_type: 披露类型编码.
        publish_date: 发布日期 (YYYY-MM-DD).
        up_date: 上传日期 (YYYY-MM-DD).
        file_ext: 文件扩展名.
    """

    model_config = ConfigDict(extra='ignore')

    dest_file_path: str
    disclosure_title: str | None = None
    disclosure_type: str | None = None
    publish_date: str | None = None
    up_date: str | None = None
    file_ext: str | None = None

    @field_validator(
        'disclosure_title', 'disclosure_type',
        'publish_date', 'up_date', 'file_ext',
        mode='before',
    )
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        """空字符串统一转为 None."""
        if v == '':
            return None
        return v
