# -*- coding: utf-8 -*-
"""產生三重賣房損益對照表（含提前清償違約金與房貸壽險解約）"""
import io, json, os

# 口徑來源：vault Joan/生活/財務/三重共構宅出售損益試算.md
BASE    = 12958545   # 真實基礎投入（買價+裝修+智慧家居+買入費用−朋友補貼）
INVOICE = 76380      # 裝修開票成本 636,500 × 12%
PAYOFF  = 75000      # 提前清償違約金（合庫，第二年 0.75%）
POLICY  = 200000     # 房貸壽險解約（信貸辦的，賣房時要還清）
ACQ     = 12500000   # 房地合一取得成本
DEDUCT  = 122045     # 可認列買入費用
IMPROVE = 636500     # 可認列改良支出（裝修 536,500 + 智慧家居 100,000）
MORT    = 10000000   # 房貸餘額
LAND    = 133000     # 土增稅・代書・規費
BROKER_RATE = 0.04
TAX_RATE    = 0.45


def calc(price):
    broker = price * BROKER_RATE
    gain = max(0, price - ACQ - broker - DEDUCT - IMPROVE)
    tax = gain * TAX_RATE
    # 真實損益：把所有確定支出都算進去
    pl = price - broker - tax - INVOICE - PAYOFF - POLICY - BASE
    # 淨到手：還完房貸後實際拿到的現金
    net = price - MORT - broker - tax - INVOICE - PAYOFF - POLICY - LAND
    return {"price": price, "broker": broker, "gain": gain, "tax": tax,
            "pl": pl, "net": net}


def breakeven():
    lo, hi = 12000000, 16000000
    for _ in range(80):
        mid = (lo + hi) / 2
        if calc(mid)["pl"] < 0:
            lo = mid
        else:
            hi = mid
    return hi


def zero_tax_price():
    """課稅所得歸零的售價：P - 0.04P - ACQ - DEDUCT - IMPROVE = 0"""
    return (ACQ + DEDUCT + IMPROVE) / (1 - BROKER_RATE)


def main():
    rows = [calc(p) for p in range(13300000, 14900001, 100000)]
    be = breakeven()
    zt = zero_tax_price()

    os.makedirs("out", exist_ok=True)
    json.dump({"rows": rows, "breakeven": be, "zeroTax": zt,
               "params": {"BASE": BASE, "INVOICE": INVOICE, "PAYOFF": PAYOFF,
                          "POLICY": POLICY, "ACQ": ACQ, "DEDUCT": DEDUCT,
                          "IMPROVE": IMPROVE, "MORT": MORT, "LAND": LAND}},
              io.open("out/sell_table.json", "w", encoding="utf-8"),
              ensure_ascii=False)

    print(f"保本價（真實損益 = 0）：{be:,.0f}  約 {be/10000:.0f} 萬")
    print(f"免稅門檻（課稅所得 = 0）：{zt:,.0f}  約 {zt/10000:.0f} 萬")
    print()
    print("成交價        仲介費     房地合一稅    真實損益        淨到手")
    print("-" * 68)
    for r in rows:
        mark = "  ← 保本" if abs(r["pl"]) < 55000 else ""
        print(f"{r['price']:>11,}  {r['broker']:>9,.0f}  {r['tax']:>10,.0f}  "
              f"{r['pl']:>+11,.0f}  {r['net']:>11,.0f}{mark}")


if __name__ == "__main__":
    main()
