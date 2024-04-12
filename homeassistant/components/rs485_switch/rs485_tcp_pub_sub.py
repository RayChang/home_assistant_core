"""RS485 TCP Pub/Sub."""
import asyncio
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


class RS485TcpPubSub:
    """RS485 TCP Pub/Sub."""

    def __init__(
        self, host: str, port: int, max_retry_delay: int = 60, connect_timeout: int = 10
    ) -> None:
        """初始化 RS485 TCP Pub/Sub 服務."""

        self.host = host
        self.port = port
        self.max_retry_delay = max_retry_delay  # 最大重試間隔，單位為秒
        self.connect_timeout = connect_timeout  # 連接超時時間，單位為秒
        self.connection_task = None  # 用於存儲連接任務的引用
        self.subscribers: dict[str, Any] = {}
        self.lock = asyncio.Lock()  # 增加一個鎖來控制對訂閱者列表的訪問
        self.running = False  # 增加一個運行狀態標誌
        self.writer = None  # 用於存儲當前連接的StreamWriter對象

    async def subscribe(self, callback, callback_id=None) -> None:
        """訂閱數據，必須提供 ID."""
        if callback_id is None:
            _LOGGER.error("訂閱必須包括一個唯一的ID。")
            return
        async with self.lock:  # 使用異步鎖來保護訂閱者列表的修改
            self.subscribers[callback_id] = callback
            _LOGGER.info("訂閱者: %s 已添加", callback_id)

    async def unsubscribe(self, callback_id):
        """取消訂閱，使用 ID 進行."""
        async with self.lock:
            if callback_id in self.subscribers:
                del self.subscribers[callback_id]
                _LOGGER.info("訂閱者: %s 已移除", callback_id)
            else:
                _LOGGER.info('沒有找到 ID 為"%s"的訂閱者', callback_id)

    async def _publish(self, data):
        """發布數據給所有訂閱者，並返回他們的 ID."""
        tasks = []
        async with self.lock:
            for callback_id, callback in self.subscribers.items():
                task = asyncio.create_task(callback(sub_id=callback_id, data=data))
                tasks.append(task)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for task, result in zip(tasks, results):
            if isinstance(result, Exception):
                _LOGGER.error(
                    "Exception in subscriber %s: %s", task.callback_id, result
                )

    async def _handle_connection(self):
        retry_delay = 1  # 初始重試間隔為1秒
        while self.running:
            try:
                # 使用asyncio.wait_for增加超時處理
                reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=self.connect_timeout,
                )
                _LOGGER.info("成功連接到 %s:%i", self.host, self.port)
                retry_delay = 1  # 連接成功，重置重試間隔
                try:
                    while True:
                        data = await reader.read(1024)
                        if not data:
                            _LOGGER.warning("連線被關閉，準備重新連接…")
                            break
                        await self._publish(tuple(data))
                except asyncio.CancelledError:
                    _LOGGER.info("連線被取消")
                    break
                finally:
                    self.writer.close()
                    await self.writer.wait_closed()
            except TimeoutError:
                _LOGGER.warning("連接到 %s:%i 超時", self.host, self.port)
            except Exception as e:  # pylint: disable=broad-except
                # 錯誤處理
                _LOGGER.error("連線錯誤: %s", e)
            finally:
                if self.running:  # 只有在運行狀態下才輸出重連信息
                    _LOGGER.info(
                        "嘗試重新連接到 %s:%i，等待 %i 秒…",
                        self.host,
                        self.port,
                        retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(
                        retry_delay * 2, self.max_retry_delay
                    )  # 採用指數退避策略，但不超過最大等待時間
                if self.writer:
                    self.writer.close()
                    await self.writer.wait_closed()

    async def start(self):
        """建立連線並開始接收數據."""
        if not self.running:
            self.running = True
            # 創建並啟動一個異步任務進行連接和數據接收
            self.connection_task = asyncio.create_task(self._handle_connection())
        else:
            _LOGGER.warning("連接已經建立，無需再次建立")

    async def close(self):
        """關閉當前連接並停止嘗試重連."""
        self.running = False  # 設置運行狀態為False以停止重連嘗試
        if self.connection_task and not self.connection_task.done():
            self.connection_task.cancel()
            try:
                await self.connection_task
            except asyncio.CancelledError:
                _LOGGER.info("Connection task cancelled")

        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
                _LOGGER.info("連接已關閉")
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.error("關閉連接時發生錯誤: %s", e)
        self.writer = None
