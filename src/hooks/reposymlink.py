#!/usr/bin/env python

import fuse
import stat
import time

class Reposymlink(object):
	fs = None

	def __init__(self, fs):
		self.fs = fs

	def respond_getattr(self, params):
		path = params[0]
		return path == '/.gitfuserepo'
		
	def getattr(self, params):
		path = params[0]
		ret = fuse.Stat()
		ret.st_mode = stat.S_IFLNK | 0755
		ret.st_nlink = 2
		ret.st_atime = int(time.time())
		ret.st_mtime = ret.st_atime
		ret.st_ctime = ret.st_atime
		return ret

	def respond_readlink(self, params):
		path = params[0]
		return path == '/.gitfuserepo'

	def readlink(self, params):
		path = params[0]
		return self.fs.basePath

	def respond_readdir(self, params):
		path = params[0]
		return path == '/'


	def readdir(self, params):
		path = params[0]
		if path == '/':
			return ['.gitfuserepo'];
