#!/usr/bin/python3
import numpy as np
import websocket
import time
import json
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timezone, timedelta
import dateutil, calendar
import matplotlib.pyplot as plt
from telethon import TelegramClient
import requests
from tapy import Indicators
import plotly.offline as py
import plotly.tools as tls
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from EMA28Fractal import EMA_14_28
import ClientConsole as cc

# telegram bot channel
botToken = 'XXXXXXX'
gchatId = 'XXXXXXX'

try:
    import thread
except ImportError:
    import _thread as thread

f = open("webSocketTester.log", "a")

pd.set_option("display.precision", 12)

df = pd.DataFrame(columns=['Datetime','rate', 'precision', 'repeat', 'ask', 'created_at','bid', 'ric','spread','volume'])
newdf = pd.DataFrame(columns=['Datetime','rate', 'precision', 'repeat', 'ask', 'created_at','bid', 'ric','spread','volume'])

timezone_offset = +7.0  # Pacific Standard Time (UTC−08:00)
tzinfo = timezone(timedelta(hours=timezone_offset))

pesan_sell_lama = ""
pesan_buy_lama = ""

msg_sell_adx = ""
msg_buy_adx = ""

last_buy_val = 0
last_sell_val = 0
aa = 0
msg = ""
pcounter = 0
ccounter = 0
hcounter = 0
dev_counter = 0
counter_ping = 300
timeleft = 0

loop_socket = 20

last_signal = ""
val_signal = 0
waktu_lalu = ""
last_signal_code = ""
reformatted_data = []

win_status = False
latest_balance = 0
cycle = 1
last_amount = 0

maxlow = []
maxhigh = []
timex = ""

def on_message(ws, message):
    global df, timex
    try:    
        msg = json.loads(message)    
        if msg["data"][0]["assets"]:
            timex = int(msg["data"][0]["assets"][0]["created_at"].split(":")[-1].split(".")[0])
            data = msg["data"][0]["assets"][0]
            strdate = data['created_at']
            ctgl = dateutil.parser.parse(strdate)
            utc_time = calendar.timegm(ctgl.utctimetuple())
            udate = datetime.utcfromtimestamp(utc_time).strftime('%Y-%m-%d %H:%M:%S')
            data["Datetime"] = udate
            data["spread"] = (data["ask"] - data["bid"]) * (10**8)
            djs = pd.DataFrame(data, columns=['Datetime','precision','repeat','rate','ask','bid','created_at','ric','spread'], index=[0]).rename_axis(columns='Datetime')        
            if df.empty:
                df = pd.concat([djs], ignore_index=True)
            else:
                df = pd.concat([df,djs], ignore_index=True)
    except:
        ws = websocket.WebSocketApp("wss://as.binomo.com/",
                                  on_message = on_message,
                                  on_error = on_error,
                                  on_close = on_close,
                                  on_ping=on_ping,
                                  on_pong=on_pong
                                  )
        ws.on_open = on_open

    process_om(df)

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("### closed ###")

def on_open(ws):
    def run(*args):
        ws.send("subscribe:Z-CRY/IDX")
    thread.start_new_thread(run, ())

def on_ping(ws, message):
    print(f'{str(datetime.now())}   ### Got a Ping! ###')

def on_pong(ws, message):
    global counter_ping
    print(f'{str(datetime.now())}   ### Send a Pong! ###')
    #ws.send("ping")    
    counter_ping = counter_ping + 1
    if counter_ping % 100 == 0:
        ws.send('{"topic":"asset:Z-CRY/IDX","event":"ping","payload":{},"ref":"' +str(counter_ping) + '","join_ref":"28"}')


def process_om(data):    
    global loop_socket

    loop_socket+=1

    dtt = datetime.now(tzinfo)
    wibtime = dtt.strftime('%H:%M')
    charttime = dtt.strftime('%Y-%m-%d %H:%M')

    data.index = pd.to_datetime(data.Datetime)
    grouped = data.groupby('ric')    
    curprice =  grouped['rate'].resample('1Min').ohlc()
    res5m =  grouped['rate'].resample('5Min').ohlc()
    volume =  grouped['rate'].resample('1Min').count()
    spread = grouped['spread'].resample('1Min').sum()

    df2 = pd.concat([curprice, volume, spread], axis=1, keys=['Rate', 'Volume', 'Spread'])
    #dg = grouped.get_group('ric')('Rate')    
    dvolume = pd.DataFrame(curprice,columns=['high','low','open','close'])
    
    #data 5 menit
    delima = pd.DataFrame(res5m,columns=['high','low','open','close'])
    delima['ema14'] = ta.ema(delima['close'],14)
    delima['ema28'] = ta.ema(delima['close'],28)

    dvolume['ema14'] = ta.ema(dvolume['close'],14) #dvolume.iloc[:,0].ewm(span=1,adjust=False).mean()
    dvolume['ema28'] = ta.ema(dvolume['close'],28)

    dvolume["counter"] = volume
    dvolume["Spread"] = spread
    va = (curprice["close"]-curprice["open"]) * (10**10)
    dvolume["va"] = np.round(va, 0)
    dvolume["volume"] = np.round(va)

    
    ava = np.array(va.values.tolist())

    waktu = data.index[-1].strftime('%H:%M')
    waktu2 = ""

    detik = data.index[-1].strftime('%S')
    ctr = dvolume["counter"][-1]

    ctrl = int(data["created_at"][-1].split(":")[-1].split(".")[0])

    print("detik -> ", detik)
    print("xctr -> ", ctrl)
    

    print(dvolume.tail(10))
    engulfing(dvolume,delima)

