#!/usr/bin/env python
# coding: utf-8

import json, collections, os
from http.client import HTTPSConnection
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import psycopg2
from . import Cleaner, Analyzer
#import Cleaner, Analyzer

from configparser import ConfigParser
import json, tweepy, requests, sys, subprocess, os
import pandas as pd 
import snscrape.modules.twitter
import string, nltk,re, emot,tagme
from datetime import datetime
from datetime import timedelta
from .Tweet import Tweet
#from Tweet import Tweet
import environ

#####
# COLLECTS TWEET DATA FROM THE DATABASE
#####

#converts list to string, uses escape characters, token: ||
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

#checks if there is any data for a certain period of time in the database --- DEPRECATED
def checkDbForDate(startDate,endDate):
    #params = {"host":os.environ['POSTGRES_HOST'], "database":os.environ['POSTGRES_DATABASE'],"user": os.environ['POSTGRES_USER'],"password":os.environ['POSTGRES_PASSWORD']} #config('posts')
    #params = {"host":env("POSTGRES_HOST"), "database":env("POSTGRES_DATABASE"),"user": env("POSTGRES_USER"),"password":env("POSTGRES_PASSWORD")} #config('posts')
    #dbconn = psycopg2.connect(**params)
    
    dbconn = psycopg2.connect(os.environ['DATABASE_URL'],sslmode='require')
    cur = dbconn.cursor()

    #query = 'SELECT DISTINCT(\"TWITTER\".\"POST_DATE\") FROM \"STREAMED_DATA\".\"TWITTER\"'
    query = 'SELECT DISTINCT(post_date) FROM twitter'
    cur.execute(query)  
    output = cur.fetchall()
    dbconn.commit() 
    cur.close()
    exists = True
    dates = []
    for i in output:
        (tarih,)=i
        print(str(tarih.strftime('%Y-%m-%d')))
        dates.append(str(tarih.strftime('%Y-%m-%d')))
    date1 = datetime.strptime(startDate, '%Y-%m-%d')
    date2 = datetime.strptime(endDate, '%Y-%m-%d')
    while date1 <= date2:
        print("check for",str(date1).split(' ')[0])
        if str(date1).split(' ')[0] not in dates:
            exists = False
            break
        date1 = date1 + timedelta(days=1)
    return exists

