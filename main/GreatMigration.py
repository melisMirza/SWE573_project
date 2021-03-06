import psycopg2
from configparser import ConfigParser
import json, tweepy, requests, sys, subprocess, os
import pandas as pd 
from tweepy import StreamListener
from tweepy import Stream
import string, nltk,re, emot,tagme
from nltk.corpus import stopwords as ntStop
from wordcloud import STOPWORDS as wcStop
from textblob import TextBlob
from emot.emo_unicode import UNICODE_EMO, EMOTICONS
import Cleaner, Analyzer
from Tweet import Tweet
from pathlib import Path

####
# SCRIPT USED FOR MIGRATING DATA FROM LOCAL DB TO HEROKU DB
# RETWEET AND FAVOURITE COUNTS ARE UPDATED BY MIGRATION
# RAN FOR ONCE. NOT IN USE ANYMORE.
####

def listToDbString(inputList):
    if len(inputList) == 0:
        dbString = "null"
    else:
        inputList = list(set(inputList))
        dbString = "|| ".join(inputList)
        dbString = Cleaner.standardize(dbString)
        dbString = dbString.replace("\'","\'\'")
        dbString = "\'" + dbString + "\'"
    return dbString

API_Key = os.environ['TWIITER_API_KEY']
API_Secret_Key = os.environ['TWIITER_API_SECRET_KEY']
Access_Token = os.environ['TWIITER_ACCESS_TOKEN']
Access_Token_Secret = os.environ['TWIITER_ACCESS_TOKEN_SECRET']
tagme.GCUBE_TOKEN = os.environ['TAGME_TOKEN']


#Authenticate
auth = tweepy.OAuthHandler(API_Key, API_Secret_Key)
auth.set_access_token(Access_Token, Access_Token_Secret)
api = tweepy.API(auth,wait_on_rate_limit=True,wait_on_rate_limit_notify=True)

params = {"host":"localhost", "database":"POSTS","user": "postgres","password":"admin123"}
#params = {"host":os.environ['POSTGRES_HOST'], "database":os.environ['POSTGRES_DATABASE'],"user": os.environ['POSTGRES_USER'],"password":os.environ['POSTGRES_PASSWORD']} #config('posts')
dbconn = psycopg2.connect(**params)
curget = dbconn.cursor()

query = 'SELECT DISTINCT(\"TWITTER\".\"POST_ID\") FROM \"STREAMED_DATA\".\"TWITTER\" ORDER BY \"TWITTER\".\"POST_ID\" '
curget.execute(query)  
output = curget.fetchall()
dbconn.commit() 
curget.close()
ids=[]
for i in output:
    (p_id,) = i
    ids.append(p_id)
print(ids)

BASE_DIR = Path(__file__).resolve().parent.parent
base = os.path.join(BASE_DIR, 'main')
print(base)
filename = base+"/CustomStopwords.txt"
stopwords = Cleaner.getCustomStopwords(reference="custom", filename=filename)

end = False
startIndex = 0
batch = 30
endIndex = startIndex + batch
# Send batches of 30 to keep the api conn. healthy
while not end:
    if endIndex > len(ids):
        endIndex = len(ids)
        end = True
    conn = psycopg2.connect(os.environ['DATABASE_URL'],sslmode='require')
    cur = conn.cursor()
    tweetContents = api.statuses_lookup(id_=ids[startIndex:endIndex],tweet_mode="extended")
    for tw in tweetContents:
        print(tw)
        if hasattr(tw,"retweeted_status"): 
        #if tw.retweeted:
            is_retweet = "true"
            try:
                text = tw.retweeted_status.extended_tweet["full_text"]
                
            except AttributeError:
                #text = tw.retweeted_status.text
                text = tw.retweeted_status.full_text

        else:
            is_retweet = "false"
            try:
                text = tw.full_text
            except AttributeError:
                text = tw.text
        mentions = tw.entities["user_mentions"]
        hashtags = tw.entities["hashtags"]
        pm = []; ht = []
        for m in mentions:
            if m["name"].isascii():
                pm.append(m["name"])
        for h in hashtags:
            if h["text"].isascii():
                ht.append(h["text"])
        post_id = tw.id_str
        retweet_count = tw.retweet_count
        favorite_count = tw.favorite_count
        user_name = tw.user.screen_name
        post_date = tw.created_at

        p_text_orig = text
        p_text_orig = p_text_orig.replace('\'','\'\'')
        p_mentions = listToDbString(pm)
        p_hashtags = listToDbString(ht)

        #Clean Tweet
        p_text_clean = Cleaner.standardize(text)
        p_text_clean = Cleaner.removeHastags(p_text_clean)
        p_text_clean = Cleaner.removeMentions(p_text_clean)
        p_text_clean = Cleaner.cleanURL(p_text_clean)
        p_text_clean = Cleaner.convertAbbreviations(p_text_clean,filename="Abbreviations.txt")
        p_fortag = p_text_clean
        p_text_clean = Cleaner.removePunctuation(p_text_clean)
        (p_text_clean, p_text_clean_wo_emojis, p_emojis) = Cleaner.convertEmojis(p_text_clean)
        p_emojis = listToDbString(p_emojis)
        p_text_clean = Cleaner.removeStopwords(p_text_clean,stopwords)

        #Analyze
        p_text_lemmatized = Analyzer.lemmatization(p_text_clean)
        sentiment_score = Analyzer.analyzeSentiment(p_text_lemmatized,tool="vader")
        sentiment_result = Analyzer.getSentimentResult(sentiment_score)

        #ENTITIES
        entities = []
        try:
            tags = tagme.annotate(p_fortag)
            for t in tags.get_annotations(0.125):
                t = str(t).split('>')[1].split('(')[0].strip()
                t = t.replace("\'","\'\'")
                entities.append(t)
        except:
            pass
        p_entities = '\'' + "||".join(list(set(entities))) + '\''


        query = 'INSERT INTO twitter (post_content , post_date, hashtags,mentions_screen_name,post_cleaned,emojis,post_lemmatized,sentiment_result,sentiment_score,post_id,user_name,favourite_count,retweet_count,is_retweet,entities) VALUES (\'%s\', TO_DATE(\'%s\',\'YYYY-MM-DD HH24:MI:SS\'),%s,%s,\'%s\',%s,\'%s\',\'%s\',%f,\'%s\',\'%s\',%d,%d,\'%s\',%s) RETURNING id' %(p_text_orig,post_date,p_hashtags,p_mentions,p_text_clean,p_emojis,p_text_lemmatized,sentiment_result,sentiment_score,post_id,user_name,favorite_count,retweet_count,is_retweet,p_entities)
        print("QUERY:",query)
        cur.execute(query)  
        output = cur.fetchone()
        print("OUTPUT:",output)
        conn.commit() 
        print("\n")
    startIndex += batch
    endIndex = startIndex + batch
    cur.close()






   
