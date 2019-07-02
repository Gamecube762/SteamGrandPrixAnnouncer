# Steam GrandPrixAnnouncer

This is the code behind <https://twitter.com/SteamSaleEvents>

If you want to use this for watching the race stats only, just follow steps 1-3 of setup.

## Requirements

* [Python](https://www.python.org/) 3.6+
* `pip install websockets`

## Setup

### Install

1. Install [Python](https://www.python.org/) version 3.6 or above
2. `pip install websockets`
3. `python3 app.py`

### If you want the bot to tweet

4. Rename `twitAuth_example.json` to `twitAuth.json`
5. Place your twitter API keys into `twitAuth.json`

### If you want to record the packets of the race

6. Start the script with `python3 app.py -p`

## Todo

* Less spammy tweets
* Change profile pic to winning team