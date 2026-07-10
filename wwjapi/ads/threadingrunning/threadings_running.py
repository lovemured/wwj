import threading
import time

from advertising.advertising import CreateAdvertising
from common.publicdata import GetRequestdata


class ThreadWorking:
    EXECUTING_ITERATIONS = 1  # 每个线程执行次数
    THREAD_COUNT = 1  # 并发线程数
    DELAY_BETWEEN_TASKS = 0.5  # 任务间隔

    def execute_task(self):
        """单个线程要执行的任务"""
        for _ in range(self.EXECUTING_ITERATIONS):
            try:
                # 执行业务逻辑
                req = GetRequestdata()
                url = req.get_url(
                    'staging',
                    '/api/v1/clues/sync?s=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJydWxlX2lkIjo0NDcsIm9yZ2FuaXphdGlvbl9pZCI6NTAwMDI4NX0.iSe9ndz9QRGI8RTX9XF1_H-3a5M3b_MAw_Nama6lJGg'
                )

                # 执行广告推送
                CreateAdvertising().baidu_advertising(url=url)

                if self.DELAY_BETWEEN_TASKS > 0:
                    time.sleep(self.DELAY_BETWEEN_TASKS)

            except Exception as e:
                print(f"⚠️ 任务执行失败：{str(e)}")

    def create_and_start_threads(self):
        """创建并启动多线程"""
        threads = []

        # 创建线程
        for _ in range(self.THREAD_COUNT):
            thread = threading.Thread(target=self.execute_task)
            threads.append(thread)
            thread.start()

        # 等待所有线程结束
        for thread in threads:
            thread.join()

        print("✅ 所有线程执行完成")


if __name__ == "__main__":
    worker = ThreadWorking()
    worker.create_and_start_threads()
