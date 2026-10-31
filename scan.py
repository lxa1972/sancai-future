import akshare as ak
import pandas as pd
import math

#====================配置区 按你的宪章V1.5====================
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL =9
MAX_MARGIN = 10000 #单手保证金上限
MIN_OPEN_INTEREST = 100000 #持仓>10万手
EXCHANGE_FILTER = ["SHFE","DCE","CZCE","GFEX","INE"]
#排除：AU AG SC 股指国债
BLACK_LIST = ["AU","AG","SC"]
#============================================================

def calc_macd(df,fast=12,slow=26,signal=9):
    ema_fast = df["close"].ewm(span=fast,adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow,adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal,adjust=False).mean()
    macd_bar = (dif-dea)*2
    df["dif"]=dif
    df["dea"]=dea
    df["macd_bar"]=macd_bar
    return df

def get_main_contract(exchange):
    df = ak.futures_main_sina(exchange=exchange)
    res=[]
    for _,row in df.iterrows():
        sym = row["symbol"]
        short_sym = sym[:-4]
        if short_sym in BLACK_LIST:
            continue
        oi = float(row["open_interest"])
        if oi <= MIN_OPEN_INTEREST:
            continue
        price = float(row["current_price"])
        multi = float(row["margin_multiplier"])
        margin = price * multi * 0.1
        if margin >= MAX_MARGIN:
            continue
        res.append({
            "symbol":sym,
            "short":short_sym,
            "exchange":exchange,
            "price":price,
            "margin":margin,
            "oi":oi
        })
    return res

def check_daily_week_macd(symbol):
    df_day = ak.futures_zh_minute_sina(symbol=symbol,period="day")
    df_day = calc_macd(df_day)
    day_dif,day_dea = df_day.iloc[-1]["dif"],df_day.iloc[-1]["dea"]
    df_wk = ak.futures_zh_minute_sina(symbol=symbol,period="week")
    df_wk = calc_macd(df_wk)
    wk_dif,wk_dea = df_wk.iloc[-1]["dif"],df_wk.iloc[-1]["dea"]
    long_ok = (day_dif>day_dea) and (wk_dif>wk_dea)
    short_ok = (day_dif<day_dea) and (wk_dif<wk_dea)
    return long_ok,short_ok,df_day,df_wk

def scan_60min(symbol):
    df60 = ak.futures_zh_minute_sina(symbol=symbol,period="60")
    df60 = calc_macd(df60)
    df60 = df60.dropna()
    cross = []
    for i in range(1,len(df60)):
        pre_dif,pre_dea = df60.iloc[i-1]["dif"],df60.iloc[i-1]["dea"]
        now_dif,now_dea = df60.iloc[i]["dif"],df60.iloc[i]["dea"]
        #金叉
        if pre_dif <= pre_dea and now_dif>now_dea:
            cross.append({"type":"long_cross","idx":i})
        #死叉
        if pre_dif >= pre_dea and now_dif<now_dea:
            cross.append({"type":"short_cross","idx":i})
    if len(cross)==0:
        return None,df60
    last_cross = cross[-1]
    cross_idx = last_cross["idx"]
    age = len(df60)-1 - cross_idx
    max_bar = df60["macd_bar"].abs().rolling(30).max().iloc[-1]
    curr_bar = df60.iloc[-1]["macd_bar"]
    bar_ratio = abs(curr_bar)/max_bar *100 if max_bar !=0 else 0
    return {"cross_type":last_cross["type"],"age":age,"bar_ratio":bar_ratio,"df":df60},df60

def run_scan():
    xianGu = []
    qiXianFeng = []
    dengXianTai = []
    warnPool = []
    for ex in EXCHANGE_FILTER:
        contracts = get_main_contract(ex)
        for c in contracts:
            sym = c["symbol"]
            long_ok,short_ok,_,_ = check_daily_week_macd(sym)
            if not long_ok and not short_ok:
                continue
            res60,df60 = scan_60min(sym)
            if res60 is None:
                xianGu.append(f'{c["short"]} 日周同向，无60分新叉')
                continue
            age = res60["age"]
            bar_ratio = res60["bar_ratio"]
            ctype = res60["cross_type"]
            if age >=5:
                xianGu.append(f'{c["short"]} 旧叉入寻仙谷')
                continue
            if age ==0:
                qiXianFeng.append(f'{c["short"]} {ctype} 第1根，观察池')
            elif 1<=age <=3:
                if bar_ratio >=30:
                    dengXianTai.append(f'{c["short"]} {ctype} 第{age+1}根，柱位{bar_ratio:.1f}%')
                else:
                    qiXianFeng.append(f'{c["short"]} 柱不足30%，栖仙峰')
            else:
                warnPool.append(f'{c["short"]} 反向叉警示')
    print("====寻仙谷·母池====")
    for i in xianGu:print(i)
    print("\n====栖仙峰·观察池====")
    for i in qiXianFeng:print(i)
    print("\n====登仙台·下单池====")
    for i in dengXianTai:print(i)
    print("\n====警示池 反向叉清仓====")
    for i in warnPool:print(i)

if __name__=="__main__":
    run_scan()
