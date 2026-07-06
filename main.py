"""가상화폐 로보어드바이저 CLI.

사용 예:
  python main.py markets                          # 거래대금 상위 코인
  python main.py price BTCUSDT                    # 현재가
  python main.py analyze BTCUSDT --interval 4h    # 지표 분석 + 매매 의견
  python main.py backtest BTCUSDT --interval 1d --candles 730 --strategy ma_rsi
  python main.py chart BTCUSDT --interval 1m      # 실시간 캔들 차트
"""
import argparse

from advisor import config
from advisor.analysis import indicators, strategy
from advisor.backtest import engine
from advisor.data import binance_client


def cmd_markets(args):
    df = binance_client.top_markets(top=args.top)
    df["price"] = df["price"].map("{:,.4g}".format)
    df["volume_24h"] = (df["volume_24h"] / 1e6).map("{:,.1f}M".format)
    print(f"\n[바이낸스 {config.QUOTE_ASSET} 마켓 거래대금 상위 {args.top}]\n")
    print(df.to_string(index=True))


def cmd_price(args):
    for symbol in args.symbols:
        p = binance_client.price(symbol)
        print(f"\n{p['symbol']}")
        print(f"  현재가     : {p['price']:,.8g} {config.QUOTE_ASSET}")
        print(f"  24h 변동   : {p['change_24h_%']:+.2f}%")
        print(f"  24h 고/저  : {p['high_24h']:,.8g} / {p['low_24h']:,.8g}")
        print(f"  24h 거래대금: {p['volume_24h'] / 1e6:,.1f}M {config.QUOTE_ASSET}")


def cmd_analyze(args):
    df = binance_client.klines(args.symbol, args.interval, limit=200)
    df = indicators.add_all(df)
    rec = strategy.recommend(df)
    last = df.iloc[-1]

    print(f"\n[{args.symbol.upper()} 분석 — {args.interval} 봉 기준]\n")
    print(f"  현재가          : {last['close']:,.8g}")
    print(f"  SMA{config.SMA_FAST}/SMA{config.SMA_SLOW} : {last['sma_fast']:,.8g} / {last['sma_slow']:,.8g}")
    print(f"  RSI({config.RSI_WINDOW})         : {last['rsi']:.1f}")
    print(f"  MACD 히스토그램  : {last['hist']:+,.6g}")
    print(f"  볼린저밴드       : {last['bb_lower']:,.8g} ~ {last['bb_upper']:,.8g}")
    print(f"\n  종합 의견: {rec['opinion']} (점수 {rec['score']:+d})")
    for r in rec["reasons"]:
        print(f"    - {r}")
    print("\n  ※ 투자 판단의 참고 자료일 뿐, 수익을 보장하지 않습니다.")


def cmd_backtest(args):
    strat_fn = strategy.STRATEGIES[args.strategy]
    print(f"\n{args.symbol.upper()} 캔들 {args.candles}개({args.interval}) 수집 중...")
    df = binance_client.klines_history(args.symbol, args.interval, total=args.candles)
    if len(df) < config.SMA_SLOW + 10:
        print(f"데이터가 부족합니다 (수집: {len(df)}개). 상장 기간이 짧은 코인일 수 있습니다.")
        return
    df = indicators.add_all(df)
    df = strat_fn(df)
    result = engine.run(df, args.symbol.upper(), args.interval)
    bh = engine.buy_and_hold_return_pct(df)

    print(f"\n[백테스트 결과 — 전략: {args.strategy}]\n")
    print(f"  기간          : {result.start:%Y-%m-%d} ~ {result.end:%Y-%m-%d} ({len(df)}캔들)")
    print(f"  시작 자본     : {result.initial_capital:,.0f} {config.QUOTE_ASSET}")
    print(f"  최종 자본     : {result.final_capital:,.0f} {config.QUOTE_ASSET}")
    print(f"  전략 수익률   : {result.total_return_pct:+.1f}%")
    print(f"  단순보유 수익률: {bh:+.1f}%  (비교 기준)")
    print(f"  최대 낙폭(MDD): {result.max_drawdown_pct:.1f}%")
    closed = [t for t in result.trades if t.pnl_pct is not None]
    print(f"  거래 횟수     : {len(result.trades)}회 (청산 완료 {len(closed)}회)")
    if result.win_rate_pct is not None:
        print(f"  승률          : {result.win_rate_pct:.0f}%")
    if closed and args.verbose:
        print("\n  개별 거래:")
        for t in closed:
            print(f"    {t.entry_time:%Y-%m-%d} 매수 {t.entry_price:,.6g} → "
                  f"{t.exit_time:%Y-%m-%d} 매도 {t.exit_price:,.6g}  ({t.pnl_pct:+.1f}%)")
    print("\n  ※ 과거 성과가 미래 수익을 보장하지 않습니다.")


