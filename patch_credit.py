# -*- coding: utf-8 -*-
"""把「中信 87 萬信貸第 25 個月月繳跳增」接進月現金流與逐月模擬"""
import io

P = 'one.html'
s = io.open(P, encoding='utf-8').read()


def rep(old, new, why):
    global s
    assert s.count(old) == 1, '錨點不唯一或找不到：' + why
    s = s.replace(old, new)
    print('  ok', why)


# 1) DEF 參數
rep(
    "living:64500, newRate:2.8, grace:3, term:30,",
    "living:64500, newRate:2.8, grace:3, term:30,\n  creditJumpM:25, creditAfter:24317,",
    'DEF 加 creditJumpM / creditAfter',
)

# 2) flows：跳增後的固定支出與 C2 段
rep(
    "  var netRent = p.rent*(p.netr/100);",
    "  var netRent = p.rent*(p.netr/100);\n"
    "  var creditLate = +p.creditAfter || p.credit;",
    'flows 算 creditLate',
)
rep(
    "  var fixed = -p.myRent - p.credit - p.living;",
    "  var fixed = -p.myRent - p.credit - p.living;\n"
    "  var fixedLate = -p.myRent - creditLate - p.living;",
    'flows 算 fixedLate',
)
rep(
    "    D: p.income + netRent + fixed - amort,",
    "    C2: p.income + netRent + fixedLate - graceP,\n"
    "    D: p.income + netRent + fixedLate - amort,\n"
    "    creditLate: creditLate, creditJump: creditLate - p.credit,",
    'flows 回傳 C2 與跳增資訊',
)

# 3) 逐月模擬同步
rep(
    "    exp = p.myRent + p.living + p.credit\n"
    "        + (m < T.sellM ? p.oldLoan : 0)",
    "    exp = p.myRent + p.living\n"
    "        + (m >= p.creditJumpM ? (+p.creditAfter||p.credit) : p.credit)\n"
    "        + (m < T.sellM ? p.oldLoan : 0)",
    'simulate 逐月反映跳增',
)

# 4) 信貸列（五欄）
rep(
    '''+ "<tr><td>信貸（兩人）</td><td class='neg'>−"+n(p.credit)+"</td><td class='neg'>−"+n(p.credit)+"</td><td class='neg'>−"+n(p.credit)+"</td><td class='neg'>−"+n(p.credit)+"</td></tr>"''',
    '''+ "<tr><td>信貸（兩人）"+(fl.creditJump>0?"<br><span style='font-size:11.5px;color:var(--brick)'>中信 87 萬：前兩年月繳 9,700，第 "+p.creditJumpM+" 月起 14,317</span>":"")+"</td><td class='neg'>−"+n(p.credit)+"</td><td class='neg'>−"+n(p.credit)+"</td><td class='neg'>−"+n(p.credit)+"</td><td class='neg'>−"+n(fl.creditLate)+"</td><td class='neg'>−"+n(fl.creditLate)+"</td></tr>"''',
    '信貸列補第五欄與說明',
)

# 5) 月結餘列
rep(
    '''+ "<tr class='tot'><td>月結餘</td>"+c(fl.A)+c(fl.B)+c(fl.C)+c(fl.D)+"</tr></tbody>"''',
    '''+ "<tr class='tot'><td>月結餘</td>"+c(fl.A)+c(fl.B)+c(fl.C)+c(fl.C2)+c(fl.D)+"</tr></tbody>"''',
    '月結餘列補 C2',
)

# 6) UI 欄位
rep(
    '''    <div class="fld"><label>信貸（兩人）</label><input type="number" id="p_credit" step="1000"><span class="u">元</span></div>''',
    '''    <div class="fld"><label>信貸（兩人）</label><input type="number" id="p_credit" step="1000"><span class="u">元／月</span></div>
    <div class="fld"><label>信貸跳增後</label><input type="number" id="p_creditAfter" step="1000"><span class="u">元／月</span></div>
    <div class="fld"><label>跳增在第幾月</label><input type="number" id="p_creditJumpM" step="1"><span class="u">月</span></div>''',
    'UI 加兩個欄位',
)

# 7) 資金來源說明回正
rep(
    '''+ "<tr><td>瓊安帳上現金<br><span style='font-size:11.5px;color:var(--ink2)'>86 萬信貸＋4 萬自有</span></td><td class='pos'>"+n(W(p.cash))+"</td></tr>"''',
    '''+ "<tr><td>瓊安帳上現金<br><span style='font-size:11.5px;color:var(--ink2)'>中信信貸 87 萬扣 1 萬手續費實拿 86 萬＋4 萬自有</span></td><td class='pos'>"+n(W(p.cash))+"</td></tr>"''',
    '資金來源說明寫清楚 87 萬來源',
)

io.open(P, 'w', encoding='utf-8').write(s)
print('全部完成')