# Queries db for tweets with filters: start date, end date, search words. Returns a data frame of tweets content
def getTweetDF(option,fromDate="",toDate="",searchwords=""):

    ##Get tweets from DB
    dbconn = psycopg2.connect(os.environ['DATABASE_URL'],sslmode='require')
    cur = dbconn.cursor()
    
    if option.lower() == "all":
        query = 'SELECT post_id,post_content,user_name,post_date,post_lemmatized,hashtags,sentiment_result,mentions_screen_name,favourite_count,retweet_count,entities FROM twitter ORDER BY id DESC LIMIT 100'
        cur.execute(query)  
        output = cur.fetchall()
        dbconn.commit() 
        cur.close()

    elif option.lower() == "thisweek":
        now = datetime.now()
        lastweek = now - timedelta(days=6)
        toDate = now.strftime("%Y-%m-%d")
        fromDate = lastweek.strftime("%Y-%m-%d")
        
        date1 = fromDate
        date1 = datetime.strptime(fromDate, '%Y-%m-%d')
        endDate = datetime.strptime(toDate, '%Y-%m-%d')
        date2= endDate + timedelta(days=1)
        daylimit = 500
        print("daylimit:",daylimit)
        output = []
        end_date = date2.strftime("%Y-%m-%d")
        while end_date > fromDate:
            print("end:",end_date)
            print("todate:",toDate)
            query_end = datetime.strptime(end_date,"%Y-%m-%d")
            query_start = query_end - timedelta(days=1)
            query_start_str = query_start.strftime("%Y-%m-%d")
            query = 'SELECT post_id,post_content,user_name,post_date,post_lemmatized,hashtags,sentiment_result,mentions_screen_name,favourite_count,retweet_count,entities FROM twitter WHERE post_date >= \'%s\' AND post_date < \'%s\' ORDER BY post_id DESC LIMIT %d' %(query_start_str,end_date,daylimit)
            print(query)
            cur.execute(query)  
            output += cur.fetchall()
            dbconn.commit()
            print("output:",len(output))
            
            end_date = query_start_str
        cur.close()

    elif option.lower() == "today":
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        query = 'SELECT post_id,post_content,user_name,post_date,post_lemmatized,hashtags,sentiment_result,mentions_screen_name,favourite_count,retweet_count,entities FROM twitter WHERE post_date = \'%s\' ORDER BY id DESC LIMIT 1500' %(today)
        cur.execute(query)  
        output = cur.fetchall()
        dbconn.commit() 
        cur.close()
    
    elif option.lower() == "custom":

        if fromDate != "" and toDate != "":
            print("collecting:", fromDate, "-", toDate)
            date1 = fromDate
            date1 = datetime.strptime(fromDate, '%Y-%m-%d')
            endDate = datetime.strptime(toDate, '%Y-%m-%d')
            date2= endDate + timedelta(days=1)
            daylimit = 1500 / (int(str(endDate - date1).split('day')[0].strip()) + 1)
            print("daylimit:",daylimit)
            output = []
            end_date = date2.strftime("%Y-%m-%d")
            while end_date > fromDate:
                print("end:",end_date)
                print("todate:",toDate)
                query_end = datetime.strptime(end_date,"%Y-%m-%d")
                query_start = query_end - timedelta(days=1)
                query_start_str = query_start.strftime("%Y-%m-%d")

                #query = 'SELECT \"TWITTER\".\"POST_CONTENT\",\"TWITTER\".\"POST_DATE\",\"TWITTER\".\"POST_LEMMATIZED\",\"TWITTER\".\"HASHTAGS\",\"TWITTER\".\"SENTIMENT_RESULT\",\"TWITTER\".\"MENTIONS_SCREEN_NAME\",\"TWITTER\".\"ENTITIES\" FROM \"STREAMED_DATA\".\"TWITTER\" WHERE \"TWITTER\".\"POST_DATE\" >= \'%s\' AND \"TWITTER\".\"POST_DATE\" < \'%s\' ORDER BY \"TWITTER\".\"ID\" DESC LIMIT 100' %(fromDate,toDate)
                if searchwords == "":
                    query = 'SELECT post_id,post_content,user_name,post_date,post_lemmatized,hashtags,sentiment_result,mentions_screen_name,favourite_count,retweet_count,entities FROM twitter WHERE post_date >= \'%s\' AND post_date < \'%s\' ORDER BY post_id DESC LIMIT %d' %(query_start_str,end_date,daylimit)
                else:
                    query = 'SELECT post_id,post_content,user_name,post_date,post_lemmatized,hashtags,sentiment_result,mentions_screen_name,favourite_count,retweet_count,entities FROM twitter WHERE post_date >= \'%s\' AND post_date < \'%s\' AND LOWER(post_content) LIKE '%(query_start_str,end_date) +'\'%' + searchwords + '%\'' + ' ORDER BY post_id DESC LIMIT %d' %(daylimit)
                print(query)
                cur.execute(query)  
                output += cur.fetchall()
                dbconn.commit()
                print("output:",len(output))
                
                end_date = query_start_str
            cur.close()
        

        elif fromDate == "" and toDate != "":
            print("collecting to: ", toDate)
            if searchwords == "":
                query = 'SELECT post_id,post_content,user_name,post_date,post_lemmatized,hashtags,sentiment_result,mentions_screen_name,favourite_count,retweet_count,entities FROM twitter WHERE post_date <= \'%s\' ORDER BY post_id DESC LIMIT 1500' %(toDate)
            else:
                query = 'SELECT post_id,post_content,user_name,post_date,post_lemmatized,hashtags,sentiment_result,mentions_screen_name,favourite_count,retweet_count,entities FROM twitter WHERE post_date <= \'%s\' AND LOWER(post_content) LIKE '%(toDate) +'\'%' + searchwords + '%\'' + ' ORDER BY post_id DESC LIMIT 1500'
            print(query)
            cur.execute(query)  
            output = cur.fetchall()
            dbconn.commit()
            print("output:",len(output))
            cur.close()
        elif fromDate != "" and toDate == "":
            print("collecting from: ", fromDate)
            if searchwords == "":
                query = 'SELECT post_id,post_content,user_name,post_date,post_lemmatized,hashtags,sentiment_result,mentions_screen_name,favourite_count,retweet_count,entities FROM twitter WHERE post_date >= \'%s\' ORDER BY post_id ASC LIMIT 1500' %(fromDate)
            else:
                query = 'SELECT post_id,post_content,user_name,post_date,post_lemmatized,hashtags,sentiment_result,mentions_screen_name,favourite_count,retweet_count,entities FROM twitter WHERE post_date >= \'%s\' AND LOWER(post_content) LIKE '%(fromDate) +'\'%' + searchwords + '%\'' + ' ORDER BY post_id ASC LIMIT 1500'
            print(query)
            cur.execute(query)  
            output = cur.fetchall()
            dbconn.commit()
            print("output:",len(output))
            cur.close()
        else:
            output = []
    
  
    elif option.lower() == "search":
        #query = 'SELECT \"TWITTER\".\"POST_CONTENT\",\"TWITTER\".\"POST_DATE\",\"TWITTER\".\"POST_LEMMATIZED\",\"TWITTER\".\"HASHTAGS\",\"TWITTER\".\"SENTIMENT_RESULT\",\"TWITTER\".\"MENTIONS_SCREEN_NAME\",\"TWITTER\".\"ENTITIES\" FROM \"STREAMED_DATA\".\"TWITTER\" WHERE LOWER(\"TWITTER\".\"POST_CONTENT\") LIKE ' +'\'%' + searchwords + '%\'' + ' ORDER BY \"TWITTER\".\"ID\" DESC LIMIT 1000'
        query = 'SELECT post_id,post_content,user_name,post_date,post_lemmatized,hashtags,sentiment_result,mentions_screen_name,favourite_count,retweet_count,entities FROM twitter WHERE LOWER(post_content) LIKE ' +'\'%' + searchwords + '%\'' + ' ORDER BY post_id DESC LIMIT 1500'
        print(query)
        cur.execute(query)  
        output = cur.fetchall()
        dbconn.commit() 
        cur.close()
    
    dfDict = {"post_id":[],"orig_content":[],"user_name":[],"date":[],"lemma":[],"tags":[],"sentiment":[],"mentions":[],"favourite_count":[],"retweet_count":[],"entities":[]}
    for tweet in output:
        #print(tweet)
        (post_id,orig_content,user_name,post_date,lemma,tags,sentiment,mentions,favourite_count,retweet_count,entities) = tweet
        dfDict["orig_content"].append(orig_content)
        dfDict["post_id"].append(post_id)
        dfDict["user_name"].append(user_name)
        dfDict["lemma"].append(lemma)
        dfDict["tags"].append(tags)
        dfDict["sentiment"].append(sentiment)
        dfDict["mentions"].append(mentions)
        dfDict["favourite_count"].append(favourite_count)
        dfDict["retweet_count"].append(retweet_count)
        dfDict["entities"].append(entities)
        dfDict["date"].append(post_date)

    tweetDF = pd.DataFrame.from_dict(dfDict)
    return tweetDF

