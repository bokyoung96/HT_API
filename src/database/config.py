import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """Supabase 데이터베이스 연결 설정"""
    supabase_url: str
    supabase_key: str
    postgres_url: str
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """환경변수에서 설정 로드"""
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        postgres_url = os.getenv('SUPABASE_POSTGRES_URL')
        
        if not all([supabase_url, supabase_key, postgres_url]):
            raise ValueError("Supabase 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
        
        return cls(
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            postgres_url=postgres_url
        ) 