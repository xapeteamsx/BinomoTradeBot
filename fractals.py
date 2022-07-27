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
        self.botToken = self.assetConf["botToken"]
        self.gchatId = self.assetConf["gchatId"]
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
        
        self.fractals_strategy(ctr, merge_ws_dataonline, count_lencur, wsdata)


    def fractals_strategy(self, ctr, merge_ws_dataonline, count_lencur, wsdata):

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
        op2 = merge_ws_dataonline['Open'].shift(2)[-1]
        cl1 = merge_ws_dataonline['Close'].shift(1)[-1]
        cl2 = merge_ws_dataonline['Close'].shift(2)[-1]
        ll1 = merge_ws_dataonline['Low'].shift(1)[-1]
        ll2 = merge_ws_dataonline['Low'].shift(2)[-1]
        hh1 = merge_ws_dataonline['High'].shift(1)[-1]
        hh2 = merge_ws_dataonline['High'].shift(1)[-1]

        ind = Indicators(merge_ws_dataonline)
        ind.bollinger_bands()
        ind.ema(period=8, column_name='ema8', apply_to='Close')   
        ind.fractals(column_name_high='fractals_high', column_name_low='fractals_low')
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

        #cci
        curr_cci = dof['cci'][-1]
        last_cci = dof['cci'].shift(1)[-1]
        past_cci = dof['cci'].shift(2)[-1]

        boltop = dof['bollinger_top'][-1]
        bolmid = dof['bollinger_mid'][-1]
        boltom = dof['bollinger_bottom'][-1]
        ema8 = dof['ema8'][-1]
        
        is_upper_bb = (curr_price > ema8 and cl1 > ema8)
        is_upper_signal = (curr_price > ema8 and cl1 > ema8)

        set_time_call = (3 if is_upper_signal == True else 1)
        set_time_put = (2 if is_upper_signal == True else 1)

        # get highest and lowest price from past and current 3 candles
        doh = dof.tail(3)
        get_max_high = doh[['High', 'High', 'High']].max().max() 
        get_min_low = doh[['Low', 'Low', 'Low']].min().min() 

        print("DataFrame -> ", dof.tail(10))
        print("curr_low -> ", merge_ws_dataonline['Low'][-1])
        print("curr_high -> ", merge_ws_dataonline['High'][-1])
        print("get_max_high -> ", get_max_high)
        print("get_min_low -> ", get_min_low)
        print("is_upper_signal -> ", is_upper_signal)

        ctr_exec = 20
        param_boltom = boltom - 10
        param_boltop = boltop - 10
        
        if ctr % 5:

            if fhi == True and (curr_price < hh1 and curr_price < op1) and curr_price < param_boltom:
                msg = "⬇ [[{}]] [[WS]] [[FRACTALS-DOWN]] potentially SELL [[23011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price, set_time_call)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if flo == True and (curr_price > ll1 and curr_price > cl1) and curr_price < param_boltop:
                msg = "⬆ [[{}]] [[WS]] [[FRACTALS-UP]] potentially BUY [[23012]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price, set_time_call)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if fhi_forward == True and (curr_price < ll1 and curr_price < curr_open) and ctr > ctr_exec:
                msg = "⬇ [[{}]] [[WS]] [[FRACTALS-FWD-DOWN]] potentially SELL [[25011]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"put",self.bid_price, set_time_call)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if flo_forward == True and (curr_price > hh1 and curr_price > curr_open) and ctr > ctr_exec:
                msg = "⬆ [[{}]] [[WS]] [[FRACTALS-FWD-UP]] potentially BUY [[25012]] - UTC7 {} | UTC0 {}".format(self.currency, str(timesx), str(timesx_utc))                
                if (msg != self.msg_buy) and (self.lasttime != str(timesx)):
                    self.orderBuySell(4,"call",self.bid_price, set_time_call)
                    self.telegram_bot_sendtext(msg)                    
                    self.msg_buy = msg  
                    self.lasttime = str(timesx)

            if len(self.val_resistance) > 0 and len(self.val_support) > 0:
                get_fhi_price = self.val_resistance[-1]
                get_flo_price = self.val_support[-1]
                print("val_support -> ", self.val_support)
                print("val_resistance -> ", self.val_resistance)                
                print("get_fhi_price -> ", get_fhi_price)
                print("get_flo_price -> ", get_flo_price)


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

        botToken = settings["botToken"]
        gchatId = settings["gchatId"]
        authToken = settings["authToken"]
        walletType = settings["walletType"]
        deviceId = settings["deviceId"]
        tournament_id = settings["tournament_id"]

        return {"assetId": assetId, "assetRic": assetRic, "currency":currency, "authToken": authToken, "deviceId": deviceId, "tournament_id": tournament_id, "walletType": walletType, "botToken": botToken, "gchatId": gchatId}

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

if __name__ == '__main__':
    bit = Binongtot()
    asyncio.run(bit.connect())

