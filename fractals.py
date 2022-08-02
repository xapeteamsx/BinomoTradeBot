#!/usr/bin/python3
import os, asyncio, websockets, ssl
import time
import pandas as pd
import talib
from datetime import datetime, timezone, timedelta
import json
import dateutil, calendar
from tapy import Indicators
from DataHistory import Ticker
import ClientConsole as cc
from telethon import TelegramClient
import requests
import logging
import numpy as np

'''
fractals and cci with heiken ashi candle strategy
'''

class Binongtot(object):
    def __init__(self):
        self._aw_conn = None
        self._depth = 0
        self.df = pd.DataFrame(columns=['Datetime','rate', 'precision', 'repeat', 'ask', 'created_at','bid', 'spread','volume'])
        self.newdf = pd.DataFrame(columns=['Datetime','rate', 'precision', 'repeat', 'ask', 'created_at','bid', 'ric','spread','volume'])
        self.response = {}
        self.counter = 0
        self.loop_socket = 0
        self.assetConf = self.get_asset()
        self.deviceId = self.assetConf["deviceId"]
        self.authToken = self.assetConf["authToken"]
        self.assetRic = self.assetConf["assetRic"]
        self.currency = self.assetConf["currency"]
        self.amount = self.assetConf["currency"]
        self.uagent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"        
        self.bid_price = self.amount
        self.lowbid = 20000
        self.ctr_minute = 1
        self.msg_buy = ""
        self.msg_sell = ""        
        self.latest_balance = 0
        self.telegram_channel_notification = True
        self.websocket_debug = False
        self.val_support = []
        self.val_resistance = []        
        self.state_val_support = []
        self.state_val_resistance = []
        self.df_support = pd.DataFrame()
        self.df_resistance = pd.DataFrame()
        self.hbuy = []
        self.hsell = []
        self.dataintv = 15

        # set time and timezone
        timezone_offset = +7.0 
        self.tzinfo = timezone(timedelta(hours=timezone_offset))
        dtb = datetime.now(self.tzinfo)
        presentDate = dtb + timedelta(minutes=+1)
        self.curr_now = presentDate.strftime('%H:%M')
        self.lasttime = ""
        present_utc = datetime.now()
        utc_present = present_utc + timedelta(minutes=+1)
        self.curr_utc = utc_present.strftime('%H:%M')

        # setup telegram bot
        self.botToken = ''
        self.gchatId = ''
        
        self.tempbin = self.getOnlineData()
        self.pollHost = "wss://as.binomo-financing.com/"
        self.cookie = "l=; authtoken="+self.authToken+"; device_id="+self.deviceId+"; device_type=web"
        self.headers = {'User-Agent': self.uagent, 'Cookie': self.cookie}

        self.pb = cc.Placebid()

        if self.websocket_debug == True:
            logger = logging.getLogger('websockets')
            logger.setLevel(logging.DEBUG)
            logger.addHandler(logging.StreamHandler())        


    async def __aenter__(self):
        # create a connection *if not already established*
        if self._aw_conn is None:
            self._aw_conn = await websockets.connect(self.pollHost,ssl=ssl.SSLContext(protocol=ssl.PROTOCOL_TLS))
            self._depth = 0
        self._depth += 1
        return self._aw_conn

    async def __aexit__(self, *exc_info):
        self._depth -= 1
        if self._depth < 1:
            # close the connection
            await self._aw_conn.close()
            self._aw_conn = None
            self._depth = 0

    async def main(self):
        async with self as websocket:
            self.connect()

    async def createDataframe(self, data):
        tempdata = {}
        rates = []
        self.loop_socket+=1
        dtt = datetime.now(self.tzinfo)
        wibtime = dtt.strftime('%H:%M')
        charttime = dtt.strftime('%Y-%m-%d %H:%M:00')
        pd.set_option('display.float_format', '{:.11f}'.format)

        data.index = pd.to_datetime(data.Datetime)
        df1 = data['rate'].resample('15s').agg(
                                    {'open': 'first', 
                                     'high': 'max', 
                                     'low': 'min', 
                                     'close': 'last'})
        

        d1 = pd.DataFrame(df1).reset_index()
        d1.columns = ['Datetime','Open', 'High','Low','Close']          

        self.counter = int(data["created_at"][-1].split(":")[-1].split(".")[0])
        print("xctr -> ", self.counter)


        curr_close = 0
        current_price = 0
        curopen = 0

        if self.counter == 0:
            curr_close = df1['close'][-1]        
        elif self.counter == 1:        
            curopen = df1['open'][-1]
        else:
            curr_close = df1['close'][-1]
            curopen = df1['open'][-1]
            current_price = df1['close'][-1]
        

        print("process_om -> currency: ", self.assetConf['currency'])
        print("process_om -> curopen: ", curopen)
        print("process_om -> current_price: ", current_price)

        hk = self.heikin_ashi(d1)
        actual_trades = self.heiken_ashi_strategy(hk)    
        actual_trades.set_index("Datetime")    
        d1.set_index("Datetime")
        
        dfm = hk.merge(actual_trades, on='Datetime', how='left')
        print("heikin_ashi -> ",dfm)
        
        if len(dfm.index) > 0:
            self.fractals_15s(self.counter, dfm)


    def fractals_15s(self, ctr, wsdata):
        
        wsdata = wsdata.rename(columns = {'ha_open':'Open', 'ha_high':'High', 'ha_low':'Low', 'ha_close':'Close'})
        wsdata = wsdata.set_index("Datetime")

        dtb = datetime.now(self.tzinfo)
        present_utc = datetime.now()
        presentDate = dtb + timedelta(minutes=+1)
        timesx = presentDate.strftime('%H:%M')

        present_utc = datetime.now()
        utc_present = present_utc + timedelta(hours=-7) + timedelta(minutes=+1)
        timesx_utc = utc_present.strftime('%H:%M')
        
        curr_high = wsdata['High'][-1]
        curr_low = wsdata['Low'][-1]
        curr_open = wsdata['Open'][-1]
        curr_price = wsdata['Close'][-1]
        op1 = wsdata['Open'].shift(1)[-1]
        op2 = wsdata['Open'].shift(2)[-1]
        cl1 = wsdata['Close'].shift(1)[-1]
        cl2 = wsdata['Close'].shift(2)[-1]
        ll1 = wsdata['Low'].shift(1)[-1]
        ll2 = wsdata['Low'].shift(2)[-1]
        hh1 = wsdata['High'].shift(1)[-1]
        hh2 = wsdata['High'].shift(2)[-1]

        # heiken-ashi strategy
        ha_long_exit = wsdata['long_exit'][-1]
        ha_short = wsdata['short'][-1]
        ha_long = wsdata['long'][-1]
        ha_short_exit = wsdata['short_exit'][-1]

        ha_up = (ha_long_exit == True and ha_short == True)
        ha_down = (ha_long == True and ha_short_exit == True)

        ind = Indicators(wsdata)
        ind.fractals(column_name_high='fractals_high', column_name_low='fractals_low')
        ind.ema(period=10, column_name='ema10', apply_to='Close')   
        ind.cci()        
        dof = ind.df

        # fractals
        pre_fhi = dof['fractals_high'].shift(2)[-1]
        pre_flo = dof['fractals_low'].shift(2)[-1]
        fhi = dof['fractals_high'].shift(3)[-1]
        flo = dof['fractals_low'].shift(3)[-1]
        fhi_price = dof['High'].shift(3)[-1]
        flo_price = dof['Low'].shift(3)[-1]
        fhi_forward = dof['fractals_high'].shift(4)[-1]
        flo_forward = dof['fractals_low'].shift(4)[-1]

        if(fhi == True):
            if len(self.val_resistance) > 0:                
                if fhi_price != self.val_resistance[-1]:
                    self.val_resistance.append(fhi_price)
                    self.state_val_resistance.append(1)
                    self.state_val_support.append(0)                    
            else:
                self.val_resistance.append(fhi_price)
                self.state_val_resistance.append(1)
                self.state_val_support.append(0)
        else:
            self.state_val_resistance.append(0)
            self.state_val_support.append(0)


        if(flo == True):
            if len(self.val_support) > 0:
                if flo_price != self.val_support[-1]:
                    self.val_support.append(flo_price)
                    self.state_val_support.append(1)
                    self.state_val_resistance.append(0)
            else:
                self.val_support.append(flo_price)
                self.state_val_support.append(1)
                self.state_val_resistance.append(0)
        else:
            self.state_val_support.append(0)
            self.state_val_resistance.append(0)

        ema10 = dof['ema10'][-1]
        curr_cci = dof['cci'][-1]
        last_cci = dof['cci'].shift(1)[-1]
        past_cci = dof['cci'].shift(2)[-1]

        is_cci_up = last_cci > past_cci
        is_cci_down = last_cci < past_cci
        cci_top = (last_cci > 100 and past_cci > 100) or curr_cci > 100
        cci_down = (last_cci < 100 and past_cci < 100) or curr_cci < 100

        is_upper_signal = (curr_price > ema10 and curr_open > ema10 and cl1 > ema10 and op1 > ema10) 
        is_lower_signal = (curr_price < ema10 and curr_open < ema10 and cl1 < ema10 and op1 < ema10) 

        is_up = (curr_price > cl1 and curr_price > curr_open and curr_price > hh1) 
        is_down = (curr_price < cl1 and curr_price < curr_open and curr_price < ll1)

        set_time_call = (2 if is_upper_signal == True else 1)
        set_time_put = (1 if is_upper_signal == True else 2)

        print(dof.tail(10))
        
        cross_ema_up = cl1 < ema10 and curr_price > ema10 and curr_price > curr_open
        cross_ema_down = cl1 > ema10 and curr_price < ema10 and curr_open < ema10

        print("cross_ema_up -> ", cross_ema_up)                
        print("cross_ema_down -> ", cross_ema_down)                
        print("is_upper_signal -> ", is_upper_signal)                
        print("is_lower_signal -> ", is_lower_signal)                
        print("is_up -> ", is_up)                
        print("is_down -> ", is_down)                
        print("val_support -> ", self.val_support)                
        print("val_resistance -> ", self.val_resistance)                

        hhres = self.val_resistance
        llsup = self.val_support

        if ctr % 10:

            if is_down == True and ha_down == True and curr_cci > -100:
                msg = "⬇ [[{}]] [[HEIKIN-ASHI-DOWN]] potentially SELL [[23011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))            
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price, set_time_put)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if is_up == True and ha_up == True and curr_cci < 100:
                msg = "⬆ [[{}]] [[HEIKIN-ASHI-UP]] potentially BUY [[23012]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price, set_time_call)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if cross_ema_down == True:
                msg = "⬇ [[{}]] [[CROSS-EMA-DOWN]] potentially SELL [[23013]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))            
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price, set_time_put)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if cross_ema_up == True:
                msg = "⬆ [[{}]] [[CROSS-EMA-UP]] potentially BUY [[23014]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price, set_time_call)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if ha_down == True and curr_cci > -100:
                msg = "⬇ [[{}]] [[HEIKIN-ASHI-DOWN]] potentially SELL [[23015]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))            
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price, set_time_put)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if ha_up == True and curr_cci < 100:
                msg = "⬆ [[{}]] [[HEIKIN-ASHI-UP]] potentially BUY [[23016]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price, set_time_call)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if fhi == True and is_down == True and curr_cci > -100:
                msg = "⬇ [[{}]] [[FRACTALS-15s-DOWN]] potentially SELL [[23017]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))            
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price, set_time_put)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if flo == True and is_up == True and curr_cci < 100:
                msg = "⬆ [[{}]] [[FRACTALS-15s-UP]] potentially BUY [[23018]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price, set_time_call)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

        if len(hhres) > 1 and len(llsup) > 1:   
            self.df_support = pd.DataFrame(llsup, columns=['support'])            
            self.df_resistance = pd.DataFrame(hhres, columns=['resistance'])       

            last_resistance= hhres[len(hhres)-1]
            past_resistance = hhres[len(hhres)-2]
            last_support = llsup[len(llsup)-1]
            past_support = llsup[len(llsup)-2]

            support_down = past_support > last_support
            support_up = last_support > past_support
            resistance_down = past_resistance > last_resistance
            resistance_up = last_resistance > past_resistance

            print("past_support -> ", past_support)                
            print("last_support -> ", last_support)                
            print("past_resistance -> ", past_resistance)                
            print("last_resistance -> ", last_resistance)
            print("fhi -> ", fhi)
            print("flo -> ", flo)
            print("support_down -> ", support_down)
            print("support_up -> ", support_up)
            print("resistance_down -> ", resistance_down)
            print("resistance_up -> ", resistance_up)
            print("support_down == True and resistance_down == True -> ", support_down == True and resistance_down == True)
            print("support_up == True and resistance_up == True -> ", support_up == True and resistance_up == True)

            if ctr % 5:
                if support_down == True and resistance_down == True and is_down == True and curr_cci > -100:
                    msg = "⬇ [[{}]] [[SR-DOWNTREND]] potentially SELL [[23019]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                    if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                        self.orderBuySell(4,"put",self.bid_price, set_time_put)
                        self.telegram_bot_sendtext(msg)                    
                        self.msg_buy = msg  
                        self.lasttime = str(timesx)

                if support_up == True and resistance_up == True and is_up == True  and curr_cci < 100:
                    msg = "⬆ [[{}]] [[SR-UPTREND]] potentially BUY [[23020]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                    if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                        self.orderBuySell(4,"call",self.bid_price, set_time_call)
                        self.telegram_bot_sendtext(msg)                    
                        self.msg_buy = msg  
                        self.lasttime = str(timesx)


    async def toDataframe(self, msg):            
        if msg['data'][0]['assets']:
            timex = int(msg["data"][0]["assets"][0]["created_at"].split(":")[-1].split(".")[0])
            data = msg["data"][0]["assets"][0]
            strdate = data['created_at']
            ctgl = dateutil.parser.parse(strdate)
            utc_time = calendar.timegm(ctgl.utctimetuple())
            udate = datetime.utcfromtimestamp(utc_time).strftime('%Y-%m-%d %H:%M:%S')
            data["Datetime"] = udate        
            data["spread"] = (data["ask"] - data["bid"]) * (10**8)
            djs = pd.DataFrame(data, columns=['Datetime','precision','repeat','rate','ask','bid','created_at', 'spread'], index=[0]).rename_axis(columns='Datetime')        
            if self.df.empty:
                self.df = pd.concat([djs], ignore_index=True)
            else:
                self.df = pd.concat([self.df,djs], ignore_index=True)

            await self.createDataframe(self.df)

    async def connect(self):        
        payload = '{"action":"subscribe","rics":["'+self.assetRic+'"]}'        
        async with self as websocket:        
            await websocket.send(payload)
            while True:                        
                print("> {}".format(payload))
                try:
                    recvv = await asyncio.wait_for(websocket.recv(), timeout=60)
                    # print("> {}".format(recvv))
                    rett = json.loads(recvv)                
                    if rett['data'][0]['action'] == 'assets':
                        #print("< {}".format(data))
                        await self.toDataframe(rett)
                    else:
                        print("return ws -> {}".format(rett)) 
                except asyncio.exceptions.CancelledError as e:
                    print(e)
                    websocket = await websockets.connect(self.pollHost,ssl=ssl.SSLContext(protocol=ssl.PROTOCOL_TLS))
                    await websocket.send('{"action":"subscribe","rics":["'+self.assetRic+'"]}')        
                    continue
                except websockets.exceptions.ConnectionClosedError as e:
                    websocket = await websockets.connect(self.pollHost,ssl=ssl.SSLContext(protocol=ssl.PROTOCOL_TLS))
                    await websocket.send('{"action":"subscribe","rics":["'+self.assetRic+'"]}')        
                    continue
                except asyncio.CancelledError as e:
                    websocket = await websockets.connect(self.pollHost,ssl=ssl.SSLContext(protocol=ssl.PROTOCOL_TLS))
                    await websocket.send('{"action":"subscribe","rics":["'+self.assetRic+'"]}')        
                    continue

    def telegram_bot_sendtext(self,bot_message):    
        send_text = 'https://api.telegram.org/bot' + self.botToken + '/sendMessage?chat_id=' + self.gchatId + '&parse_mode=Markdown&text=' + bot_message
        if self.telegram_channel_notification == True:
            response = requests.get(send_text)
            return response.json()
        else:
            print("-- Telegram channel notification off. --")

    def get_asset(self):
        with open("asset.json","r") as f:assetList=json.loads(f.read())
        with open("setting.json","r") as f:settings=json.loads(f.read())
        currency = settings["currency"]
        for i in assetList:
            if i["name"] == currency:assetId=i["id"]; assetRic=i["ric"]

        authToken = settings["authToken"]
        walletType = settings["walletType"]
        deviceId = settings["deviceId"]
        tournament_id = settings["tournament_id"]

        return {"assetId": assetId, "assetRic": assetRic, "currency":currency, "authToken": authToken, "deviceId": deviceId, "tournament_id": tournament_id, "walletType": walletType}

    def getOnlineData(self):
        binomodata = Ticker()
        data = binomodata.getData(self.dataintv)
        if len(data["d1"]) > 0:
            return data
        

    def orderBuySell(self, typeorder, call_put, amnt=15000, duration=1):
        try:
            self.pb.bid(typeorder, call_put, amnt, duration)
        except Exception as e:
            print(e)
        finally:
            pass

        balance = self.pb.getCurrentBalance()
        print("orderBuySell balance -> ", balance)
        self.setBalance(balance)

    def countOpenPosition(self):
        op = self.pb.openPosition()
        if op.empty:            
            return False
        else:
            result = op.query('close_rate == 0')             
            return True if len(result.index) > 0 else False

    def setBalance(self,lbalance):
        self.latest_balance = lbalance
        
    def getBalance(self):
        return self.latest_balance

    # https://github.com/koulakis/simple-heikin-ashi-trading-strategy-in-python/blob/master/heikin_ashi_tutorial.ipynb
    def heikin_ashi(self,df):    
        dt = df['Datetime']
        ha_close = (df['Open'] + df['Close'] + df['High'] + df['Low']) / 4

        ha_open = [(df['Open'].iloc[0] + df['Close'].iloc[0]) / 2]
        for close in ha_close[:-1]:
            ha_open.append((ha_open[-1] + close) / 2)    
        ha_open = np.array(ha_open)

        elements = df['High'], df['Low'], ha_open, ha_close
        ha_high, ha_low = np.vstack(elements).max(axis=0), np.vstack(elements).min(axis=0)
                
        return pd.DataFrame({
            'Datetime': dt,
            'ha_open': ha_open,
            'ha_high': ha_high,    
            'ha_low': ha_low,
            'ha_close': ha_close
        })         


    def heiken_ashi_strategy(self,df):
        
        current = df[1:]
        previous = df.shift(1)[1:]
        
        latest_bearish = current['ha_close'] < current['ha_open']
        previous_bearish = previous['ha_close'] < previous['ha_open']
        
        current_candle_longer = (
            np.abs(current['ha_close'] - current['ha_open']) 
            > np.abs(previous['ha_close'] - previous['ha_open']))
            
        current_open_eq_high = current['ha_open'] == current['ha_high']
        current_open_eq_low = current['ha_open'] == current['ha_low']
            
        llong = (
            latest_bearish 
            & current_candle_longer 
            & previous_bearish 
            & current_open_eq_high)
        short = (
            ~latest_bearish 
            & current_candle_longer 
            & ~previous_bearish 
            & current_open_eq_low)

        long_exit = (
            ~latest_bearish 
            & ~previous_bearish 
            & current_open_eq_low)
        short_exit = (
            latest_bearish 
            & previous_bearish 
            & current_open_eq_high)
            
        return pd.DataFrame(
            {'Datetime':current['Datetime'],
            'long': llong,
             'short': short,
             'long_exit': long_exit,
             'short_exit': short_exit},
            index=current.index)


if __name__ == '__main__':
    bit = Binongtot()
    asyncio.run(bit.connect())

