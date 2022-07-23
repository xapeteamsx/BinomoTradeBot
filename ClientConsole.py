from websocket import create_connection
from collections import Counter
import time, random, string, json, requests, datetime, threading, urllib.parse
import pandas as pd
import math

class Placebid():
    def __init__(self):
        self.uagent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
        self.df_martingale = pd.DataFrame()
        self.bet_result = pd.DataFrame()
        with open("asset.json","r") as f:self.assetList=json.loads(f.read())
        with open("setting.json","r") as f:self.settings=json.loads(f.read())
        self.amount = self.settings["amount"]
        self.authToken = self.settings["authToken"]
        self.currency = self.settings["currency"]
        self.walletType = self.settings["walletType"]
        self.deviceId = self.settings["deviceId"]
        self.tournament_id = self.settings["tournament_id"]
        self.max_loss_level = self.settings["max_loss_level"]
        self.loss_divider = self.settings["loss_divider"]
        self.round_value = self.settings["round_value"]
        bet_multiplier = self.settings["bet_multiplier"]
        self.count_loss = 0
        self.status_bet = False
        self.last_bet_amount = 0
        self.multi_bet_amount = bet_multiplier
        self.loss_bet = 0
        self.last_balance = 0
        self.new_balance = 0

        self.cookie = "l=; authtoken="+self.authToken+"; device_id="+self.deviceId+"; device_type=web"
        self.headers = {'User-Agent': self.uagent, 'Cookie': self.cookie}
        for i in self.assetList:
            if i["name"] == self.currency:self.assetId=i["id"]; self.assetRic=i["ric"]
        #self.pollHost = "wss://as.binomobroker.com/"
        self.apiHost = "wss://ws.binomo.com/?authtoken="+self.authToken+"&device_type=web&device_id="+self.deviceId+"&v=2&vsn=2.0.0"
        self.history=[]; self.lastSend=time.time(); self.ref=1; self.stop=False
        self.wsApi = create_connection(self.apiHost,header=self.headers)
        threading.Thread(target=self.hook,daemon=True).start()        
        #threading.Thread(target=self.pollingMarket,daemon=True).start()
        self.phxJoin()
        self.ping()

        self.istur = "null" if str(self.tournament_id) == "None" else str(self.tournament_id)
        print("tournament_id -> ", self.istur)
        
        if self.istur != "none":
            self.sendWs('{"topic":"tournament","event":"subscribe_tournament","payload":{"tournament_id":'+self.istur+'},"ref":"~~","join_ref":"4"}')

        print("[ CALLBACK OPERATION ] BOT STARTED...")
    
    def bid(self, tb, order_type, amnt, waktu):
        deal_amount = self.getBetAmount()
        losbet = self.getLossBet()        
        div_loss = self.round_up(losbet / 100)
        if int(deal_amount) > 0:
            if div_loss > (self.amount * 10):
                deal_amount = abs(self.round_up((div_loss / self.loss_divider) * self.multi_bet_amount))
            elif div_loss > self.amount and div_loss < (self.amount * 10) and div_loss > (self.amount * 3):
                deal_amount =  abs(self.round_up((div_loss / 3) * self.multi_bet_amount))
            elif div_loss < self.amount:
                deal_amount = abs(self.round_up((div_loss + self.amount) * self.multi_bet_amount))
            else:
                deal_amount = abs(self.round_up(deal_amount * self.multi_bet_amount))

            if deal_amount < self.amount:
                deal_amount = self.amount * self.multi_bet_amount
            
            lastchar = str(int(deal_amount))[-3:]
            rounded = int(self.round_value - (int(lastchar) if int(lastchar) > 0 else int(deal_amount)))
            deal_amount = int(deal_amount) + int(rounded)
        else:
            deal_amount = self.amount
            self.setBetAmount(int(deal_amount))
        
        self.typeBid(tb,order_type,int(deal_amount),waktu)

    def round_up(self, n, decimals=0):
        multiplier = 10 ** decimals
        return math.ceil(n * multiplier) / multiplier

    def getCurrentBalance(self):
        headers = {'device-id': self.deviceId, 'device-type': 'web','authorization-token': self.authToken, 'User-Agent': self.uagent}
        res = requests.get("https://api.binomo.com/bank/v1/read?locale=en",headers=headers).json()
        for i in res["data"]:
            if i["account_type"] == self.walletType:
                return i["amount"]/100

    def getHistoryMarket(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        return requests.get("https://api.binomo.com/platform/candles/"+urllib.parse.quote_plus(self.assetRic)+"/"+str(now)+"T00:00:00/60?locale=en",headers=self.headers).json()["data"]

    def parseBidTime(self, m=1):
        now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:00")
        bid = datetime.datetime.strptime(now, "%d/%m/%Y %H:%M:%S")+datetime.timedelta(minutes=m)
        return str(int(time.mktime(bid.timetuple())))

    # bid type
    def fastBid(self, status, amount, timees=1):
        if int(datetime.datetime.now().strftime("%S")) < 30:
            bidTime=self.parseBidTime()
        else:
            bidTime=self.parseBidTime(1)
        wstext = '{"topic":"bo","event":"create","payload":{"amount":'+str(amount*100)+',"created_at":'+str(int(time.time()))+',"ric":"'+self.assetRic+'","deal_type":"'+self.walletType+'","expire_at":'+bidTime+',"option_type":"turbo","trend":"'+status+'","tournament_id":'+self.istur+',"is_state":false},"ref":"~~","join_ref":"3"}'
        self.sendWs(wstext)

    def mediumBid(self, status, amount, timees=2):
        bidTime=self.parseBidTime(timees)
        wstext = '{"topic":"bo","event":"create","payload":{"amount":'+str(amount*100)+',"created_at":'+str(int(time.time()))+',"ric":"'+self.assetRic+'","deal_type":"'+self.walletType+'","expire_at":'+bidTime+',"option_type":"turbo","trend":"'+status+'","tournament_id":'+self.istur+',"is_state":false},"ref":"~~","join_ref":"3"}'
        self.sendWs(wstext)

    def slowBid(self, status, amount, timees=3):        
        if int(datetime.datetime.now().strftime("%S")) < 30:
            bidTime=self.parseBidTime()
        else:
            bidTime=self.parseBidTime(timees)
        wstext = '{"topic":"bo","event":"create","payload":{"amount":'+str(amount*100)+',"created_at":'+str(int(time.time()))+',"ric":"'+self.assetRic+'","deal_type":"'+self.walletType+'","expire_at":'+bidTime+',"option_type":"turbo","trend":"'+status+'","tournament_id":'+self.istur+',"is_state":false},"ref":"~~","join_ref":"3"}'        
        self.sendWs(wstext)

    def customBid(self, status, amount, timees=5):
        if int(datetime.datetime.now().strftime("%S")) < 30:
            bidTime=self.parseBidTime(timees)
        else:
            bidTime=self.parseBidTime(timees+1)        
        wstext = '{"topic":"bo","event":"create","payload":{"amount":'+str(amount*100)+',"created_at":'+str(int(time.time()))+',"ric":"'+self.assetRic+'","deal_type":"'+self.walletType+'","expire_at":'+bidTime+',"option_type":"turbo","trend":"'+status+'","tournament_id":'+self.istur+',"is_state":false},"ref":"~~","join_ref":"3"}'
        print("customBid -> ", wstext)
        self.sendWs(wstext)

    def defaultBid(self, status, amount, timees=1):
        if int(datetime.datetime.now().strftime("%S")) < 30:
            bidTime=self.parseBidTime()
        else:
            bidTime=self.parseBidTime(2)
        wstext = '{"topic":"bo","event":"create","payload":{"amount":'+str(amount*100)+',"created_at":'+str(int(time.time()))+',"ric":"'+self.assetRic+'","deal_type":"'+self.walletType+'","expire_at":'+bidTime+',"option_type":"turbo","trend":"'+status+'","tournament_id":'+self.istur+',"is_state":false},"ref":"~~","join_ref":"3"}'        
        print("defaultBid -> ", wstext)
        self.sendWs(wstext)

    def typeBid(self, tb, status, amount, timees):
        self.ping() 
        if tb == 1:
            self.fastBid(status, amount, 1)
        elif tb == 2:
            self.mediumBid(status, amount,2)
        elif tb == 3:
            self.slowBid(status, amount,3)
        elif tb == 4:
            self.customBid(status, amount,timees)
        else: 
            self.defaultBid(status, amount, 1)

    def openPosition(self):
        return self.df_martingale
        
    def hook(self):
        while True:
            try:
                data = json.loads(self.wsApi.recv())
                if len(data['event']) > 0:
                    if data["event"] == "deal_created":
                        print("[ CALLBACK OPERATION ] CREATED DEAL AMOUNT: "+str(int(data["payload"]["amount"]/100)))
                    elif data["event"] == "asset_changed_v1":
                        print("[ CALLBACK OPERATION ] ASSET RATE CHANGED: "+str(data["payload"]["trading_tools_settings"]["standard"]["payment_rate_standard"])+"%")
                        if data["payload"]["trading_tools_settings"]["standard"]["payment_rate_standard"] < 75:self.stop=True
                        else:
                            if self.stop:self.stop=False
                    
                    elif data["event"] == "close_deal_batch":
                        mrt = data["payload"]
                        close_rate = mrt['end_rate']
                        self.bet_result = pd.DataFrame([mrt])
                        martingale = self.df_martingale
                        search_martingale = martingale[martingale.eq("{}".format(mrt['finished_at'])).any(1)]
                        idxs = search_martingale.index
                        for idx in idxs:                            
                            seldata = martingale.iloc[idx]

                            if seldata['trend'] == 'put':
                                if seldata['open_rate'] > close_rate:
                                    self.status_bet = True
                                    losbet = self.getLossBet()
                                    losbet = losbet - seldata['amount'] 
                                    self.setLossBet(losbet)
                                    self.df_martingale.at[idx,'win']=True                                    
                                    self.df_martingale.at[idx,'close_rate']=close_rate

                                elif seldata['open_rate'] < close_rate:
                                    self.status_bet = False
                                    losbet = self.getLossBet()
                                    losbet = losbet + seldata['amount'] 
                                    self.setLossBet(losbet)
                                    self.df_martingale.at[idx,'win']=False     
                                    self.df_martingale.at[idx,'close_rate']=close_rate
                                    cl = self.count_loss + 1                                    
                                    self.setCountLoss(cl)

                            elif seldata['trend'] == 'call':
                                if  close_rate > seldata['open_rate']:
                                    self.status_bet = True
                                    losbet = self.getLossBet()
                                    losbet = losbet - seldata['amount'] 
                                    self.df_martingale.at[idx,'win']=True
                                    self.df_martingale.at[idx,'close_rate']=close_rate                                    
                                    self.setLossBet(losbet)

                                elif close_rate < seldata['open_rate']:
                                    self.status_bet = False
                                    losbet = self.getLossBet()
                                    self.df_martingale.at[idx,'win']=False
                                    self.df_martingale.at[idx,'close_rate']=close_rate                                    
                                    losbet = losbet + seldata['amount'] 
                                    cl = self.count_loss + 1                                    
                                    self.setCountLoss(cl)
                                    self.setLossBet(losbet)

                        losbet = self.getLossBet()
                        if (losbet / 100) <= 0:
                            self.setLossBet(0)                            
                            self.setBetAmount(self.amount)
                        else:
                            setbet = int((losbet / 100) * self.multi_bet_amount)
                            self.setBetAmount(setbet)   
                            self.setLossBet(losbet)

                        betamn = self.getBetAmount()

                        if self.getCountLoss() >= 2:
                            self.setCountLoss(0)
                            self.setBetAmount(self.amount)
                            self.setLossBet(losbet)
                        else:
                            setbet = int((losbet / 100) * self.multi_bet_amount)                            
                            self.setBetAmount(setbet)
                            self.setLossBet(losbet)

                        # save bet history to csv
                        self.df_martingale.to_csv("bet_result.csv")

                    elif data["event"] == "opened":
                        mrt = data["payload"]
                        mrt["win"] = False
                        mrt["close_rate"] = 0
                        dmrt = pd.DataFrame([mrt])
                        self.df_martingale = pd.concat([dmrt,self.df_martingale], ignore_index=True)                        
                    
                    else:print(data)

                    if (time.time() - self.lastSend) > 35:
                        print("[ CALLBACK OPERATION ] PHOENIX HEARTBEAT")
                        self.ping()                
                        self.sendWs('{"topic":"phoenix","event":"heartbeat","payload":{},"ref":"~~"}')
            except Exception as e:
                self.wsApi = create_connection(self.apiHost,header=self.headers)                
                self.phxJoin()
                self.ping()                
                print("Error hook -> ", e)

    def phxJoin(self):
        self.sendWs('{"topic":"account","event":"phx_join","payload":{},"ref":"1","join_ref":"1"}')
        self.sendWs('{"topic":"user","event":"phx_join","payload":{},"ref":"2","join_ref":"2"}')
        self.sendWs('{"topic":"bo","event":"phx_join","payload":{},"ref":"3","join_ref":"3"}')
        self.sendWs('{"topic":"tournament","event":"phx_join","payload":{},"ref":"4","join_ref":"4"}')
        self.sendWs('{"topic":"cfd_zero_spread","event":"phx_join","payload":{},"ref":"5","join_ref":"5"}')
        self.sendWs('{"topic":"asset","event":"phx_join","payload":{},"ref":"6","join_ref":"6"}')
        self.sendWs('{"topic":"asset:'+self.assetRic+'","event":"phx_join","payload":{},"ref":"7","join_ref":"7"}')

    def ping(self):
        self.sendWs('{"topic":"account","event":"ping","payload":{},"ref":"~~","join_ref":"1"}')
        self.sendWs('{"topic":"user","event":"ping","payload":{},"ref":"~~","join_ref":"2"}')
        self.sendWs('{"topic":"bo","event":"ping","payload":{},"ref":"~~","join_ref":"3"}')
        self.sendWs('{"topic":"tournament","event":"ping","payload":{},"ref":"~~","join_ref":"4"}')
        self.sendWs('{"topic":"cfd_zero_spread","event":"ping","payload":{},"ref":"~~","join_ref":"5"}')
        self.sendWs('{"topic":"asset","event":"ping","payload":{},"ref":"~~","join_ref":"6"}')
        self.sendWs('{"topic":"asset:'+self.assetRic+'","event":"ping","payload":{},"ref":"~~","join_ref":"7"}')

    def pollingMarket(self):
        ws = create_connection(self.pollHost,header=self.headers)
        ws.send('{"action":"subscribe","rics":["'+self.assetRic+'"]}')
        tempData={}; reset=False
        while True:
            try:
                data = json.loads(ws.recv())
                if "assets" in data["data"][0]:
                    timex = data["data"][0]["assets"][0]["created_at"].split(":")[-1].split(".")[0]
                    rate = data["data"][0]["assets"][0]["rate"]
                    if timex == "01":
                        if self.history == []:self.history = self.getHistoryMarket()
                        if reset:
                            if tempData["open"] > tempData["close"]:tempData["stat"]="put"
                            elif tempData["open"] < tempData["close"]:tempData["stat"]="call"
                            self.history.append(tempData)
                            print("[ CALLBACK OPERATION ] CANDLE: "+tempData["stat"].upper())
                            tempData={}; reset=False
                        if tempData == {}:tempData["low"]=rate;tempData["high"]=rate;tempData["open"]=rate
                        else:tempData["low"]=min(rate,tempData["low"]);tempData["high"]=max(rate,tempData["high"])
                    elif timex == "00" and tempData != {}:
                        if reset == False:reset=True
                        tempData["low"]=min(rate,tempData["low"]);tempData["high"]=max(rate,tempData["high"]);tempData["close"]=rate
                    elif tempData != {}:tempData["low"]=min(rate,tempData["low"]);tempData["high"]=max(rate,tempData["high"])
            except:
                ws = create_connection(self.pollHost,header=self.headers)
                ws.send('{"action":"subscribe","rics":["'+self.assetRic+'"]}')
    
    def setBetAmount(self, amount):
        self.last_bet_amount = amount

    def getBetAmount(self):
        return self.last_bet_amount

    def setLossBet(self, amount):
        self.loss_bet = amount

    def getLossBet(self):
        return self.loss_bet

    def setCountLoss(self, ct):
        self.count_loss = ct

    def getCountLoss(self):
        return self.count_loss

    def sendWs(self,data):
        sd = data.replace("~~",str(self.ref))
        try:
            print("sendWs() data -> ", sd)            
            self.wsApi.send(sd)
        except Exception as e:
            print(e)
        else:            
            print("sendWs() else -> ",sd)
        finally:
            pass

        self.ref+=1;self.lastSend = time.time()

    def run(self):
        while True:
            time.sleep(1)
