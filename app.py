import asyncio
import json
import random
import traceback
import websockets
import tweepy

from datetime import datetime
from os.path import exists

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
    ],
    "leaderboard": [
        "1st {}\n2nd {}\n3rd {}\n4th {}\n5th {}",
        "1st {} - {:,}km\n2nd {} - {:,}km\n3rd {} - {:,}km\n4th {} - {:,}km\n5th {} - {:,}km",
    ]
}

randMsg_leader = lambda leader: (random.choice(MESSAGES['leader']) if len(leader) == 1 else random.choice(MESSAGES['tie'])).format(formatLeader(leader))
formatLeader = lambda leader: teamName(leader[0]) if len(leader) == 1 else f"{', '.join([teamName(t) for t in leader[:len(leader)-1]])} and {teamName(leader[-1])}"
teamName = lambda team: TEAMS[team['teamid']-1]
calcHour = lambda hour: hour-16+(0 if hour > 16 else 24)
calcSpeed = lambda newStat, oldStat: (newStat['score_dist'] - oldStat['score_dist']) * 3200

class GrandPrix():
    def __init__(self, recordPackets = False, replayMode = False):
        self.recordPackets = recordPackets
        self.replaymode = replayMode

        self.twit = twitInit() if not replayMode else None
        self.sock = None

        self.leaders = []
        self.scores = []
        self.day = -1
        self.hour = -1
        
        asyncio.get_event_loop().run_until_complete(self.main() if not replayMode else self.main_replaymode())

    def __del__(self):
        if self.sock: self.sock.close()

    async def connect(self):
        try:
            self.sock = await websockets.connect("wss://community.steam-api.com/websocket/")
            await self.sock.send(json.dumps({ "message": "subscribe", "seqnum": 1, "feed": "TeamEventScores" }))
        except Exception as e:
            self.sock.close()
            raise e

    async def main(self):
        while True:

            try:
                # Connect if socket doesn't exist
                if not self.sock: await self.connect()
                
                # Receive message
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

            # Log packets to file
            if self.recordPackets:
                try:
                    with open('db.txt', 'a') as f: f.write(json.dumps(data) +'\n')
                except Exception:
                    print("Failed to write to 'db.txt'")

            # Parse data, print errors and continue
            try:
                await self.parse(data)
            except Exception as e:
                traceback.print_exc(e)
    
    async def main_replaymode(self):
        if not exists('replay.txt'):
            print("'replay.txt' not found!")
            return

        with open('replay.txt', 'r') as f:
            lines = [l for l in f.readlines() if l.strip()]
            print(f"Replaying {len(lines)} packets.")

            for msg in lines:
                print(msg)
                data = json.loads(msg)

                # Parse data, print errors and continue
                try:
                    await self.parse(data)
                except Exception as e:
                    traceback.print_exc(e)

    async def tweet(self, msg):
        if not self.twit: return

        print('Tweeting:', msg)

        try:
            self.twit.update_status(msg)
        except tweepy.error.TweepError as err:
            print('Failed to tweet:', err.api_code)

    async def parse(self, data):
        if ("message" in data and data['message'] == "feedupdate" and data['feed'] == "TeamEventScores"):
            feed = json.loads(data['data'])
            scores = feed['scores']
            scores.sort(key = lambda i: i['score_dist'], reverse = True)
            leaders = [t for t in scores if 'score_dist' in t and t['score_pct'] == 1] # Check if scores exists | Day4 had no scores for the first msg
            leadersIDs = [t['teamid'] for t in leaders]
            leadermsg = randMsg_leader(leaders) if leaders else ""
            currentHour = calcHour(datetime.utcnow().hour) #UTC time for consitency

            # Final team placements
            if feed['sale_day'] != self.day:
                if self.day != -1:
                    msg = f"Day {self.day+1} of the race has ended!\n" + MESSAGES['leaderboard'][1].format(
                        teamName(self.scores[0]), int(self.scores[0]['score_dist']),
                        teamName(self.scores[1]), int(self.scores[1]['score_dist']), 
                        teamName(self.scores[2]), int(self.scores[2]['score_dist']), 
                        teamName(self.scores[3]), int(self.scores[3]['score_dist']), 
                        teamName(self.scores[4]), int(self.scores[4]['score_dist'])
                    )
                    print(msg)
                    await self.tweet(msg)
                self.day = feed['sale_day']

            # Temp disabled in favor of Hourly leaderboard (It's just gonna be 1 tweet of Corgi in lead again, lets get something tweeting)
            # TODO System to reduce spam
            # Check Team placement
            #if checkLeaders(self.leaders, leadersIDs):
            #    if self.leaders != []:
            #        print(leadermsg)
            #        await self.tweet(leadermsg)
            #        self.leaders = leadersIDs
            
            # Hourly Leaderboard
            if currentHour != self.hour:
                if self.hour != -1 and currentHour > 1: # Skip hour 1
                    msg = f"Entering hour {currentHour} of the race:\n"
                    
                    if currentHour == 24:
                        msg = "Entering the final hour of the race!\n"
                    
                    msg += MESSAGES['leaderboard'][1].format(
                        teamName(scores[0]), int(scores[0]['score_dist']),
                        teamName(scores[1]), int(scores[1]['score_dist']), 
                        teamName(scores[2]), int(scores[2]['score_dist']), 
                        teamName(scores[3]), int(scores[3]['score_dist']), 
                        teamName(scores[4]), int(scores[4]['score_dist'])
                    )
                    
                    print(msg)
                    await self.tweet(msg)
                self.hour = currentHour

            print(f"Hour {currentHour} in Day {feed['sale_day']+1} of the race!")
            print(f"Leader(s): {formatLeader(leaders)}")
            print(f"TID{' '*5}Team{' '*4}Score{' '*7}Speed/hr{' '*5}Score%{' '*2}Mult_raw{' '*10}Total boost-deboost{' '*20}Current boost-deboost")

            for i in range(len(scores)):
                team = scores[i]
                speed = calcSpeed(team, self.scores[i]) if self.scores else 0
                totalBoost = f"{int(team['total_boosts']):>10,} - {int(team['total_deboosts']):>10,} = {int(team['total_boosts']) - int(team['total_deboosts']):>10,}"
                currentBoost = f"{team['current_active_boosts']:>10,} - {team['current_active_deboosts']:>10,} = {team['current_active_boosts'] - team['current_active_deboosts']:>10,}"
                print(f"{team['teamid']} {TEAMS[team['teamid']-1]:>10}: {team['score_dist']:>7.2f}km{' '*3}{speed:>7.2f}km/hr{' '*3}{team['score_pct']:.3f}{' '*3}{team['current_multiplier']:.5f}  | {totalBoost:37} | {currentBoost:37}")

            self.scores = scores


def checkLeaders(old, new):
    if len(old) != len(new):
        return True
    
    for i in old:
        if i not in new:
            return True
    
    return False


def twitInit():
    if not exists('twitAuth.json'):
        print("'twitAuth.json' not found. Bot wont tweet.")
        return None

    with open('twitAuth.json', 'r') as f:
        j = json.load(f)

    twitauth = tweepy.OAuthHandler(j['consumer_key'], j['consumer_secret'])
    twitauth.set_access_token(j['access_token'], j['access_token_secret'])
    return tweepy.API(twitauth)

if __name__ == "__main__":
    from sys import argv
    gp = GrandPrix(
        recordPackets = '-p' in argv or '--recordPackets' in argv,
        replayMode = '-r' in argv or '--replay' in argv
    )