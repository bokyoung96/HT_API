import asyncpg
import logging
from typing import Optional, Any, Dict, List
from datetime import datetime

from .config import DatabaseConfig
from .schemas import ALL_TABLES


class DatabaseConnection:
    """Supabase PostgreSQL 데이터베이스 연결 관리자"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None
        
    async def initialize(self) -> None:
        """데이터베이스 연결 풀 초기화 및 테이블 생성"""
        try:
            # 연결 풀 생성
            self.pool = await asyncpg.create_pool(
                self.config.postgres_url,
                min_size=1,
                max_size=10,
                server_settings={
                    'jit': 'off'  # JIT 컴파일러 비활성화 (성능 최적화)
                }
            )
            
            # 테이블 생성
            await self._create_tables()
            logging.info("✅ 데이터베이스 연결 및 테이블 초기화 완료")
            
        except Exception as e:
            logging.error(f"❌ 데이터베이스 초기화 실패: {e}")
            raise
    
    async def _create_tables(self) -> None:
        """모든 테이블 생성"""
        async with self.pool.acquire() as conn:
            for table_sql in ALL_TABLES:
                await conn.execute(table_sql)
    
    async def close(self) -> None:
        """연결 풀 종료"""
        if self.pool:
            await self.pool.close()
            logging.info("🔌 데이터베이스 연결 종료")
    
    async def execute_query(self, query: str, *args) -> Any:
        """쿼리 실행 (INSERT, UPDATE, DELETE)"""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict]:
        """단일 레코드 조회"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
    
    async def fetch_all(self, query: str, *args) -> List[Dict]:
        """다중 레코드 조회"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
    
    async def health_check(self) -> bool:
        """데이터베이스 연결 상태 확인"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:
            logging.error(f"❌ 데이터베이스 헬스체크 실패: {e}")
            return False 