# Collect tweets using snscrape --- DEPRECATED
def getTweetsFromPast(fromDate,toDate):
    ''' % LOCAL TESTS
    API_Key = env("TWIITER_API_KEY")
    API_Secret_Key = env("TWIITER_API_SECRET_KEY")
    Access_Token = env("TWIITER_ACCESS_TOKEN")
    Access_Token_Secret = env("TWIITER_ACCESS_TOKEN_SECRET")
    '''
    API_Key = os.environ['TWIITER_API_KEY']
    API_Secret_Key = os.environ['TWIITER_API_SECRET_KEY']
    Access_Token = os.environ['TWIITER_ACCESS_TOKEN']
    Access_Token_Secret = os.environ['TWIITER_ACCESS_TOKEN_SECRET']
    
    #Authenticate
    auth = tweepy.OAuthHandler(API_Key, API_Secret_Key)
    auth.set_access_token(Access_Token, Access_Token_Secret)
    api = tweepy.API(auth,wait_on_rate_limit=True,wait_on_rate_limit_notify=True)

    ids=[]; tweets = []
    date1 = fromDate
    date1 = datetime.strptime(fromDate, '%Y-%m-%d')
    date2 = date1 + timedelta(days=1)
    endDate = datetime.strptime(toDate, '%Y-%m-%d')
    daylimit = 100 / (int(str(endDate - date1).split('day')[0].strip()) + 1)
    while date1 <= endDate:
        dayIds=[]
        #print(str(date1))
        #print(str(date2))
        date1 = date2
        date2 = date1 + timedelta(days=1)
        query = "covid since:%s until:%s lang:en" %(str(date1).split(' ')[0],str(date2).split(' ')[0])
        #print(query)
        for tweet in snscrape.modules.twitter.TwitterSearchScraper(query).get_items():
            tl = str(tweet).split('/')[-1]
            #print(tl)
            #print(tweet.content)
            dayIds.append(tl)
            if len(dayIds) >= daylimit:
                break
        ids += dayIds
    print("total: " , len(ids))
    
    end = False
    startIndex = 0
    batch = 30
    endIndex = startIndex + batch
    while not end:
        if endIndex > len(ids):
            endIndex = len(ids)
            end = True
        tweetContents = api.statuses_lookup(id_=ids[startIndex:endIndex],tweet_mode="extended")
        for tw in tweetContents:
            if hasattr(tw,"retweeted_status"): 
                rt = "true"
                try:
                    text = tw.retweeted_status.extended_tweet["full_text"]
                    
                except AttributeError:
                    text = tw.retweeted_status.text
            else:
                rt = "false"
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

            tweet = Tweet(text,tw.id_str,tw.user.screen_name,tw.created_at,ht,pm,tw.favorite_count,tw.retweet_count,rt)   
            tweets.append(tweet)
        startIndex += batch
        endIndex = startIndex + batch

    return tweets

