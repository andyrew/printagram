import requests
import json
import os
from datetime import datetime
from pytz import timezone
import sys
from pathlib import Path
import traceback

from apscheduler.schedulers.blocking import BlockingScheduler


local_timezone = 'US/Pacific'

#Class for following instagram account
class InstagramAccount:
    def __init__(self, user_id, access_token, username, filename):
        self.user_id = user_id
        self.access_token = access_token
        self.username = username
        #file for storing lastest post id (for persistence if the power is lost)
        self.filename = filename
        try:
            with open(self.filename, 'r') as f:
                self.previous_post_ids = [line.rstrip() for line in f]
        except:
            self.previous_post_ids = []
    
    #checks for new posts
    def check_for_post(self):
        #get users most recent post
        try:
            media_request = f'https://graph.instagram.com/{self.user_id}/media?access_token={self.access_token}'
        except Exception as err:
            print("error checking for posts. request and response follow")
            print()
            traceback.print_tb(err.__traceback__)
            sys.exit()

        try:
            self.currentmedia = requests.get(media_request)
            self.currentpost_id = self.currentmedia.json()["data"][0]["id"]

        except Exception as err:
            print("error checking for posts. request and response follow")
            print(media_request)
            print(self.currentmedia)
            print(self.currentmedia.json())
            print()
            traceback.print_tb(err.__traceback__)
            sys.exit()

        #check if the most recent post is new or the same as the last post, if not, get new post
        if not self.currentpost_id in self.previous_post_ids:
            try:
                post_request = f'https://graph.instagram.com/{self.currentpost_id}?fields=id,media_type,media_url,username,timestamp,thumbnail_url,caption&access_token={self.access_token}'
                self.currentpost = requests.get(post_request)

            except Exception as err:
                print("error retrieving post. request and response follow")
                print(post_request)
                print(self.currentpost)
                print(self.currentpost.json())
                print()
                traceback.print_tb(err.__traceback__)
                sys.exit()                

            self.print_insta()
            #update lastpost_id to new post ide
            self.previous_post_ids.append(self.currentpost_id)
            #write lastpost_id to file
            try:
                with open(self.filename, 'a+') as f:
                    f.write(self.currentpost_id + '\n')
            except:
                pass
    
    #prints post
    def print_insta(self):
        username = self.currentpost.json()["username"]
        caption = self.currentpost.json()["caption"]
        time_string = self.currentpost.json()["timestamp"]
        timestamp_utc = datetime.strptime(time_string,"%Y-%m-%dT%H:%M:%S%z")
        timestamp_local = timestamp_utc.astimezone(timezone(local_timezone))
        time_string_formatted = timestamp_local.strftime("%-I:%M %p\n%A, %B %d, %Y")

        if self.currentpost.json()["media_type"] == "IMAGE":
            photo = self.currentpost.json()['media_url']
        elif self.currentpost.json()["media_type"] == "VIDEO":
            photo = self.currentpost.json()['thumbnail_url']
        elif self.currentpost.json()["media_type"] == "CAROUSEL_ALBUM":
            photo = self.currentpost.json()['media_url']

        #print photo
        os.system(f'wget -q -O - \'{photo}\' | lp -o fit-to-page')
        #print username and caption
        os.system(f'echo -n "{username}\n{caption}\n\n{time_string_formatted}" | lp -o cpi=20')

    def refresh_token(self):
        try:
            refresh_request = f'https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token={self.access_token}'
            response = requests.get(refresh_request)
            self.access_token = response.json()["access_token"]

        except Exception as err:
            print("error refreshing access_token. request and response follow")
            print(refresh_request)
            print(response)
            print(response.json())
            print()
            traceback.print_tb(err.__traceback__)
            sys.exit()


# Function to check posts for each object
def checking(account_objects):
    for acct in account_objects:
        acct.check_for_post()

def refresh_tokens(account_objects, config_file):
    for acct in account_objects:
        acct.refresh_token()

    act_configs = { "accounts": [] }
    for acct in account_objects:
        act_configs["accounts"].append({
                "username": acct.username,
                "access_token": acct.access_token,
                "user_id": acct.user_id
            })

    #re-write config file
    with open(config_file, 'w') as out_file:
        json.dump(act_configs, out_file)



def main():
    home = str(Path.home())
    basedirectory = f'{home}/.printagram/'
    if not Path(basedirectory):
        os.makedirs(basedirectory)

    if len(sys.argv) > 1:
        #load configs from file passed as argument
        config_file = sys.argv[1]
    else:
        #look for config file in home directory
        config_file = f'{basedirectory}instagram_accounts.json'
        if not Path(config_file).is_file():
            print('Can\'t find config json file')
            print(config_file)
            sys.exit()

    #Load access tokens from JSON
    accounts =[]

    with open(config_file, 'r') as config:
        acts = json.load(config)
        for account in acts["accounts"]:
            #instantiate InstagramAccount objects for each user
            accounts.append(
                InstagramAccount(   account["user_id"],
                                    account["access_token"],
                                    account["username"],
                                    f'{basedirectory}{account["username"]}.txt'
                                )
                )


    ###### This is the scheduling part.
    # Cron like python scheduler
    sched = BlockingScheduler()
    sched.add_job(checking,'cron', args=[accounts], year='*',month='*',day='*',week='*',day_of_week='*',hour='8-23', minute='*/2', second='0')
    sched.add_job(refresh_tokens,'cron', args=[accounts, config_file], year='*',month='*',day='1,15',hour='6', minute='0', second='0')
    sched.start()

if __name__ == '__main__':
    main()

