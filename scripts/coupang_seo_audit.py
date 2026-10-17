#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
쿠팡 상품 검색 칸 진단 — **읽기 전용**(판매자 API GET 만 · 아무것도 안 바꿈).

노대표 2026-10-17 「쇼핑몰 세션과 협업」 1단계(A 진단기). 네이버 쇼핑광고 진단(seo_audit.mjs)의 쿠팡판. 주인 = 마케팅 세션(ad-optimizer).
승인완료(노출 가능) 상품마다 검색 관련도에 드는 칸이 비었는지 센다:
  태그(API 실측 한도 10 · 3자 이상 · 상품명과 겹침) · 브랜드(GENERIC=빈칸) · 제조사 · 속성 채움 ·
  쿠팡이 노출상품명을 바꿨나(키워드 유실) · 금칙어(coupang-agent/seo_rules.json never_claim) · 상품명 길이 · 깨진 글자(U+FFFD).
부품 = coupang-agent 의 coupang_gw.calls(묶음 호출 · 지포스 경유 · 키는 지포스 밖 안 나감). 그 저장소는 안 고친다(쇼핑몰 세션 10-17 「calls 꼴은 안 바꿈」).
🔒 판정 기준 = RULES 한 곳. 태그 한도 10 = 쇼핑몰 세션 10-16 실측(15개 400 · 10개 통과 · 2자 400). Wing 화면으로 등록된 옛 상품은 20개가 들어 있기도 하다 → «초과»는 알림만.
🩸 10-17 이전 게이트웨이는 한글을 U+FFFD 로 깨뜨렸다(coupang_gw 8c62e7d 수정) — 깨진 글자 칸이 0 이어야 결과를 믿는다.

사용: python coupang_seo_audit.py [--accounts A00351801,A00979539] [--status 승인완료] [--batch 10]
      python coupang_seo_audit.py --from-json output/coupang_seo_audit_2026-10-17.json   # API 안 부르고 보고서만 다시
