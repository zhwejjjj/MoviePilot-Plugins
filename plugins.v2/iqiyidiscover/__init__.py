from typing import Any, List, Dict, Tuple
from cachetools import cached, TTLCache

from app import schemas
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import DiscoverSourceEventData
from app.schemas.types import ChainEventType
from app.utils.http import RequestUtils

IQIYI_CHANNEL_PARAMS = {
    "电视剧": "2",
    "电影": "1",
    "综艺": "4",
    "动漫": "5",
    "儿童": "15",
    "纪录片": "3",
}

HEADERS = {
    "User-Agent": settings.USER_AGENT,
    "Referer": "https://www.iqiyi.com",
}

class IQiyiDiscover(_PluginBase):
    plugin_name = "爱奇艺探索"
    plugin_desc = "让探索支持爱奇艺的数据浏览。"
    plugin_icon = "https://www.iqiyi.com/favicon.ico"
    plugin_version = "1.0.0"
    plugin_author = "DDSRem"
    author_url = "https://github.com/DDSRem"
    plugin_config_prefix = "iqiyidiscover_"
    plugin_order = 100
    auth_level = 1

    _enabled = False

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
        if "iqiyi.com" not in settings.SECURITY_IMAGE_DOMAINS:
            settings.SECURITY_IMAGE_DOMAINS.append("iqiyi.com")

    def get_state(self) -> bool:
        return self._enabled

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/iqiyi_discover",
                "endpoint": self.iqiyi_discover,
                "methods": ["GET"],
                "summary": "爱奇艺探索数据源",
                "description": "获取爱奇艺探索数据",
            }
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ], {"enabled": False}

    def get_page(self) -> List[dict]:
        pass

    @cached(cache=TTLCache(maxsize=32, ttl=1800))
    def __request(self, **kwargs) -> List[dict]:
        url = "https://pcw-api.iqiyi.com/search/video/v3"
        res = RequestUtils(headers=HEADERS).get_res(url, params=kwargs)
        if res is None or not res.ok:
            raise Exception(f"请求爱奇艺 API 失败：{res.text if res else '无响应'}")
        return res.json().get("data", {}).get("list", [])

    def iqiyi_discover(
        self,
        mtype: str = "电视剧",
        page: int = 1,
        count: int = 20,
    ) -> List[schemas.MediaInfo]:
        def __to_media(item: dict) -> schemas.MediaInfo:
            return schemas.MediaInfo(
                type=mtype,
                title=item.get("albumName"),
                year=item.get("year"),
                title_year=f"{item.get('albumName')} ({item.get('year')})",
                mediaid_prefix="iqiyi",
                media_id=str(item.get("albumId")),
                poster_path=item.get("imageUrl"),
            )

        try:
            params = {
                "channel_id": IQIYI_CHANNEL_PARAMS[mtype],
                "mode": "11",  # 推荐排序
                "pageNum": page,
                "pageSize": count,
            }
            result = self.__request(**params)
        except Exception as e:
            logger.error(str(e))
            return []
        return [__to_media(r) for r in result]

    @staticmethod
    def iqiyi_filter_ui() -> List[dict]:
        mtype_ui = [
            {
                "component": "VChip",
                "props": {"filter": True, "tile": True, "value": key},
                "text": key,
            }
            for key in IQIYI_CHANNEL_PARAMS
        ]
        return [
            {
                "component": "div",
                "props": {"class": "flex justify-start items-center"},
                "content": [
                    {
                        "component": "div",
                        "props": {"class": "mr-5"},
                        "content": [{"component": "VLabel", "text": "种类"}],
                    },
                    {
                        "component": "VChipGroup",
                        "props": {"model": "mtype"},
                        "content": mtype_ui,
                    },
                ],
            },
        ]

    @eventmanager.register(ChainEventType.DiscoverSource)
    def discover_source(self, event: Event):
        if not self._enabled:
            return
        event_data: DiscoverSourceEventData = event.event_data
        iqiyi_source = schemas.DiscoverMediaSource(
            name="爱奇艺",
            mediaid_prefix="iqiyidiscover",
            api_path=f"plugin/IQiyiDiscover/iqiyi_discover?apikey={settings.API_TOKEN}",
            filter_params={"mtype": "电视剧"},
            filter_ui=self.iqiyi_filter_ui(),
            depends={"mtype": []},
        )
        if not event_data.extra_sources:
            event_data.extra_sources = [iqiyi_source]
        else:
            event_data.extra_sources.append(iqiyi_source)

    def stop_service(self):
        pass
