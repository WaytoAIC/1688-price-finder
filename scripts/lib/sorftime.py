"""sorftime 1688 接口(domain=601)薄封装。走官方 `sorftime` CLI,先 `sorftime add <名字> <API Key>` 配好鉴权。

实测配额(2026-08):名称搜 2 / 图搜 2 / 条件搜 5 / 类目树 5 / 详情 1 / SKU 1(单位:request)。
每次调用的原始响应都整份落盘——付费数据别只留在内存里。
"""
import json
import os
import re
import subprocess

QUOTA = {'ProductSearchFromName': 2, 'ProductSearchFromImage': 2, 'ProductSearch': 5,
         'CategoryTree': 5, 'ProductRequest': 1, 'ProductVariations': 1}


class SorftimeError(RuntimeError):
    pass


def call(api, payload, out_path):
    """调一次接口,原始响应写 out_path,返回 Data。失败抛 SorftimeError,不吞。"""
    cmd = ['sorftime', 'api', api, json.dumps(payload, ensure_ascii=False), '--domain', '601']
    if os.environ.get('SORFTIME_PROFILE'):
        cmd += ['--profile', os.environ['SORFTIME_PROFILE']]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        raise SorftimeError('找不到 sorftime 命令:先安装 sorftime CLI 并 `sorftime add <名字> <API Key>`')
    text = r.stdout[r.stdout.find('{'):] if '{' in r.stdout else ''
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as fp:
        fp.write(text or (r.stdout + r.stderr))
    try:
        d = json.loads(text)
    except ValueError:
        raise SorftimeError(f'{api} 返回非 JSON:{(r.stdout or r.stderr)[:200]}')
    code = d.get('Code', d.get('code'))
    if code not in (0, None):
        raise SorftimeError(f"{api} 失败(code={code}):{d.get('Message') or d.get('message')}")
    return d.get('Data')


def _f(x):
    try:
        return float(str(x).replace('¥', '').strip())
    except (TypeError, ValueError):
        return None


def tier_price(tiers, qty):
    """阶梯价 [{Price, PurchaseQuantity:'10~999个'|'≥1'}] → 买 qty 件时那一档的单价。
    取「起订下限 ≤ qty」里下限最大的一档;每档下限都高于 qty(起订量超过首单)时取第一档。"""
    best = None
    for t in tiers or []:
        p = _f(t.get('Price'))
        nums = re.findall(r'\d+', str(t.get('PurchaseQuantity') or ''))
        lo = int(nums[0]) if nums else 1
        if p and p > 0 and lo <= qty and (best is None or lo > best[0]):
            best = (lo, p)
    if best:
        return best[1]
    ps = [_f(t.get('Price')) for t in tiers or [] if (_f(t.get('Price')) or 0) > 0]
    return ps[0] if ps else None


def normalize(items, source, qty):
    """搜索结果 → 统一候选字段。没有报价(Price=0)的货盘丢掉。"""
    out = []
    for it in items if isinstance(items, list) else []:
        tiers = it.get('WholesalePriceRange') or []
        p = tier_price(tiers, qty) or _f(it.get('Price'))
        if not p or p <= 0:
            continue
        m = re.search(r'/offer/(\d+)', str(it.get('Url') or ''))
        out.append({'来源': source, 'offerId': m.group(1) if m else str(it.get('ProductId') or ''),
                    '标题': it.get('Title') or '', '价格': p, '阶梯价': tiers,
                    '起订量': it.get('MinOrderQuantity'), '近30天销量': it.get('SalesOf30d'),
                    '供应商': it.get('StoreName') or '', '发货地': it.get('ShippingOrigin') or '',
                    '链接': it.get('Url') or '', '图片': it.get('Photo') or ''})
    return out


def search_name(query, out_dir, qty):
    data = call('ProductSearchFromName', {'name': query}, os.path.join(out_dir, 'keyword-results.json'))
    return normalize(data, '文字搜', qty)