def engulfing(data,datalima):
    global pcounter, ccounter, dev_counter, timeleft, last_signal, waktu_lalu, timex
    global msg_buy_adx, msg_sell_adx, last_signal_code, msg, maxlow, maxhigh    
    global pesan_buy_lama, pesan_sell_lama, win_status, last_amount, latest_balance
    global pesan_buy_lama, pesan_sell_lama, aa
    
    datasli = data

    if data.size > 4:

        '''
        start volume analysis
        '''

        aa = 0
        # volume
        if int(round(datasli['va'][-1])) > 5000:
            print("AV BUY detected send message ..." + waktu)
            aa+=1
            dtb = datetime.now(tzinfo)
            buyt = dtb.strftime('%H:%M')
            pesan_buy = "⬆️ [[CRY-IDX]] [[RT]] [[VA]] big BUY detected at " + str(buyt)
            print("aa -> ",aa)
            if pesan_buy_lama != pesan_buy:
                if (aa > 15) and (ctr < 75):  
                    if c2 > ema5_1:                                   
                        orderBuySell(1,"call",20001)
                        print(pesan_buy)
                        aa = 0
                        telegram_bot_sendtext(pesan_buy)
                        pesan_buy_lama = pesan_buy
            

        elif int(round(datasli['va'][-1])) < -5000:
            print("AV SELL detected send message ...")
            aa+=1
            dts = datetime.now(tzinfo)
            sellt = dts.strftime('%H:%M')
            pesan_sell = "⬇️ [[CRY-IDX]] [[RT]] [[VA]] big SELL detected at " + str(sellt)
            print("aa -> ",aa)
            if pesan_sell_lama != pesan_sell:
                if (aa > 15) and (ctr < 75):             
                    if c2 < ema5_1:                                   
                        orderBuySell(1,"put",20002)
                        print(pesan_sell)
                        aa = 0
                        #telegram_bot_sendtext(pesan_sell)
                        pesan_sell_lama = pesan_sell

        '''
        end Volume analysis
        '''

        # waktu
        i = 0
        dtb = datetime.now(tzinfo)
        present_utc = datetime.now()
        presentDate = dtb + timedelta(minutes=1)
        waktu = presentDate.strftime('%H:%M')
        
        lmnt = presentDate.strftime('%M')
        last_minute = getLastMinute(int(lmnt))
        if last_minute == 5:
            last_minute == 1
        limit_tp = 5
        max_tp5 = limit_tp - last_minute

        last_signal_time = dtb - timedelta(minutes=1)
        last_stime = last_signal_time.strftime('%H:%M')

        utc_present = present_utc + timedelta(minutes=1)
        waktu_utc = utc_present.strftime('%H:%M')
        # end waktu

        eng = data.tail(3)
        eng.drop(eng.tail(1).index,inplace=True)

        #print("eng -> ",eng)
        
        d11 = get_ema1428(60)
        d1 = d11["d1"]
        
        print("d1 before -> ", d1.tail(5))

        dlima = d1.resample("5Min").mean()
        ind5 = Indicators(dlima)
        ind5.fractals(column_name_high='fractals_high', column_name_low='fractals_low')
        ind5 = ind5.df

        ind5['EMA5'] = ta.ema(ind5['Close'],5)
        ind5['EMA14_5'] = ta.ema(ind5['Close'],14)
        ind5['EMA28_5'] = ta.ema(ind5['Close'],28)
        ind5['EHigh'] = (ind5['High'] - ind5['EMA28_5']) * (10**7)
        ind5['ELow'] = (ind5['Low'] - ind5['EMA28_5']) * (10**7)
        ind5['EHigh_mean'] = ((ind5['High'] - ind5['EMA28_5']) * (10**7)).mean()
        ind5['ELow_mean'] = ((ind5['Low'] - ind5['EMA28_5']) * (10**7)).mean()

        d5 = ind5

        dema = d1.tail(3)

        dedema = dema
        latest_ema = d1['EMA28'][-1]
        ema28 = latest_ema
        ema14 = d1['EMA14'][-1]        
        ema5_1 = d1['EMA5'][-1]

        dema.drop(dema.tail(1).index,inplace=True)

        ema28 = float(0 if ema28 is None else ema28)
        ema14 = float(0 if ema14 is None else ema14)
        
        
        latest_v3 = datasli['va'][-1]

        # close data
        h1 = dema['High'][0] 
        h2 = dema['High'][-1]
        h3 = d1['High'][-1]  

        c1 = dema['Close'][0]
        c2 = dema['Close'][-1]
        c3 = d1['Close'][-1]

        l1 = dema['Low'][1]
        l2 = dema['Low'][-1]
        l3 = d1['Low'][-1] 

        o1 = dema['Open'][0]
        o2 = dema['Open'][-1]
        o3 = d1['Open'][-1]
        
        #volume
        v1 = eng['va'][0]
        v2 = eng['va'][-1]
        v3 = latest_v3


        cur_balance = getBalance()
                
        if (cur_balance > latest_balance):
            win_status = True
        elif (cur_balance < latest_balance):
            win_status = False

        if last_amount > cur_balance:
            last_amount = 0

        win_rate_adjustment = 2.5

        counter = datasli['counter'][-1]
        time_threshold_eng = 70
        threshold_va = 3000
        threshold_counter = 50

        # MAXLOW - MAXHIGH 1 Menit
        ll11 = d1['Low'][-1]
        hh11 = d1['High'][-1]

        if ll11 not in maxlow:            
            maxlow.append(ll11)
        if hh11 not in maxhigh:            
            maxhigh.append(hh11)


        # reset maxlow & maxhigh
        if int(datetime.utcnow().strftime("%S")) == 1:
            maxlow = []
            maxhigh = []
        
        print("maxlow -> ", maxlow)
        print("maxhigh -> ", maxhigh)

        print("MIN: maxlow -> ", min(maxlow))
        print("MAX: maxhigh -> ", max(maxhigh))

        last_minute = int(1 if last_minute == 0 else last_minute)
        last_minute = int(2 if last_minute == 1 else last_minute)
        last_minute = int(1 if last_minute == 5 else last_minute)


        # END MAXLOW MAXHIGH

        d1_hh = d1['EHigh'][-1]
        d1_ll = d1['ELow'][-1]

        #EMA timeframe 5 menit
        delima = d5.tail(3)
        print("delima before -> ", delima)
        dlima = delima
        lema28 = d5['EMA28_5'][-1]
        lema14 = d5['EMA14_5'][-1]

        latest_h53 = d5['High'][-1]
        latest_c53 = d5['Close'][-1]
        latest_l53 = d5['Low'][-1]
        latest_o53 = d5['Open'][-1]

        delima.drop(delima.tail(1).index,inplace=True)

        print("delima after -> ",delima)

        # --------------------------------------

        h51 = delima['High'][0] 
        h52 = delima['High'][-1]
        h53 = latest_h53

        l51 = delima['Low'][0]
        l52 = delima['Low'][-1]
        l53 = latest_l53 

        o51 = delima['Open'][0]
        o52 = delima['Open'][-1]
        o53 = latest_o53

        c51 = delima['Close'][0] 
        c52 = delima['Close'][-1]
        c53 = latest_c53

        d5_hh = d5['EHigh'][-1]
        d5_ll = d5['ELow'][-1]

        ema28_5 = float(0 if d5['EMA28_5'][-1] is None else d5['EMA28_5'][-1])
        ema14_5 = float(0 if d5['EMA14_5'][-1] is None else d5['EMA14_5'][-1])
        ema5 = float(0 if d5['EMA5'][-1] is None else d5['EMA5'][-1])

        d5_fractals_high = bool(0 if d5['fractals_high_y'][-1] is None else d5['fractals_high_y'][-1])
        d5_fractals_low = bool(0 if d5['fractals_low_y'][-1] is None else d5['fractals_low_y'][-1])

        print("latest c53 -> ", latest_c53)
        print("latest h53 -> ", latest_h53)
        print("latest l53 -> ", latest_l53)
        print("latest o53 -> ", latest_o53)
        
        print("latest h53 > h52 ", latest_c53 > h52)
        print("latest l53 > l52 ", latest_l53 > l52)

        # fractal EMA 28
        HFractalEMA = float(0 if d1['EHigh'][-1] is None else d1['EHigh'][-1])
        LFractalEMA = float(0 if d1['ELow'][-1] is None else d1['ELow'][-1])

        #print(dema['EMA28'])

        fractals_high = bool(0 if d1['fractals_high'][-1] is None else d1['fractals_high'][-1])     
        fractals_low = bool(0 if d1['fractals_low'][-1] is None else d1['fractals_low'][-1])

        fractals_high2 = bool(0 if dema['fractals_high'][1] is None else dema['fractals_high'][1])     
        fractals_low2 = bool(0 if dema['fractals_low'][1] is None else dema['fractals_low'][1])

        diff_hema = (h3 - latest_ema) * (10**7)
        diff_lema = (l3 - latest_ema) * (10**7)

        #ELow, EHigh
        curr_diff_ema  = (c3 - ema28) * (10**7)
        diff_ema14  = (c3 - ema14) * (10**7)
        
        ema28_5 = float(0 if ema28_5 is None else ema28_5)
        ema14_5 = float(0 if ema14_5 is None else ema14_5)
        
        print("latest_ema -> ", latest_ema)
        print("curr_diff_ema -> ", curr_diff_ema)
        print("HFractalEMA -> ",HFractalEMA)
        print("LFractalEMA -> ", LFractalEMA)
        print("diff_hema:  ", diff_hema)
        print("diff_lema: ", diff_lema)
        print("fractals_high: ", fractals_high)
        print("fractals_low: ", fractals_low)

        print("fractals_high2: ", fractals_high2)
        print("fractals_low2: ", fractals_low2)
        print("is_below_ema: ", latest_ema > c3)
        print("is_below_ema_28_5: ", ema28_5 > c3)
        print("is_below_ema_14_5: ", ema14_5 > c3)
        print("is ema14_5 > ema28_5 : ", ema14_5 > ema28_5)
        print("fractal_up_threshold_5m: ", h52)
        print("fractal_down_threshold_5m: ", l52)
        print("d5_hh: ", d5_hh)
        print("d5_ll: ", d5_ll)
        print("d1_hh: ", d1_hh)
        print("d1_ll: ", d1_ll)
        print("d5_fractals_low: ", d5_fractals_low)
        print("d5_fractals_high: ", d5_fractals_high)

        
        if counter >= 100:
            hcounter = c3

        if (counter <= threshold_counter) and (abs(v3) >= threshold_va):
            pcounter = c3
            ccounter = counter
            dev_counter = ccounter + 15
            timeleft = 140 - (counter - 5)


        print("counter -> ", counter)
        print("prices -> ", c3)
        print("volume -> ", v3)
        print("timeleft -> ", timeleft)
        print("pcounter -> ", pcounter)
        print("dev_counter -> ", dev_counter)
        print("last_minute: ", last_minute)

        print("l53 < l52: ", l53 < l52)
        print("l53 > l52: ", l53 > l52)
        print("h53 > h52: ", h53 > h52)
        print("h53 < h52: ", h53 < h52)
        print("ema14 < ema28: ", ema14 < ema28)

        param_cek_candle_kenaikan = (c53 > c52) and (l53 > l52) and (h53 > h52) and ((h3 > h2) and (l3 > l2))
        param_cek_candle_penurunan = (c53 <= c52) and (h53 < h52) and ((h3 < h2) and (l3 < l2))
        param_cek_hh = (h53 < h52) and (c3 < h52) and (c53 < h52) and (c3 < h2)
        param_cek_ll = (c53 > l52) and (c3 > l52) and (c3 > l2)
        param_ciri_naik_overbought= (c3 > h52) and (c3 > o53)
        param_ciri_turun_oversold = (c3 < l52) and (c3 < o53)

        # 1 menit
        param_diatas_ema14 = (c3 > ema14)
        param_diatas_ema28 = (c3 > ema28)
        param_dibawah_ema14 = (c3 < ema14)
        param_dibawah_ema28 = (c3 < ema28)
        param_diatas_ema14_28 = (c3 > ema14) and (c3 > ema28) and (ema14 > ema28)
        param_dibawah_ema14_28 = (c3 < ema14) and (c3 < ema28)

        # 5 menit
        param_dibawah_ema28_5 = (c53 < ema28_5)
        param_dibawah_ema14_5 = (c53 < ema14_5)
        param_diatas_ema28_5 = (c53 > ema28_5)
        param_diatas_ema14_5 = (c53 > ema14_5)        
        param_diatas_ema14_28_5 = (c3 > ema14_5) and (c3 > ema28_5) and (ema14 > ema28)
        param_dibawah_ema14_28_5 = (c3 < ema14_5) and (c3 < ema28_5)        

        # dibawah ema5
        c53_dibawah_ema5 = (c53 < ema5)
        c53_diatas_ema5 = (c53 > ema5)
        c52_dibawah_ema5 = (c52 < ema5)
        c52_diatas_ema5 = (c52 > ema5)        
        h52_diatas_ema5 = (h52 > ema5)
        h52_dibawah_ema5 = (h52 < ema5)
        l52_diatas_ema5 = (l52 > ema5)
        l52_dibawah_ema5 = (l52 < ema5)

        c2_dibawah_ema5_1 = (c2 < ema5_1)
        c2_diatas_ema5_1 = (c2 > ema5_1)        

        ema14_5_diatas_ema28_5 = (ema14_5 > ema28_5)
        ema14_5_dibawah_ema28_5 = (ema14_5 < ema28_5)

        param_cek_satu_candle_turun = (c3 < o3) and (c3 < c2 and c3 < l2)
        param_cek_satu_candle_naik = (c3 > o3) and (c3 > c2 and h3 > h2)
        print("param_cek_candle_kenaikan: ", param_cek_candle_kenaikan)
        print("param_cek_candle_penurunan: ", param_cek_candle_penurunan)
        print("param_cek_satu_candle_turun: ", param_cek_satu_candle_turun)
        print("param_cek_hh: ", param_cek_hh)
        print("param_cek_ll: ", param_cek_ll)
        print("param_ciri_naik_overbought: ", param_ciri_naik_overbought)
        print("param_ciri_turun_oversold: ", param_ciri_turun_oversold)

        param_cek_satu_candle_naik_dibawah_ema14 = (v2 > 0 and v3 > 0) and (c3 > c2 and l3 > l2) and (c3 < ema14) and (c3 <= h2) or (c3 > o3 and c3 > c2 and c3 > h2)

        param_cek_satu_candle_naik = (v2 > 0 and v3 > v2) and (c3 > c2 and l3 > l2) and (c3 <= h2) or (c3 > o3 and c3 > c2 and c3 > h2)

        print("param_cek_satu_candle_naik_dibawah_ema14: ", param_cek_satu_candle_naik_dibawah_ema14)
        print("param_cek_satu_candle_naik: ", param_cek_satu_candle_naik)
        print("l3 < l52: ", c3 < l52)
        print("h3 < h52: ", c3 < l52)


        if len(msg) <= 0:
            msg = "[[BOT STARTED]]"


        dts = datetime.now(tzinfo)
        ordert = dts.strftime('%H:%M')

        maxv3 = datasli[['va'][-1]].max()
        minv3 = datasli[['va'][-1]].min()
      
        maxc3 = d1[['High'][-1]].max()
        minc3 = d1[['Low'][-1]].min()
        
        print("maxv3 -> ", maxv3)
        print("minv3 -> ", minv3)
        print("maxc3 -> ", maxc3)
        print("minc3 -> ", minc3)
        print("cur_balance -> ", cur_balance)
        print("win_status -> ", win_status)
        print("last_amount -> ", last_amount)
        
        diff_ema5_1 = float(ema5_1 - c3 if ema5_1 > c3 else c3 - ema5_1) * (10**7)
        diff_ema28 = float(ema28 - c3 if ema28 > c3 else c3 - ema28) * (10**7)
        print("jarak ema5 1 menit dengan c3 -> ", diff_ema5_1)
        print("jarak ema28 1 menit dengan c3 -> ", diff_ema28)

        mnt = last_minute + 1

        print("c2_diatas_ema5_1 -> ", c2_diatas_ema5_1)

        '''
        engulfing analysis
        '''

        if (h2 < ema5_1) and (c2 < ema5_1):
            msg = "⬆️ [[CRY-IDX]] [[RT]] [[ENG]] potentially BUY [[22501]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
            print(msg)            
            def_amount = (25501 if last_amount == 0 else last_amount and 25501 if win_status == True else last_amount)                                        
            if (o3 < ema5_1) and (h3 > h2) and (c3 > ema5_1) and (h3 > ema5_1):
                if c52_diatas_ema5 == True:                
                    if msg != msg_buy_adx:                
                        orderBuySell(4,"call",25501,1)
                        telegram_bot_sendtext(msg)                        
                        msg_buy_adx = msg  
                        last_amount = def_amount 


        if (h2 < ema5_1) and (c2 < ema5_1):
            msg = "⬆️ [[CRY-IDX]] [[RT]] [[ENG]] potentially SELL [[25502]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
            print(msg) 
            def_amount = (25502 if last_amount == 0 else last_amount and 25502 if win_status == True else last_amount)                                                   
            if (o3 > ema5_1) and (h3 < l2) and (c3 < ema5_1) and (h3 < ema5_1):
                if c52_dibawah_ema5 == True:
                    if msg != msg_buy_adx:                
                        orderBuySell(1,"put",25502,1)
                        telegram_bot_sendtext(msg)                        
                        msg_buy_adx = msg  
                        last_amount = def_amount 

        '''
        end engulfing tambahan
        '''

        '''
        start EMA analysis
        '''

        if (c2_diatas_ema5_1 == True):

            if (diff_ema5_1 < 1) and (c3 > ema5_1) and (o2 > ema5_1):
                def_amount = (21500 if last_amount == 0 else last_amount and 21500 if win_status == True else last_amount)                            
                if (h3 > h2) and (c2 > ema5_1) and (o2 > ema5_1):  
                    msg = "⬆️ [[CRY-IDX]] [[RT]] [[EMA51]] potentially BUY [[21500]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                    print(msg)
                    if c52_diatas_ema5 == True:                        
                        if msg != msg_buy_adx:
                                orderBuySell(1,"call",21500)
                                telegram_bot_sendtext(msg)
                                msg_buy_adx = msg  
                                last_amount = def_amount 

            if (c3 <= min(maxlow)):
                def_amount = (25011 if last_amount == 0 else last_amount and 25011 if win_status == True else last_amount)            
                place_order = (25011 if win_status == True else win_rate_adjustment * 25011)
                #and (c3 >= c2)

                if (c2_diatas_ema5_1 == True) and (c3 > l2) or (c3 >= c2):
                    if (c52_diatas_ema5 == True) and (c2 > ema5_1) and (c53 > c52):
                        if (h53 < h52) and (c3 > o3) and (counter > 120):
                            msg = "⬆️ [[CRY-IDX]] [[RT]] [[EMA51]] potentially BUY [[25011]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                            print(msg)
                            if msg != msg_buy_adx:                            
                                orderBuySell(4,"call",25011,last_minute)
                                telegram_bot_sendtext(msg)                    
                                msg_buy_adx = msg  
                                last_amount = def_amount

                    if (c52_dibawah_ema5 == True) and (c2 < ema5_1) and (c53 < c52):
                        msg = "⬇️ [[CRY-IDX]] [[RT]] [[EMA51]] potentially SELL [[25111]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                        print(msg)
                        if (c3 < o3) and (counter > 120):
                            if msg != msg_buy_adx:                            
                                orderBuySell(4,"put",25111,last_minute)
                                telegram_bot_sendtext(msg)                    
                                msg_buy_adx = msg  
                                last_amount = def_amount
                
                if (c3 < ema14) or (c3 < ema28) and (ema28 < ema14) and (ema14 < ema5_1):
                    place_order = (25025 if win_status == True else win_rate_adjustment * 25025)                
                    print("place_order CALL -> ",place_order)
                    if c52_diatas_ema5 == True:                
                        if (c3 > c2) or (c3 > h2) and (c3 > o3):                                                  
                            msg = "⬆️ [[CRY-IDX]] [[RT]] [[EMA51]] [[REV]] potentially BUY [[25025]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                            print(msg)
                            if msg != msg_buy_adx:                            
                                orderBuySell(4,"call",25025,last_minute)
                                telegram_bot_sendtext(msg)                    
                                msg_buy_adx = msg  
                                last_amount = def_amount                        

            if (c3 > max(maxhigh)) and (diff_ema28 > 30) and ((c3 < o3) or (c3 < l2)):
                    place_order = (25026 if win_status == True else win_rate_adjustment * 25026)                
                    print("place_order PUT -> ",place_order)
                    if (c3 > c2) or (c3 > h2) and (c3 > o3):                                                  
                        msg = "⬆️ [[CRY-IDX]] [[RT]] [[EMA51]] [[REV30]] potentially BUY [[25026]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                        print(msg)
                        if msg != msg_buy_adx:                            
                            orderBuySell(1,"call",25026)
                            telegram_bot_sendtext(msg)                    
                            msg_buy_adx = msg  
                            last_amount = def_amount 
            

            elif (c2_diatas_ema5_1 == True) and (counter < 75) and (c3 < c2) and (diff_ema5_1 < 0.5):
                if c52_diatas_ema5 == True:  
                    if (c3 > c2) or (c3 > h2) and (c3 > o3):   
                        msg = "⬆️ [[CRY-IDX]] [[RT]] [[EMA51]] [[REV30]] potentially BUY [[25026]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                        print(msg)                    
                        if msg != msg_buy_adx:                                                                           
                            orderBuySell(1,"call",25027)
                            telegram_bot_sendtext(msg)                    
                            msg_buy_adx = msg  
                            last_amount = def_amount

        #print("c2_dibawah_ema5_1 -> ", c2_dibawah_ema5_1)

        if (c2_dibawah_ema5_1 == True):
            def_amount = (25012 if last_amount == 0 else last_amount and 25012 if win_status == True else last_amount)                        
            # jika terrjadi penurunan
            if (c3 >= max(maxhigh)):
                if (c2_dibawah_ema5_1 == True) and (c3 < l2) or (h3 > h2):                
                    msg = "⬇️ [[CRY-IDX]] [[RT]] [[EMA51]] potentially SELL [[25012]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                    print(msg)
                    place_order = (25012 if win_status == True else win_rate_adjustment * 25012)                
                    print("place_order PUT -> ",place_order)
                    if (c52_dibawah_ema5 == True) and ((c3 > ema28_5) or (c3 > ema14_5)):                    
                        if (c3 < c2) or (c3 < l2) and (c3 < o3):
                            if msg != msg_buy_adx:                                                                                                       
                                orderBuySell(4,"put",25012, last_minute)
                                telegram_bot_sendtext(msg)                    
                                msg_buy_adx = msg  
                                last_amount = def_amount 

                if (c3 > ema14) or (c3 > ema28) and (ema28 > ema14) and (ema14 > ema5_1) and (o2 > ema14):                                        
                    if c52_dibawah_ema5 == True:
                        msg = "⬇️ [[CRY-IDX]] [[RT]] [[EMA51]] [[REV]] potentially SELL [[25022]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                        print(msg)                        
                        place_order = (25022 if win_status == True else win_rate_adjustment * 25022)                
                        if (c2 < ema5_1) and ((c3 > ema28_5) or (c3 > ema14_5)) and (c2 < ema5):
                            if (c3 < c2) or (c3 < l2) and (c3 < o3):
                                if msg != msg_buy_adx:                                                                                                                                       
                                    orderBuySell(4,"put",25022, last_minute)
                                    telegram_bot_sendtext(msg)                    
                                    msg_buy_adx = msg  
                                    last_amount = def_amount                        
                    elif c52_diatas_ema5 == True:
                        if c2 > ema5_1:
                            msg = "⬆️ [[CRY-IDX]] [[RT]] [[EMA51]] [[REV]] potentially BUY [[22222]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                            print(msg)
                            if (c3 > c2) or (c3 > h2) and (c3 > o3):
                                if msg != msg_buy_adx:                                                                                                                                                                                                                             
                                    orderBuySell(4,"call",22222, last_minute)
                                    telegram_bot_sendtext(msg)                    
                                    msg_buy_adx = msg  
                                    last_amount = def_amount                        
                        elif c2 < ema5_1:
                            msg = "⬇️ [[CRY-IDX]] [[RT]] [[EMA51]] [[REV]] potentially SELL [[22220]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                            print(msg)
                            if (c3 < c2) or (c3 < l2) and (c3 < o3):
                                if counter < 75: 
                                    if msg != msg_buy_adx:                                                                                                                                                                                                                                                                                                                        
                                        orderBuySell(1,"put",22220)
                                        telegram_bot_sendtext(msg)                    
                                        msg_buy_adx = msg  
                                        last_amount = def_amount                        

                if (c3 > ema14) or (c3 > ema28) and (ema28 > ema14) and (ema14 > ema5_1) and (o2 < ema14) and (ema14_5 > ema28_5):
                    place_order = (25222 if win_status == True else win_rate_adjustment * 25222)                
                    print("place_order CALL -> ",place_order)
                    if c2 < ema5_1:
                        if (diff_ema5_1 < 1) and (c3 < ema5_1) and (c2 < ema5_1):
                            msg = "⬇️ [[CRY-IDX]] [[RT]] [[EMA51]] [[REV]] potentially SELL [[22221]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                            print(msg)                            
                            if c52_dibawah_ema5 == True:
                                if msg != msg_buy_adx:
                                    orderBuySell(1,"put",22221)
                                    telegram_bot_sendtext(msg)                                    
                                    msg_buy_adx = msg  
                                    last_amount = def_amount 

                        if (c3 > c2) or (c3 > h2) and (c3 > o3): 
                            if (c52_diatas_ema5 == True) or (c2 > ema5_1) and (c3 > o3):
                                msg = "⬆️ [[CRY-IDX]] [[RT]] [[EMA51]] [[REV]] potentially BUY [[21220]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                                print(msg)
                                if (last_minute > 2):
                                    if h3 < h2 and c2 < ema5_1 and c3 < c2:
                                        if (counter < 75 and o2 > ema5_1):
                                            if msg != msg_buy_adx:                                            
                                                orderBuySell(1,"call",21220)
                                                telegram_bot_sendtext(msg)                    
                                                msg_buy_adx = msg  
                                                last_amount = def_amount 
                            if (c52_dibawah_ema5 == True) and (diff_ema5_1 > 10):
                                if (h53 > h52) and (h52 < h51):
                                    msg = "⬇️ [[CRY-IDX]] [[RT]] [[EMA51]] [[REV]] potentially SELL [[21221]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                                    print(msg)
                                    if msg != msg_buy_adx:                                                                                
                                        orderBuySell(4,"put",21221, mnt)
                                        telegram_bot_sendtext(msg)                    
                                        msg_buy_adx = msg  
                                        last_amount = def_amount 


            if (c3 < min(maxlow)) and (diff_ema28 > 30) and ((c3 > o3) or (c3 > c2)):
                    msg = "⬆️ [[CRY-IDX]] [[RT]] [[EMA51]] [[REV30]] potentially BUY [[25023]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                    print(msg)
                    place_order = (25023 if win_status == True else win_rate_adjustment * 25023)                
                    print("place_order CALL -> ",place_order)
                    if (c3 > c2) or (c3 > h2) and (c3 > o3): 
                        if (c52_diatas_ema5 == True) and (c3 > c2):
                            if msg != msg_buy_adx:                                                                                                         
                                orderBuySell(4,"call",25023, mnt)
                                telegram_bot_sendtext(msg)                    
                                msg_buy_adx = msg  
                                last_amount = def_amount 
            
            if (c3 < ema5_1) and ((c3 < ema14) or (c3 < ema28)) and (ema28 < ema14) and (ema14 < ema5_1):
                msg = "⬆️ [[CRY-IDX]] [[RT]] [[EMA51]] [[REV]] potentially BUY [[25024]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                print(msg)
                place_order = (25024 if win_status == True else win_rate_adjustment * 25024)                
                print("place_order CALL -> ",place_order)
                if (c3 > c2) or (c3 > h2) and (c3 > o3):   
                    if (c52_diatas_ema5 == True) and (c3 > c2) and (c2 > c1) and (c3 > ema5_1):  
                        if msg != msg_buy_adx:                                                                                                                                 
                            orderBuySell(4,"call",25024,mnt)
                            telegram_bot_sendtext(msg)                    
                            msg_buy_adx = msg  
                            last_amount = def_amount                        

            if (c2_dibawah_ema5_1 == True) and (c3 < c2) and (diff_ema5_1 < 1):
                msg = "⬇️ [[CRY-IDX]] [[RT]] [[EMA51]] [[NXT]] potentially SELL [[25113]] - UTC7 " + str(waktu) + " | UTC0 " + str(waktu_utc)            
                print(msg)
                if (c2 < ema5) and (c2 < ema5_1) and (h2 < h1) and (h3 < h2):
                    if (h53 < h52) and (c3 < o3):
                        if (counter < 75) and (c52_dibawah_ema5 == True):
                            if msg != msg_buy_adx:                                                                                                                                                                                         
                                orderBuySell(1,"put",25113,1)
                                telegram_bot_sendtext(msg)                    
                                msg_buy_adx = msg  
                                last_amount = def_amount


        '''
        end EMA analysis
        '''

