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

'''
#--- Candle to Candle Strategy (buy on bullish and sell when bearish and forward followed signal) ---#
Signal is ema8 
Candle over signal and upper mid-bb is bullish
Candle below signal and lower mid-bb is bearish
Bullish sign is indicated by last candle is upper signal
Bearish sign is indicated by last candle is lower signal
Last and past bearish signal lower mid-bb then touch midbb = try to short until appears next signal
Last and past bullish signal upper mid-bb then touch midbb = try to long until appears next signal
Do not open any position until appears new signal
Retest is when price below signal but last and past candle is over or below signal
This strategy is valid for 2-3 minutes and more (5 minutes)
CCI used for reversal signal
Note: Backtest result about this strategy is over 70% and this is the aggressive signal suitable for autonomous daily trade
This strategy already combined with martingale (https://en.wikipedia.org/wiki/Martingale_(probability_theory)) strategy as compensation for your loss trade
Contact us via telegram @apeteams or email xapeteamsx@gmail.com
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
        self.val_support = []
        self.val_resistance = []
        self.state_val_support = []
        self.state_val_resistance = []
        self.ctr_minute = 1
        self.msg_buy = ""
        self.msg_sell = ""        
        self.latest_balance = 0
        self.last_cci_c1 = 0
        self.last_cci_c2 = 0
        self.cci = 0
        self.is_reversal_up = False
        self.is_reversal_down = False
        self.telegram_channel_notification = False
        self.websocket_debug = False
        self.setSellTopSignal = False
        self.setBuyLowerSignal = False
        self.sidewaysUp = False
        self.sidewaysDown = False
        self.forwardSignalUp = False
        self.forwardSignalDown = False
        self.reversalUp = False
        self.reversalDown = False

        # set time and timezone
        timezone_offset = +7.0 
        self.tzinfo = timezone(timedelta(hours=timezone_offset))
        dtb = datetime.now(self.tzinfo)
        presentDate = dtb + timedelta(minutes=+1)
        self.curr_now = presentDate.strftime('%H:%M')
        self.lasttime = ""
        present_utc = datetime.now()
        utc_present = present_utc + timedelta(hours=-7) + timedelta(minutes=+1)
        self.curr_utc = utc_present.strftime('%H:%M')

        # setup telegram bot
        self.botToken = ''
        self.gchatId = ''
        
        self.tempbin = self.getOnlineData()
        self.pollHost = "wss://as.binomo.com/"
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

        data.index = pd.to_datetime(data.Datetime)
        df1 = data['rate'].resample('1Min').agg(
                                    {'open': 'first', 
                                     'high': 'max', 
                                     'low': 'min', 
                                     'close': 'last'})
        
        d1 = pd.DataFrame(df1).reset_index()
        d1.columns = ['Datetime','open', 'high','low','close']  

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

        self.mergeDataWSOnline(self.counter, d1)

    def mergeDataWSOnline(self, ctr, wsdata):        

        counter = ctr
        tempdata = {}
        historydata = []

        pd.set_option('display.float_format', '{:.11f}'.format)
        
        wsdata = wsdata.set_index('Datetime')

        curr_open = wsdata['open'][-1]

        cur_digits = str(curr_open).split('.')
        count_lencur = len(cur_digits[1])

        dtb = datetime.now(self.tzinfo)
        present_utc = datetime.now()
        #unix_timestamp = dtb.timestamp(presentDate)*1000
        presentDate = dtb + timedelta(minutes=+1)
        timesx = presentDate.strftime('%H:%M')

        present_utc = datetime.now()
        utc_present = present_utc + timedelta(hours=-7) + timedelta(minutes=+1)
        timesx_utc = utc_present.strftime('%H:%M')

        temp_dfol = self.tempbin["d1"]

        # merge data websocket and one-day history data
        df_ws = pd.DataFrame(wsdata, columns=['open', 'high', 'low','close'])
        wsdata_copy = df_ws.rename(columns = {'open':'Open', 'high':'High', 'low':'Low', 'close':'Close'})
        wsdata_copy['Datetime'] = pd.to_datetime(wsdata_copy.index) + timedelta(minutes=1)
        temp_dfol['Datetime'] = pd.to_datetime(temp_dfol.Datetime)
        wsdata_copy.index = wsdata_copy['Datetime']
        temp_dfol['Datetime'] = temp_dfol['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
        vol_copy = (wsdata_copy['High'] - wsdata_copy['Low']) - (wsdata_copy['Open'] - wsdata_copy['Close'])
        wsdata_copy['Volume'] = vol_copy

        # dropping last 1 row to avoid duplicate
        temp_dfol = temp_dfol.iloc[:-1]

        merge_ws_dataonline = pd.concat([temp_dfol, wsdata_copy]).drop_duplicates()
        merge_ws_dataonline.index = pd.to_datetime(merge_ws_dataonline.Datetime)
        merge_ws_dataonline["Volume"] = merge_ws_dataonline.Volume * (10 ** count_lencur)
        
        self.simple_strategy(ctr, merge_ws_dataonline, count_lencur, wsdata)


    def simple_strategy(self, ctr, merge_ws_dataonline, count_lencur, wsdata):

        dtb = datetime.now(self.tzinfo)
        present_utc = datetime.now()
        presentDate = dtb + timedelta(minutes=+1)
        timesx = presentDate.strftime('%H:%M')

        present_utc = datetime.now()
        utc_present = present_utc + timedelta(hours=-7) + timedelta(minutes=+1)
        timesx_utc = utc_present.strftime('%H:%M')
        
        curr_high = merge_ws_dataonline['High'][-1]
        curr_low = merge_ws_dataonline['Low'][-1]
        curr_open = merge_ws_dataonline['Open'][-1]
        curr_price = merge_ws_dataonline['Close'][-1]
        op1 = merge_ws_dataonline['Open'].shift(1)[-1]
        cl1 = merge_ws_dataonline['Close'].shift(1)[-1]
        cl2 = merge_ws_dataonline['Close'].shift(2)[-1]
        ll1 = merge_ws_dataonline['Low'].shift(1)[-1]
        ll2 = merge_ws_dataonline['Low'].shift(2)[-1]
        hh1 = merge_ws_dataonline['High'].shift(1)[-1]
        hh2 = merge_ws_dataonline['High'].shift(1)[-1]

        ind = Indicators(merge_ws_dataonline)
        ind.bollinger_bands()
        ind.ema(period=8, column_name='ema8', apply_to='Close')   
        ind.cci()             
        dof = ind.df

        curr_cci = dof['cci'][-1]
        last_cci = dof['cci'].shift(1)[-1]
        past_cci = dof['cci'].shift(2)[-1]

        boltop = dof['bollinger_top'][-1]
        bolmid = dof['bollinger_mid'][-1]
        boltom = dof['bollinger_bottom'][-1]
        ema8 = dof['ema8'][-1]
        past_candle = merge_ws_dataonline.shift(2)['Close'][-1]
        last_candle = merge_ws_dataonline.shift(1)['Close'][-1]
        is_last_candle_upper_signal = last_candle > ema8
        is_past_candle_upper_signal = past_candle > ema8
        is_curr_candle_upper_signal = curr_price > ema8

        is_still_up_cci = curr_cci > last_cci and curr_low > ll1
        is_still_down_cci = curr_cci < last_cci and curr_high < hh1
        stop_buy = (curr_cci < last_cci and last_cci < past_cci) and (past_cci >= 100 and last_cci >= 100)
        stop_sell = (curr_cci > last_cci and curr_cci > past_cci) and (past_cci <= -100 and last_cci <= -100)

        one_candle_signal_sell = curr_price < cl1 and curr_high < hh1 and stop_buy == True
        one_candle_signal_buy = curr_price > cl1 and curr_high > hh1 and stop_sell == True

        is_upper_bb = (curr_price > bolmid and cl1 > bolmid)
        is_upper_signal = (curr_price > ema8 and cl1 > bolmid)
        set_time_call = (3 if is_upper_bb == True else 1)
        set_time_put = (1 if is_upper_bb == True else 3)

        set_time_cci_call = (2 if is_upper_bb == True else 1)
        set_time_cci_put = (1 if is_upper_bb == True else 2)

        # get highest and lowest price from past and current 3 candles
        get_max_high = dof[['High', 'High', 'High']].max().max() 
        get_min_low = dof[['Low', 'Low', 'Low']].min().min() 

        param_up = (curr_price > cl1 or curr_price > hh1 or curr_price <= get_min_low)
        param_down = (curr_price < cl1 or curr_price < ll1 or curr_price >= get_max_high)

        param_buy_low = (curr_price < op1 or curr_price < ll1)
        param_sell_high = (curr_price > op1 or curr_price > hh1)

        print("curr_low -> ", merge_ws_dataonline['Low'][-1])
        print("curr_high -> ", merge_ws_dataonline['High'][-1])
    
        print("get_max_high -> ", get_max_high)
        print("get_min_low -> ", get_min_low)
        
        ctr_exec = 20
        
        if ctr % 5:

            #---------- handle sideways market ----------#
            if is_last_candle_upper_signal == True and is_past_candle_upper_signal == True and (curr_price <= ema8) and is_still_up_cci == True and stop_buy == False and stop_sell == True and param_buy_low == True:
                print("Sideways BUY signal detected... trying to long")
                self.setSidewaysUp(True)

            if self.getSidewaysUp() == True and is_last_candle_upper_signal == True and is_past_candle_upper_signal == True and (curr_price <= ema8) and is_still_up_cci == True and stop_buy == False and stop_sell == True and param_buy_low == True:
                msg = "⬆️ [[{}]] [[WS]] [[SIDEWAYS-EMA-UP]] potentially BUY [[23011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price, set_time_call)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if is_last_candle_upper_signal == False and is_past_candle_upper_signal == False and (curr_price >= ema8) and stop_sell == False and stop_buy == True and param_sell_high == True:
                print("Sideways SELL signal detected... trying to short")
                self.setSidewaysDown(True)

            if self.getSidewaysDown() == True and is_last_candle_upper_signal == False and is_past_candle_upper_signal == False and (curr_price >= ema8) and stop_sell == False and stop_buy == True and param_sell_high == True:
                msg = "⬇️ [[{}]] [[WS]] [[SIDEWAYS-EMA-DOWN]] potentially SELL [[23033]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price, set_time_put)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)


            if is_last_candle_upper_signal == True and is_past_candle_upper_signal == True and (curr_price > ema8) and stop_buy == False and param_buy_low == True:
                print("BUY at lower signal detected... trying to long")
                self.setBuylower(True)

            if self.getBuyLower() == True and is_last_candle_upper_signal == True and is_past_candle_upper_signal == True and (curr_price > ema8) and stop_buy == False and param_buy_low == True:
                msg = "⬆️ [[{}]] [[WS]] [[LOWEST-EMA-UP]] potentially BUY [[23011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price,set_time_cci_call)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if is_last_candle_upper_signal == False and is_past_candle_upper_signal == False and (curr_price < ema8) and stop_sell == False and param_sell_high == True:
                print("Sell at TOP signal detected... trying to sell")
                self.setSellTop(True)

            if self.getSellTop() == True and is_last_candle_upper_signal == False and is_past_candle_upper_signal == False and (curr_price < ema8) and stop_sell == False and param_sell_high == True:
                msg = "⬇️ [[{}]] [[WS]] [[TOP-EMA-DOWN]] potentially SELL [[23011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price,set_time_cci_put)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)
            
            if is_last_candle_upper_signal == True and is_past_candle_upper_signal == True and (curr_price > ema8) and stop_buy == False and stop_sell == True and param_up == True:
                print("Forward signal detected... trying to long")
                self.setforwardSignalUp(True)

            if self.getforwardSignalUp() == True and is_last_candle_upper_signal == True and is_past_candle_upper_signal == True and (curr_price > ema8) and stop_buy == False:
                msg = "⬆️ [[{}]] [[WS]] [[FORWARD-EMA-UP]] potentially BUY [[23011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price,2)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if is_last_candle_upper_signal == False and is_past_candle_upper_signal == False and (curr_price < ema8) and stop_sell == False and stop_buy == True param_down == True:
                print("Forward bearish signal detected... trying to short")
                self.setforwardSignalDown(True)

            if self.getforwardSignalDown() == True and is_last_candle_upper_signal == False and is_past_candle_upper_signal == False and (curr_price < ema8) and stop_sell == False:
                msg = "⬇️ [[{}]] [[WS]] [[FORWARD-EMA-DOWN]] potentially SELL [[23011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price,2)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if is_last_candle_upper_signal == True and (curr_price > ema8) and is_still_up_cci == False and is_still_down_cci == True and one_candle_signal_sell == True:
                print("Reversal SELL signal detected... trying to short")
                self.setreversalDown(True)

            if self.getreversalDown() == True and is_last_candle_upper_signal == True and (curr_price > ema8) and is_still_up_cci == False and is_still_down_cci == True and one_candle_signal_sell == True:
                msg = "⬇️ [[{}]] [[WS]] [[SIMPLE-EMA-UP]] potentially SELL [[23011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price,2)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if is_last_candle_upper_signal == False and (curr_price < ema8) and is_still_down_cci == False  and is_still_up_cci == True and one_candle_signal_buy == True:
                print("Reversal BUY signal detected... trying to long")
                self.setreversalUp(True)

            if self.getreversalUp() == True and is_last_candle_upper_signal == False and (curr_price < ema8) and is_still_down_cci == False  and is_still_up_cci == True and one_candle_signal_buy == True:
                msg = "⬆️ [[{}]] [[WS]] [[SIMPLE-EMA-DOWN]] potentially BUY [[23033]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price, set_time_put)
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
        data = binomodata.getData()
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

    def setBuylower(self,signal):
        self.setBuyLowerSignal = signal
        
    def getBuyLower(self):
        return self.setBuyLowerSignal

    def setSellTop(self,signal):
        self.setSellTopSignal = signal

    def getSellTop(self):
        return self.setSellTopSignal

    def setSidewaysUp(self,signal):
        self.sidewaysUp = signal

    def getSidewaysUp(self):
        return self.sidewaysUp

    def setSidewaysDown(self,signal):
        self.sidewaysDown = signal

    def getSidewaysDown(self):
        return self.sidewaysDown

    def setforwardSignalUp(self,signal):
        self.forwardSignalUp = signal

    def getforwardSignalUp(self):
        return self.forwardSignalUp

    def setforwardSignalDown(self,signal):
        self.forwardSignalDown = signal

    def getforwardSignalDown(self):
        return self.forwardSignalDown

    def setreversalUp(self,signal):
        self.reversalUp = signal

    def getreversalUp(self):
        return self.reversalUp

    def setreversalDown(self,signal):
        self.reversalDown = signal

    def getreversalDown(self):
        return self.reversalDown

if __name__ == '__main__':
    bit = Binongtot()
    asyncio.run(bit.connect())