def cmd_screen(args):
    from advisor.screening import screener  # 조회가 많아 지연 임포트

    print(f"\n거래대금 상위 {args.top}개 코인 평가 중 (주봉 데이터 수집)...\n")
    results = screener.screen(top=args.top)
    print(f"[장기 투자 적합도 — 생존·지위·낙폭·장기성과·추세 종합]\n")
    for s in results:
        ret4 = f"{s.ret_4y:+.0%}" if s.ret_4y is not None else "  — "
        print(f"  {s.score:+d}점  {s.symbol:12s} {s.grade:12s} "
              f"| {s.years_listed:4.1f}년차 | 고점대비 {s.dd_from_ath:+.0%} | 4년 {ret4}")
        if args.verbose:
            for r in s.reasons:
                print(f"         - {r}")
    print("\n  ※ 점수는 과거 데이터 기반 필터일 뿐, 미래 수익을 보장하지 않습니다.")


def cmd_paper(args):
    from advisor.paper import portfolio

    if args.paper_cmd == "reset":
        portfolio.reset(args.capital)
        print(f"모의투자 초기화: 가상 자본 {args.capital:,.0f} USDT")
        return
    if args.paper_cmd == "buy":
        t = portfolio.buy(args.symbol, args.usdt)
        print(f"[모의 매수] {t['symbol']} {t['qty']:.6g}개 @ {t['price']:,.6g} "
              f"(투입 {t['usdt']:,.2f} USDT, 수수료 반영)")
        return
    if args.paper_cmd == "sell":
        t = portfolio.sell(args.symbol, args.pct)
        print(f"[모의 매도] {t['symbol']} {t['qty']:.6g}개 @ {t['price']:,.6g} "
              f"(회수 {t['usdt']:,.2f} USDT, 실현손익 {t['realized_pnl_pct']:+.2f}%)")
        return
    # status
    s = portfolio.status()
    print(f"\n[모의투자 현황 — 실시간 평가]\n")
    print(f"  총자산   : {s['total_value']:,.2f} USDT ({s['total_return_pct']:+.2f}%)")
    print(f"  현금     : {s['cash']:,.2f} USDT")
    if s["holdings"]:
        print(f"\n  {'심볼':10s} {'수량':>14s} {'평단가':>12s} {'현재가':>12s} {'평가액':>10s} {'손익':>8s}")
        for h in s["holdings"]:
            print(f"  {h['symbol']:10s} {h['qty']:>14.6g} {h['avg_price']:>12,.6g} "
                  f"{h['cur_price']:>12,.6g} {h['value']:>10,.2f} {h['pnl_pct']:>+7.2f}%")
    else:
        print("  보유 코인 없음")
    if s["trades"] and args.verbose:
        print("\n  거래 내역:")
        for t in s["trades"]:
            pnl = f" ({t['realized_pnl_pct']:+.2f}%)" if t["realized_pnl_pct"] is not None else ""
            print(f"    {t['time']}  {t['side']} {t['symbol']} {t['qty']:.6g}개 "
                  f"@ {t['price']:,.6g}{pnl}")


def cmd_autotrade(args):
    from advisor.autotrade import bot

    if args.once:
        n = bot.run_once(args.symbols, args.strategy, args.interval, args.budget)
        print(f"\n1회 점검 완료 — 체결 {n}건")
    else:
        bot.run_loop(args.symbols, args.strategy, args.interval, args.poll, args.budget)