출력: scripts/output/coupang_seo_audit_<날짜>.md + .json
"""
import sys, os, re, json, time, argparse, datetime

CA = r'D:\0_Dotcell\coupang-agent'
OUT = os.path.join(r'D:\0_Dotcell\ad-optimizer\scripts', 'output')
P = '/v2/providers/seller_api/apis/api/v1/marketplace/seller-products'
ACCOUNT_NAME = {'A00351801': 'MD홍 본계정', 'A00979539': 'mdhong2'}
RULES = {'tag_api_max': 10, 'tag_min_len': 3, 'name_max': 50, 'attr_fill_low': 0.3}
rules = json.load(open(os.path.join(CA, 'seo_rules.json'), encoding='utf-8'))
NEVER_CLAIM = rules.get('never_claim', []); GENERIC = rules.get('generic', [])
CHECKS = [('태그 10개 미만(채울 자리 남음)', r'^태그 \d+개$'), ('태그 10개 초과(API 한도 밖 · Wing 등록?)', r'^태그 10개 초과'),
          ('태그 3자 미만', r'^태그 3자'), ('태그가 상품명 낱말과 중복', r'^태그가 상품명'),
          ('브랜드 빈칸/GENERIC', r'^브랜드'), ('제조사 빈칸', r'^제조사'), ('속성 30% 미만', r'^속성'),
          ('쿠팡이 노출상품명 변경', r'^쿠팡이'), ('상품명 50자 넘음', r'^상품명 \d+자'), ('금칙어(효능)', r'^금칙어'),
          ('일반어 태그', r'^일반어'), ('깨진 글자 U+FFFD', r'^깨진 글자'), ('상세 읽기 실패', r'^상세 읽기 실패')]

def body(x):
    b = x.get('body'); return b if isinstance(b, dict) else json.loads(b)

def words(s):
    return [w for w in re.split(r'[\s/·,\[\]()]+', s or '') if len(w) >= 2]

def compact(x):
    """상세 응답 → 진단에 필요한 칸만(저장용)."""
    it = (x.get('items') or [{}])[0]; at = it.get('attributes') or []
    return {'name': x.get('sellerProductName') or '', 'display': x.get('displayProductName') or '',
            'tags': it.get('searchTags') or [], 'brand': x.get('brand'), 'manufacture': x.get('manufacture'),
            'attr_filled': sum(1 for a in at if (a.get('attributeValueName') or '').strip()), 'attr_total': len(at),
            'attr_fffd': sum((a.get('attributeValueName') or '').count('\ufffd') for a in at),
            'category': x.get('displayCategoryCode'), 'price': it.get('salePrice'), 'delivery': x.get('deliveryMethod')}

def diagnose(r):
    """저장된 칸(compact)만으로 판정 — --from-json 재계산도 같은 길."""
    name, disp, tags = r.get('name') or '', r.get('display') or '', r.get('tags') or []
    nw = set(words(name)); issues = []
    fffd = name.count('\ufffd') + disp.count('\ufffd') + sum(t.count('\ufffd') for t in tags) + int(r.get('attr_fffd') or 0)
    if fffd: issues.append('깨진 글자 %d' % fffd)
    if len(tags) < RULES['tag_api_max']: issues.append('태그 %d개' % len(tags))
    elif len(tags) > RULES['tag_api_max']: issues.append('태그 10개 초과 %d' % len(tags))
    short = [t for t in tags if len(t) < RULES['tag_min_len']]
    if short: issues.append('태그 3자 미만 ' + ','.join(short))
    dup = [t for t in tags if t in nw]
    if dup: issues.append('태그가 상품명 낱말과 중복 %d' % len(dup))
    if (r.get('brand') or '').upper() in ('', 'GENERIC'): issues.append('브랜드 빈칸/GENERIC')
    if not (r.get('manufacture') or '').strip(): issues.append('제조사 빈칸')
    at, filled = int(r.get('attr_total') or 0), int(r.get('attr_filled') or 0)
    if at and filled / at < RULES['attr_fill_low']: issues.append('속성 %d/%d' % (filled, at))
    lost = []
    if disp and disp != name:
        lost = [w for w in words(name) if w not in disp]
        issues.append('쿠팡이 노출상품명 변경' + (' · 유실 ' + ','.join(lost[:5]) if lost else ''))
    if len(name) > RULES['name_max']: issues.append('상품명 %d자' % len(name))
    bad = [w for w in NEVER_CLAIM if w and (w in name or any(w in t for t in tags))]
    if bad: issues.append('금칙어(효능) ' + ','.join(bad[:4]))
    gen = [t for t in tags if t in GENERIC]
    if gen: issues.append('일반어 태그 ' + ','.join(gen))
    r['tag_n'] = len(tags); r['lost_words'] = lost; r['issues'] = issues
    return r

def list_all(gw, account):
    items, tok = [], None
    while True:
        q = 'vendorId={{CFG:VENDOR_ID}}&maxPerPage=50' + ('&nextToken=' + tok if tok else '')
        b = body(gw.calls([{'name': 'l', 'method': 'GET', 'path': P, 'query': q}], account=account)[0])
        items += b.get('data') or []; tok = b.get('nextToken')
        print('  %s 목록 누적 %d' % (account, len(items)), flush=True)
        if not tok: return items

def fetch(accounts, status, batch):
    sys.path.insert(0, CA); cwd = os.getcwd(); os.chdir(CA)
    import coupang_gw as gw  # noqa: E402
    os.chdir(cwd)
    rows = []
    for acc in accounts:
        prods = [p for p in list_all(gw, acc) if p.get('statusName') == status]
        print('%s %s %d개 상세 읽기…' % (acc, status, len(prods)), flush=True)
        for i in range(0, len(prods), batch):
            chunk = prods[i:i + batch]; t = time.time()
            reqs = [{'name': str(p['sellerProductId']), 'method': 'GET', 'path': P + '/%s' % p['sellerProductId'], 'query': ''} for p in chunk]
            res = {r['name']: r for r in gw.calls(reqs, account=acc)}
            for p in chunk:
                r = res.get(str(p['sellerProductId']))
                if not r or r.get('status') != 200:
                    rows.append({'account': acc, 'id': p['sellerProductId'], 'name': p.get('sellerProductName'), 'tags': [],
                                 'issues': ['상세 읽기 실패 %s' % (r or {}).get('status')]}); continue
                x = body(r); x = x.get('data') or x
                d = compact(x); d.update({'account': acc, 'id': p['sellerProductId']}); rows.append(d)
            print('  %d/%d (%.0f초)' % (min(i + batch, len(prods)), len(prods), time.time() - t), flush=True)
    return rows

def report(rows, accounts, status, base):
    for r in rows:
        if not (r.get('issues') and r['issues'][0].startswith('상세 읽기 실패')): diagnose(r)
    json.dump(rows, open(base + '.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    day = os.path.basename(base).rsplit('_', 1)[-1]
    md = ['# 쿠팡 상품 검색 칸 진단 — %s' % day, '',
          '> 읽기 전용(판매자 API). 대상 = %s 상품 %d개(%s). 기준 = RULES(태그 API 한도 10 · 3자 이상 · 상품명과 안 겹치게 · 브랜드/제조사 입력 · 속성 30%% 이상 · 금칙어 없음). 쿠팡 공식 가중치는 비공개 — 공개 2차 자료 공통값.' % (
              status, len(rows), ' · '.join('%s %d' % (ACCOUNT_NAME.get(c, c), sum(1 for r in rows if r.get('account') == c)) for c in accounts)),
          '> ⚠ 상품명·태그·속성을 고치면 전체 PUT = 승인완료→임시저장(직원 Wing 승인요청) · 연달아 PUT 하면 «요청 진행중» 400 이 몇 시간 — 상품당 한 번에, 10개씩, 노대표 승인 뒤(쇼핑몰 세션 실측 10-16).',
          '> 깨진 글자(U+FFFD) 칸이 0 이어야 이 표를 믿는다(10-17 이전 게이트웨이 버그).', '',
          '| 걸린 항목 | 상품 수 |', '|---|---|']
    for label, pat in CHECKS:
        md.append('| %s | %d |' % (label, sum(1 for r in rows if any(re.match(pat, i) for i in r.get('issues', [])))))
    md += ['', '| 계정 | ID | 상품명 | 태그 | 브랜드/제조사 | 속성 | 걸린 것 |', '|---|---|---|---|---|---|---|']
    for r in sorted(rows, key=lambda r: -len(r.get('issues', []))):
        md.append('| %s | %s | %s | %s | %s/%s | %s | %s |' % (
            ACCOUNT_NAME.get(r.get('account'), r.get('account')), r.get('id'), (r.get('name') or '').replace('|', '/')[:40],
            r.get('tag_n', len(r.get('tags') or [])), r.get('brand') or '—', r.get('manufacture') or '—',
            '%s/%s' % (r.get('attr_filled', ''), r.get('attr_total', '')), ' · '.join(r.get('issues', []))))
    open(base + '.md', 'w', encoding='utf-8').write('\n'.join(md))
    print('\n'.join(md[:22])); print('→ %s.md (%d 상품)' % (base, len(rows)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--accounts', default='A00351801,A00979539')
    ap.add_argument('--status', default='승인완료')
    ap.add_argument('--batch', type=int, default=10)
    ap.add_argument('--from-json', default='', help='저장된 결과에서 보고서만 다시(API 안 부름)')
    a = ap.parse_args(); accounts = a.accounts.split(',')
    os.makedirs(OUT, exist_ok=True)
    if a.from_json:
        rows = json.load(open(a.from_json, encoding='utf-8'))
        accounts = list(dict.fromkeys(r.get('account') for r in rows))
        base = a.from_json[:-5]
    else:
        rows = fetch(accounts, a.status, a.batch)
        base = os.path.join(OUT, 'coupang_seo_audit_' + datetime.date.today().isoformat())
    report(rows, accounts, a.status, base)

if __name__ == '__main__':
    main()
