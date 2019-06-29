import asyncio
import json
import websockets
import tweepy
from importlib import reload

TEAMS = [
    "Hare",  # 1
    "Tortoise",
    "Corgi",
    "Cockatiel",
    "Pig"  # 5
]

def formatScore(mult): return int(mult*10)
def teamName(team): return TEAMS[team['teamid']-1]

class GrandPrix():
    def __init__(self):
        self.twit = twitInit()
        self.sock = None

        self.leaders = []
        self.day = -1
        asyncio.get_event_loop().run_until_complete(self.main())

    def __del__(self):
        self.sock.close()

    async def connect(self):
        try:
            self.sock = await websockets.connect("wss://community.steam-api.com/websocket/")
            await self.sock.send(json.dumps({"message": "subscribe", "seqnum": 1, "feed": "TeamEventScores"}))
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
                    f.write(json.dumps(data) + '\n')
            except Exception:
                pass

            try:
                await self.parse(data)
            except Exception as e:
                print(f"Error: {e}")

    async def tweet(self, msg, retry=5):
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
            scores.sort(key=lambda i: i['score_pct'], reverse=True)
            leaders = [t for t in scores if t['score_pct'] == 1]
            leadersIDs = [t['teamid'] for t in scores if t['score_pct'] == 1]
            leadermsg = msg = f"Team {teamName(leaders[0])} has taken the lead!" if len(leaders) == 1 else f"Teams {', '.join([teamName(t) for t in leaders[:len(leaders)-1]])} and {teamName(leaders[-1])} are tied!"

            if feed['sale_day'] != self.day:
                if self.day != -1:
                    msg = f"Day {self.day+1} of the race has ended!\n1st {teamName(scores[0])}\n2nd {teamName(scores[1])}\n3rd {teamName(scores[2])}\n4th {teamName(scores[3])}\n5th {teamName(scores[4])}"
                    print(msg)
                    await self.tweet(msg)
                self.day = feed['sale_day']

            if checkLeaders(self.leaders, leadersIDs):
                if self.leaders != []:
                    print(leadermsg)
                    await self.tweet(leadermsg)
                self.leaders = leadersIDs

            print(f"Day {feed['sale_day']+1} of the race!")
            print(leadermsg)
            print(f"TID{' '*5}Team{' '*2}Score%{' '*15}Mult_raw{' '*13}Mult_formatted")

            for team in scores:
                print(f"{team['teamid']} {TEAMS[team['teamid']-1]:>10}: {team['score_pct']:<20} {team['current_multiplier']:<20} {formatScore(team['current_multiplier']):02} {team['total_deboosts']}")

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