def search_image(image_url, out_dir, qty):
    """以图搜款。ImageUrl 必须是公网可访问的图片、不超过 1MB(接口限制)。"""
    data = call('ProductSearchFromImage', {'ImageUrl': image_url}, os.path.join(out_dir, 'image-results.json'))
    return normalize(data, '图搜', qty)


def search_category(node_id, out_dir, qty, min_sales=None, price_min=None, price_max=None):
    payload = {'NodeId': node_id, 'Page': 1}
    for k, v in (('Recent30DaySaleMin', min_sales), ('DropshippingPriceRangeMin', price_min),
                 ('DropshippingPriceRangeMax', price_max)):
        if v is not None:
            payload[k] = v
    data = call('ProductSearch', payload, os.path.join(out_dir, 'category-results.json'))
    return normalize(data, '类目搜', qty)


def category_tree(cache_path):
    """类目树(1.8MB,约 1.6 万节点)。第一次拉取花 5 req,之后读本地缓存。"""
    if os.path.exists(cache_path):
        with open(cache_path) as fp:
            return json.load(fp)
    data = call('CategoryTree', {}, cache_path + '.raw.json')
    tree = data if isinstance(data, list) else []
    with open(cache_path, 'w') as fp:
        json.dump(tree, fp, ensure_ascii=False)
    return tree


def find_nodes(tree, name, limit=10):
    by_id = {n['Id']: n for n in tree}

    def path_of(n):
        parts = []
        while n:
            parts.append(n['Name'])
            n = by_id.get(n.get('ParentId'))
        return ' > '.join(reversed(parts))
    hits = sorted((n for n in tree if name in n['Name']), key=lambda n: (n['Name'] != name, len(path_of(n))))
    return [(n['NodeId'], path_of(n)) for n in hits[:limit]]


def detail(offer_id, out_dir, qty):
    """详情(完整阶梯价)+ SKU(每个 SKU 的价、库存、包装尺寸重量)。各 1 req。
    部分货盘 sorftime 没收录报价(详情 Price=0、SKU 无数据),此时首单档价为 None,由调用方回落列表价。"""
    d = os.path.join(out_dir, 'offers', offer_id)
    pr = call('ProductRequest', {'ProductId': offer_id}, os.path.join(d, 'detail.json')) or {}
    try:
        pv = call('ProductVariations', {'ProductId': offer_id}, os.path.join(d, 'variations.json')) or []
    except SorftimeError:
        pv = []
    tiers = pr.get('WholesalePriceRange') or []
    skus = [s for s in pv if isinstance(s, dict)]
    sku_prices = [_f(s.get('Price')) for s in skus if (_f(s.get('Price')) or 0) > 0]
    first = next((s for s in skus if s.get('Length')), {})
    return {
        'offerId': offer_id, '标题': pr.get('Title'), '链接': f'https://detail.1688.com/offer/{offer_id}.html',
        '供应商': pr.get('StoreName'), '发货地': pr.get('ShippingOrigin'),
        '首单档价': tier_price(tiers, qty),
        '阶梯价': '; '.join(f"{t.get('Price')}@{t.get('PurchaseQuantity')}" for t in tiers),
        '起订量': pr.get('MinOrderQuantity'), '库存': pr.get('StockCount'), '近30天销量': pr.get('SalesOf30d'),
        '服务分': pr.get('ServiceScore'), '发货时效': pr.get('ShippingTime'), 'SKU数': len(skus),
        'SKU价区间': f'{min(sku_prices)}~{max(sku_prices)}' if sku_prices else None,
        'SKU明细': [{'名称': s.get('SkuName'), '价': s.get('Price'), '库存': s.get('Stock'),
                   '包装cm': f"{s.get('Length')}×{s.get('Width')}×{s.get('Height')}" if s.get('Length') else None,
                   '重量kg': s.get('Weight')} for s in skus],
        '包装cm': f"{first.get('Length')}×{first.get('Width')}×{first.get('Height')}" if first else None,
        '重量kg': first.get('Weight'), '尺寸来源': first.get('PkgSizeSource'),
    }