def telegram_bot_sendtext(bot_message):    
    bot_token = botToken
    bot_chatID = gchatId
    send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message
    response = requests.get(send_text)
    return response.json()    


def telegram_bot_sendchart():    
    bot_token = botToken
    bot_chatID = gchatId
    dtt = datetime.now(tzinfo)
    charttime = dtt.strftime('%Y%m%d-%H%M')
    
    response = requests.post(
        "https://api.telegram.org/bot"+bot_token+"/sendPhoto?chat_id="+bot_chatID,
        files={"photo": open("BinomoStream.png", "rb")}
    )
    os.rename("BinomoStream.png", "BinomoStream-" + str(charttime) + ".png")    
    os.remove("BinomoStream.png")
    return response.json()    

def isclose(a, b, rel_tol=1e-09, abs_tol=0.0):
    return abs(a-b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


def setLastSignal(sgnl,val):
    global last_signal, val_signal
    last_signal = sgnl
    val_signal = val

def getLastSignal():
    global last_signal, val_signal
    return [last_signal,val_signal]

def setBalance(lbalance):
    global latest_balance
    latest_balance = lbalance

def getBalance():
    global latest_balance
    return latest_balance

def orderBuySell(typeorder, call_put, amnt=14000, duration=1):
    global loop_socket, latest_balance
    print("loop_socket -> ",loop_socket)
    loop_socket+=1
    pb = cc.Placebid(typeorder, call_put, amnt, duration, loop_socket)
    balance = pb.getCurrentBalance()
    setBalance(balance)
    
def getLastMinute(mnt):
    resmin = mnt % 5 
    left_minute = 5 - resmin
    return left_minute

def get_ema1428(duration):
    ema28 = EMA_14_28()
    return ema28.getData(duration)

if __name__ == "__main__":
    ws = websocket.WebSocketApp("wss://as.binomo.com/",
                              on_message = on_message,
                              on_error = on_error,
                              on_close = on_close,
                              on_ping=on_ping,
                              on_pong=on_pong
                              )
    ws.on_open = on_open
    
    keep_on = True
    while keep_on:
      try:
        ping_data = {"topic":"asset:Z-CRY/IDX","event":"ping","payload":{},"ref": str(counter_ping),"join_ref":"28"}
        keep_on = ws.run_forever(ping_interval=5, ping_payload=json.dumps(ping_data))
      except:
        print("[Websocket Error]")