def cmd_chart(args):
    from advisor.chart import live  # matplotlib 로딩이 느려서 지연 임포트

    if args.save:
        live.snapshot(args.symbol, args.interval, args.candles, args.save)
    else:
        live.show(args.symbol, args.interval, args.candles, args.refresh)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="가상화폐 로보어드바이저 (바이낸스)")
    sub = p.add_subparsers(dest="command", required=True)

    m = sub.add_parser("markets", help="거래대금 상위 코인 목록")
    m.add_argument("--top", type=int, default=20)
    m.set_defaults(func=cmd_markets)

    pr = sub.add_parser("price", help="현재가 조회")
    pr.add_argument("symbols", nargs="+", metavar="SYMBOL")
    pr.set_defaults(func=cmd_price)

    a = sub.add_parser("analyze", help="기술 지표 분석 + 매매 의견")
    a.add_argument("symbol")
    a.add_argument("--interval", default=config.DEFAULT_INTERVAL)
    a.set_defaults(func=cmd_analyze)

    b = sub.add_parser("backtest", help="전략 백테스트")
    b.add_argument("symbol")
    b.add_argument("--interval", default=config.DEFAULT_INTERVAL)
    b.add_argument("--candles", type=int, default=config.DEFAULT_CANDLES)
    b.add_argument("--strategy", choices=sorted(strategy.STRATEGIES), default="ma_cross")
    b.add_argument("--verbose", "-v", action="store_true", help="개별 거래 내역 출력")
    b.set_defaults(func=cmd_backtest)

    s = sub.add_parser("screen", help="장기 투자 적합도 스크리닝")
    s.add_argument("--top", type=int, default=20, help="평가할 거래대금 상위 코인 수")
    s.add_argument("--verbose", "-v", action="store_true", help="평가 근거 출력")
    s.set_defaults(func=cmd_screen)

    pp = sub.add_parser("paper", help="모의투자 (실시간 시세, 가상 자본)")
    psub = pp.add_subparsers(dest="paper_cmd", required=False)
    ps = psub.add_parser("status", help="포트폴리오 현황")
    ps.add_argument("--verbose", "-v", action="store_true")
    pb = psub.add_parser("buy", help="모의 매수")
    pb.add_argument("symbol")
    pb.add_argument("usdt", type=float, help="매수 금액 (USDT)")
    pl = psub.add_parser("sell", help="모의 매도")
    pl.add_argument("symbol")
    pl.add_argument("--pct", type=float, default=100.0, help="매도 비율 %% (기본 전량)")
    pr = psub.add_parser("reset", help="초기화")
    pr.add_argument("--capital", type=float, default=config.INITIAL_CAPITAL)
    pp.set_defaults(func=cmd_paper, paper_cmd="status", verbose=False)

    at = sub.add_parser("autotrade", help="자동매매 실험 (모의투자 체결, API 키 불필요)")
    at.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"],
                    metavar="SYMBOL")
    at.add_argument("--strategy", choices=sorted(strategy.STRATEGIES), default="ma_rsi")
    at.add_argument("--interval", default="1m", help="캔들 주기 (실험은 1m 권장)")
    at.add_argument("--poll", type=float, default=30.0, help="점검 주기(초)")
    at.add_argument("--budget", type=float, default=1000.0, help="코인당 매수 예산(USDT)")
    at.add_argument("--once", action="store_true", help="1회만 점검하고 종료")
    at.set_defaults(func=cmd_autotrade)

    c = sub.add_parser("chart", help="실시간 캔들 차트")
    c.add_argument("symbol")
    c.add_argument("--interval", default="1m", help="캔들 주기 (기본 1m)")
    c.add_argument("--candles", type=int, default=120, help="표시할 캔들 수")
    c.add_argument("--refresh", type=float, default=3.0, help="갱신 주기(초)")
    c.add_argument("--save", metavar="PNG", help="창 대신 PNG 1장 저장")
    c.set_defaults(func=cmd_chart)
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
