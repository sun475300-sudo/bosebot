import json
import os

faq_path = 'data/faq.json'
with open(faq_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

new_item = {
  'id': 'DOC_001_PATENT',
  'category': 'GENERAL',
  'question': '보세전시장을 특허하려면 무슨 서류를 내야해? (보세전시장 특허 신청 서류)',
  'answer': '보세전시장을 운영(특허)하시려면 관할 세관장에게 「보세전시장 운영에 관한 고시」 제6조에 따라 다음 서류를 준비해 제출하셔야 합니다:\n\n1. 특허신청서 (고시 별지 제1호 서식)\n2. 사업계획서: 박람회 등의 소재지, 면적, 건조물 형태, 전시할 물품의 종류 등을 명시\n3. 해당 보세구역 도면 및 부근 위치도\n4. 보세전시장 운영업무를 담당하는 임원의 인적사항 (이름, 주민등록번호, 등록기준지 등)\n※ 법인인 경우 법인등기부등본은 공무원이 행정정보로 확인하지만, 열람에 동의하지 않으면 직접 추가 제출해야 합니다.',
  'legal_basis': [
    '관세법 제190조',
    '보세전시장 운영에 관한 고시 제6조(특허 신청 등)'
  ],
  'notes': '국가법령정보센터(law.go.kr)에서 서식을 다운로드 하실 수 있으며 자세한 사항은 관할 세관에 문의해 주십시오.',
  'keywords': ['특허', '서류', '신청서', '사업계획서', '도면', '임원', '제출서류', '구비서류', '관세법', '고시']
}

# Check if item already exists
idx = next((i for i, item in enumerate(data['items']) if '서류' in item['question'] and '특허' in item['question']), -1)
if idx >= 0:
    data['items'][idx] = new_item
else:
    data['items'].append(new_item)

with open(faq_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('FAQ successfully updated.')
