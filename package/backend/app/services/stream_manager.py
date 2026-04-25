import asyncio
from typing import Dict, List, Any
import json
from asyncio import Queue

class StreamManager:
    """流式响应管理器"""
    
    def __init__(self):
        # session_id -> List[Queue]
        self.connections: Dict[str, List[Queue]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, session_id: str) -> Queue:
        """建立连接"""
        async with self._lock:
            if session_id not in self.connections:
                self.connections[session_id] = []
            
            queue = Queue()
            self.connections[session_id].append(queue)
            return queue
    
    async def disconnect(self, session_id: str, queue: Queue):
        """断开连接"""
        async with self._lock:
            if session_id in self.connections:
                if queue in self.connections[session_id]:
                    self.connections[session_id].remove(queue)
                
                if not self.connections[session_id]:
                    del self.connections[session_id]

    async def broadcast(self, session_id: str, data: Dict[str, Any]):
        """广播消息给指定会话的所有连接"""
        # 不加锁以避免阻塞，只在读取连接列表时加锁（如果需要严格一致性，但这里为了性能可以放宽）
        # 使用副本进行迭代
        queues = []
        async with self._lock:
            if session_id in self.connections:
                queues = list(self.connections[session_id])
        
        if not queues:
            # 只记录非 content 类型的消息，避免刷屏
            if data.get('type') != 'content':
                print(f"[STREAM WARNING] No active connections for session {session_id}, message type: {data.get('type')}", flush=True)
            return

        message = f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        
        # 只记录非 content 类型的消息，避免刷屏
        if data.get('type') != 'content':
            print(f"[STREAM BROADCAST] Session: {session_id}, Type: {data.get('type')}, Connections: {len(queues)}", flush=True)
        
        failed_queues = []
        for queue in queues:
            try:
                # 使用 put_nowait 避免阻塞
                queue.put_nowait(message)
            except asyncio.QueueFull:
                print(f"[STREAM ERROR] Queue full for session {session_id}, dropping message", flush=True)
                failed_queues.append(queue)
            except Exception as e:
                print(f"[STREAM ERROR] Failed to push to queue: {e}", flush=True)
                failed_queues.append(queue)
        
        # 清理失败的队列
        if failed_queues:
            async with self._lock:
                for failed_queue in failed_queues:
                    if session_id in self.connections and failed_queue in self.connections[session_id]:
                        self.connections[session_id].remove(failed_queue)

# 全局实例
stream_manager = StreamManager()