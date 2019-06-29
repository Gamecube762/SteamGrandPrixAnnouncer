import asyncio
import json
import random
import traceback
import websockets
import tweepy

TEAMS = [
    "Hare", # 1
    "Tortoise",
    "Corgi",
    "Cockatiel",
    "Pig" # 5
]

POSITIONS = [
    "1st",
    "2nd",
    "3rd",
    "4th",
    "5th"
]

#todo hourly stats

MESSAGES = {
    "leader": [
        "Team {} is now in the lead!",
        "Team {} is now in 1st!",
        "Team {} is now the leader!",
        "Team {} is now leading the race!",
        "Team {} has taken the lead!",
        "Team {} has stolen the lead!",
        "Team {} has taken 1st place!",
        "Team {} has stolen 1st place!",
        "Team {} ahead of the rest!"
    ],
    "tie": [
        "Teams {} are now tied!",
        "Teams {} are tied for 1st!",
        "Teams {} have tied!",
        "Teams {} are battling for 1st!",
        "Teams {} are battling for the lead!",
        "Teams {} are fighting for the lead!",
        "Teams {} are fighting for 1st!"
    ]
}

randMsg_leader = lambda leader: (random.choice(MESSAGES['leader']) if len(leader) == 1 else random.choice(MESSAGES['tie'])).format(formatLeader(leader))
formatLeader = lambda leader: teamName(leader[0]) if len(leader) == 1 else f"{', '.join([teamName(t) for t in leader[:len(leader)-1]])} and {teamName(leader[-1])}"
formatScore = lambda mult: int(mult*10)
teamName = lambda team: TEAMS[team['teamid']-1]

class GrandPrix():
    def __init__(self):
        self.twit = twitInit()
        self.sock = None

        self.leaders = []
        self.scores = []
        self.day = -1
        
        asyncio.get_event_loop().run_until_complete(self.main())

    def __del__(self):
        self.sock.close()

    async def connect(self):
        try:
            self.sock = await websockets.connect("wss://community.steam-api.com/websocket/")
            await self.sock.send(json.dumps({ "message": "subscribe", "seqnum": 1, "feed": "TeamEventScores" }))
        except:
            self.sock.close()

    async def main(self):
        while True:
            try:
                if not self.sock:
                    await self.connect()

                msg = await self.sock.recv()
            except KeyboardInterrupt:
                self.sock.close()
                exit()
            except Exception as e:
                print(e)
                await self.connect()
                continue

            print(msg)
            data = json.loads(msg)

            try:
                with open('db.txt', 'a') as f:
                    f.write(json.dumps(data) +'\n')
            except Exception:
                pass

            try:
                await self.parse(data)
            except KeyboardInterrupt:
                self.sock.close()
                exit()
            except Exception as e:
                traceback.print_exc(e)
    
    async def tweet(self, msg, retry = 5):
        try:
            print('Tweeting:', msg)
            self.twit.update_status(msg)
        except tweepy.error.TweepError as err:
            print('Failed to tweet:', err.api_code)
            if err.api_code == 187:
                if retry < 0:
                    return
                retry -= 1
                await asyncio.sleep(.1)
                await self.tweet(msg + '-', retry)

    async def parse(self, data):
        if ("message" in data and data['message'] == "feedupdate" and data['feed'] == "TeamEventScores"):
            feed = json.loads(data['data'])
            scores = feed['scores']
            scores.sort(key = lambda i: i['score_dist'], reverse = True)
            print(len(scores))
            leaders = [t for t in scores if 'score_dist' in t and t['score_pct'] == 1] # Check if scores exists | Day4 had no scores for the first msg
            print(len(leaders))
            leadersIDs = [t['teamid'] for t in leaders]
            leadermsg = randMsg_leader(leaders) if leaders else ""

            if feed['sale_day'] != self.day:
                if self.day != -1:
                    finalscores = self.scores if leaders == [] else scores
                    msg = f"Day {self.day+1} of the race has ended!\n1st {teamName(finalscores[0])}\n2nd {teamName(finalscores[1])}\n3rd {teamName(finalscores[2])}\n4th {teamName(finalscores[3])}\n5th {teamName(finalscores[4])}"
                    print(msg)
                    await self.tweet(msg)
                self.day = feed['sale_day']

            if checkLeaders(self.leaders, leadersIDs):
                if self.leaders != []:
                    print(leadermsg)
                    await self.tweet(leadermsg)
                self.leaders = leadersIDs
            
            self.scores = scores

            print(f"Day {feed['sale_day']+1} of the race!")
            print(leadermsg)
            print(f"TID{' '*5}Team{' '*2}Score dist{' '*10}score%{' '*15}Mult_raw{' '*18}total boost-deboost | Current boost-deboost")

            for team in scores:
                print(f"{team['teamid']} {TEAMS[team['teamid']-1]:>10}: {int(team['score_dist']):<10} {team['score_pct']:>20} {team['current_multiplier']:<25} {team['total_boosts']} - {team['total_deboosts']} = {int(team['total_boosts']) - int(team['total_deboosts'])} | {team['current_active_boosts']} - {team['current_active_deboosts']} = {team['current_active_boosts'] - team['current_active_deboosts']}")

def checkLeaders(old, new):
    if len(old) != len(new):
        return True
    
    for i in old:
        if i not in new:
            return True
    
    return False


def twitInit():
    with open('twitAuth.json', 'r') as f:
        j = json.load(f)

    twitauth = tweepy.OAuthHandler(j['consumer_key'], j['consumer_secret'])
    twitauth.set_access_token(j['access_token'], j['access_token_secret'])
    return tweepy.API(twitauth)

if __name__ == "__main__":
    gp = GrandPrix()