# format tweet data from snscrape --- DEPRECATED
def preparePastTweets(tweets):
    dfDict = {"orig_content":[],"date":[],"lemma":[],"tags":[],"sentiment":[],"mentions":[],"favourite_count":[],"retweet_count":[],"entities":[]}
    tagme.GCUBE_TOKEN = os.environ['TAGME_TOKEN']

    stopwords = Cleaner.getCustomStopwords(reference="custom", filename="main\CustomStopwords.txt")
    for tweet in tweets:

        p_text_orig = tweet.text
        p_text_orig = p_text_orig.replace('\'','\'\'')
        p_date = tweet.post_date
        p_mentions = listToDbString(tweet.mentions)
        p_hashtags = listToDbString(tweet.hashtags)

        #Clean Tweet
        p_text_clean = Cleaner.standardize(tweet.text)
        p_text_clean = Cleaner.removeHastags(p_text_clean)
        p_text_clean = Cleaner.removeMentions(p_text_clean)
        p_text_clean = Cleaner.cleanURL(p_text_clean)
        p_text_clean = Cleaner.convertAbbreviations(p_text_clean)
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
        tags = tagme.annotate(p_fortag)
        for t in tags.get_annotations(0.125):
            t = str(t).split('>')[1].split('(')[0].strip()
            t = t.replace("\'","\'\'")
            entities.append(t)
        p_entities = "||".join(list(set(entities)))

        dfDict["orig_content"].append(p_text_orig)
        dfDict["lemma"].append(p_text_lemmatized)
        dfDict["tags"].append(p_hashtags)
        dfDict["sentiment"].append(sentiment_result)
        dfDict["mentions"].append(p_mentions)
        dfDict["entities"].append(p_entities)
        p_date = p_date.strftime('%b. %d, %Y')
        dfDict["date"].append(str(p_date))

    tweetDF = pd.DataFrame.from_dict(dfDict)

    return tweetDF

# returns most frequent hastags in a tweet list
def getTopHashtags(tweets,count=15):
    
    hashtags = tweets['tags']
    hashlist = []
    for tags in hashtags:
        try:
            t = tags.split('||')
            for i in t:
                hashlist.append(i.strip())
        except AttributeError:
            pass
    hashCnt = dict(collections.Counter(hashlist))
    dfDict = {"topics":[],"count":[]}
   
    for w in hashCnt.keys():
        dfDict["topics"].append(w)
        dfDict["count"].append(hashCnt[w])
    hashDF = pd.DataFrame({"count":dfDict["count"]},index=dfDict["topics"])
    hashDF.sort_values(by=["count"],ascending=False,inplace=True)
    hashDF = hashDF.head(count)
    
    return hashDF

# prepare sentiment results for bar chart format
def getSentimentResults(tweets):

    sentiment_dict = {}
    sentiment_df = tweets[["date", "sentiment"]]
    sentiments = [['Date', 'Very Positive','Positive', 'Neutral', 'Negative','Very Negative']]
    dates = list(set(sentiment_df["date"]))
    dates.sort()
    for d in dates:
        sentiment_dict[d] = {"Very_Positive":0,"Positive":0,"Negative":0,"Neutral":0,"Very_Negative":0,}
    for i in range(len(sentiment_df.index)):
        sent = tweets["sentiment"][i].strip().replace(' ','_')
        sentiment_dict[tweets["date"][i]][sent] += 1
    for d in dates:
        total = sentiment_dict[d]["Very_Positive"] + sentiment_dict[d]["Positive"] + sentiment_dict[d]["Neutral"] + sentiment_dict[d]["Negative"]+ sentiment_dict[d]["Very_Negative"]
        sentiments.append([str(d), (sentiment_dict[d]["Very_Positive"]/total)*100, (sentiment_dict[d]["Positive"]/total)*100,(sentiment_dict[d]["Neutral"]/total)*100,(sentiment_dict[d]["Negative"]/total)*100,(sentiment_dict[d]["Very_Negative"]/total)*100])
    return sentiments