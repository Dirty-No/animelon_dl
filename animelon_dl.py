from requests import get , post, Session
from bs4 import BeautifulSoup
import time
import os
import json
import numpy as np
from multiprocessing import Process
import progressbar
import argparse
import sys

def pid_exists(pid):
	try:
		os.kill(pid, 0)
	except OSError:
		return (False)
	else:
		return True

class AnimelonDownloader():
	def __init__(self, baseUrl="https://animelon.com/", session=Session(), processMax=1, sleepTime=5, maxTries=5, savePath="", userAgent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"):
		self.baseUrl = baseUrl
		self.session = session
		self.userAgent = userAgent
		self.videoUserAgent="Mozilla/5=+(dot)+=0 (Linux; Android 9; CPH2015) AppleWebKit/537=+(dot)+=36 (KHTML, like Gecko) Chrome/91=+(dot)+=0=+(dot)+=4472=+(dot)+=164 Mobile Safari/537=+(dot)+=36"
		self.headers = { "user-agent": self.userAgent }
		self.apiVideoFormat = "https://animelon.com/api/languagevideo/findByVideo?videoId=%s&learnerLanguage=en&subs=1&cdnLink=1&viewCounter=1"
		self.session.headers.update(self.headers)
		self.processList = []
		self.processMax = processMax
		self.sleepTime = sleepTime
		self.maxTries = maxTries
		self.savePath = savePath

	def __repr__(self):
		rep = 'AnimelonDownloader(baseUrl="%s", processMax=%d, sleepTime=%d, maxTries=%d, savePath="%s", session=%s, userAgent="%s", headers="%s", processList=%s)' \
		% (self.baseUrl, self.processMax, self.sleepTime, self.maxTries, self.savePath, self.session, self.userAgent, self.headers, self.processList)
		return rep

	def waitForFreeProcess(self, processMax=None):
		if processMax is None:
			processMax = self.processMax
		while len(self.processList) >= processMax:
			newList = [process for process in self.processList if process.is_alive()]
			self.processList = newList
			time.sleep(5)

	def downloadVideo(self, url, fileName=None, stream=None):
		if fileName is None:
			fileName = url.split("/")[-1] + ".mp4"
		video = stream
		if video is None:
			video = self.session.get(url, stream=True)
			# Estimates the number of bar updates
		block_size = 1024
		file_size = int(video.headers.get('Content-Length', None))
		print ("Downloading : ", fileName , "(%.2f MB)" % (file_size * 1024 ** -2) , " ...\n")
		n_chunk = 2
		num_bars = np.ceil(file_size / (n_chunk * block_size))
		bar = None
		if len(self.processList) == 1: 
			bar = progressbar.ProgressBar(maxval=num_bars).start()
		fileName = os.path.join(self.savePath, fileName)
		with open(fileName, 'wb') as f:
			for i, chunk in enumerate(video.iter_content(chunk_size=n_chunk * block_size)):
				f.write(chunk)
				if bar is not None:
					bar.update(i+1)
		# (did not)Add a little sleep so you can see the bar progress

	def downloadFromResObj(self, resObj, fileName=None):
		if fileName is None:
			fileName = resObj["title"] + ".mp4"
		video = (resObj["video"])
		videoUrls = video["videoURLsData"]
		#list of lists of lists of urls, yeah
		#only one of them is valid, so we try all of them
		for mobileUrlList in videoUrls.values():
			for mobileUrlList in videoUrls.values():
				videoUrlsSublist = mobileUrlList["videoURLs"]
				for videoUrl in videoUrlsSublist.values():
					time.sleep(0.2)
					videoStream = self.session.get(videoUrl, stream=True)
					if videoStream.status_code == 200:
						self.downloadVideo(videoUrl, fileName=fileName, stream=videoStream)
						print ("Finished downloading ", fileName)
						return True
		print ("No valid download link found for " + fileName)
		return False

#unused and unfinished
	def recursiveDownload(self, url, filename=None):
		response = get(url, headers=self.headers, stream=True)
		if response.status_code == 200:
			headers = response.headers
			if (headers["Content-Type"] == "video/mp4"):
				self.downloadVideo(url, fileName=filename, stream=response)
				return
			elif (headers["Content-Type"] == "application/json"):
				data = json.loads(response.content)
				if "resObj" in data.keys():
					self.downloadFromResObj(data["resObj"], fileName=filename)
					return
		
	def downloadFromVideoPage(self, url=None, id=None, fileName=None):	
		assert(url is not None or id is not None)
		if url is None:
			url = self.baseUrl + "video/" + id
		if id is None:
			id = url.split("/")[-1]
		apiUrl = self.apiVideoFormat % (id)
		response = get(apiUrl, headers=self.headers)
		print (apiUrl, response)
		jsonsed = json.loads(response.content)
		return (self.downloadFromResObj(jsonsed["resObj"], fileName=fileName))
		
	def getEpisodeList(self, seriesUrl):
		seriesName = seriesUrl.rsplit('/', 1)[-1]
		url = self.baseUrl + "api/series/" + seriesName
		statusCode = 403
		tries = 0
		while statusCode != 200 and tries < self.maxTries:
			response = self.session.get(url)
			statusCode = response.status_code
			tries += 1
			time.sleep(0.5)
		if (statusCode != 200):
			print ("Error getting anime info")
			return None
		try:
			jsoned = json.loads(response.text)
			resObj = jsoned["resObj"]
			assert (resObj is not None)
		except Exception as e:
			print ("Error: Could not parse anime info :\n", e, url , "\n", response, response.content, file=sys.stderr)
			return None
		return resObj

	def initsavePath(self, name):
		if self.savePath == "":
			self.savePath = name
		os.makedirs(self.savePath, exist_ok=True)

	def launchBackgroundDownload(self, url, episode, fileName):
		p = Process(target=self.downloadFromVideoPage, args=(url, episode, fileName))
		self.processList.append(p)
		p.start()
		time.sleep(self.sleepTime)

	def downloadEpisodes(self, episodes:dict, title:str, episodesToDownload:dict=None, seasonNumber:int=0):
		index = 0
		for episode in episodes:
			index += 1
			if episodesToDownload is None or index in episodesToDownload[seasonNumber]:
				self.waitForFreeProcess()
				url = self.baseUrl + "video/" + episode
				fileName = title + " S" + str(seasonNumber) + "E" + str(index) + ".mp4"
				print(fileName, " : ", url)
				try:
					self.launchBackgroundDownload(url, episode, fileName)
				except Exception as e:
					print("Error: Failed to download " + url, file=sys.stderr)
					print(e)

#episodesToDownload = {season_i : [episode_j, episode_j+1]}
	def downloadSeries(self, url, seasonsToDownload:list=None, episodesToDownload:dict=None):
		#https://animelon.com/api/series/Shoujo%20Shuumatsu%20Ryokou%20(Girls'%20Last%20Tour)
		#url = everything after last /
		resObj = self.getEpisodeList(url)
		if resObj is None:
			return
		title = resObj["_id"]
		print("Title:\n", title)
		self.initsavePath(title)
		seasons = resObj["seasons"]
		for season in seasons:
			seasonNumber = int(season["number"])
			if seasonsToDownload is None or seasonNumber in seasonsToDownload:
				print("Season %d:" % (seasonNumber))
				episodes = season["episodes"]
				self.downloadEpisodes(episodes, title, episodesToDownload=episodesToDownload, seasonNumber=seasonNumber)
		self.waitForFreeProcess(processMax=1)

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Downloads videos from animelon.com')
	parser.add_argument('videoURL', metavar='videoURL', type=str,
						help='A video page URL, eg: https://animelon.com/video/579b1be6c13aa2a6b28f1364')
	parser.add_argument('--savePath', metavar='savePath', help='Path to save', type=str, default="")
	parser.add_argument('--forks', metavar='forks', help='Number of worker process for simultaneous downloads (defaults to 1)', type=int, default=1)
	parser.add_argument('-d', metavar='delay', help="Sleep time between each download (defaults to 5)", type=int, default=5)
	parser.add_argument('--maxTries', metavar='maxTries', help='Maximum number of retries in case of failed requests (defaults to 5)', type=int, default=5)
	args = parser.parse_args()
	url = args.videoURL
	type = url.split('/')[3]
	downloader = AnimelonDownloader(savePath=args.savePath, processMax=args.forks, maxTries=args.maxTries, sleepTime=args.d)
	if type == 'series':
		downloader.downloadSeries(url)
	elif type == 'video':
		downloader.downloadFromVideoPage(url)
	else:
		print('Error: Unknown URL type "' + type + '"', file=sys.stderr)

