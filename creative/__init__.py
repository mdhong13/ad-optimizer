"""
Creative 생성 모듈 — 카피/이미지/영상 생성 라우터.

원칙:
  - 이미지·영상은 항상 최상위 모델 고정 (models.py 참조).
  - 카피는 Claude 기본, 사용자가 UI에서 provider 선택 가능.
  - 바이링규얼 생성 시 번역이 아닌 독립 작성 (prompts/copy_bilingual.txt).
"""
