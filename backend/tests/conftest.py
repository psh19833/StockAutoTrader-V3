"""pytest 설정: backend/를 PYTHONPATH에 추가"""
import sys
from pathlib import Path

# backend/ 디렉토리를 sys.path에 추가하여 'kis' 모듈을 import 가능하게 함
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))